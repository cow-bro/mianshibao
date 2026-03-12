from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppException
from app.models.interview_message import InterviewMessage, InterviewMessageRole
from app.models.interview_report import InterviewReport as InterviewReportModel
from app.models.interview_session import InterviewSession, InterviewStatus
from app.models.resume import Resume
from app.models.user import User
from app.schemas.interview import InterviewStartRequest, InterviewState
from app.services.interview_graph import InterviewGraphService

logger = logging.getLogger(__name__)


class InterviewService:
    def __init__(self) -> None:
        self.graph = InterviewGraphService()
        self._state_cache: dict[int, InterviewState] = {}
        self._disconnected_at: dict[int, datetime] = {}

    async def create_session(
        self,
        db: AsyncSession,
        user: User,
        payload: InterviewStartRequest,
    ) -> InterviewSession:
        session = InterviewSession(
            user_id=user.id,
            resume_id=payload.resume_id,
            position_id=payload.position_id,
            target_company=payload.target_company,
            target_position=payload.target_position,
            job_description=payload.job_description,
            status=InterviewStatus.INIT,
            current_stage="WELCOME",
            interview_start_time=datetime.now(UTC),
            max_total_questions=payload.max_total_questions,
            max_resume_dig_questions=payload.max_resume_dig_questions,
            max_tech_qa_questions=payload.max_tech_qa_questions,
            max_interview_duration=payload.max_interview_duration,
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    async def get_owned_session(self, db: AsyncSession, session_id: int, user_id: int) -> InterviewSession:
        stmt = select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == user_id,
        )
        result = await db.execute(stmt)
        session = result.scalar_one_or_none()
        if session is None:
            raise AppException("interview session not found", code=404)
        return session

    async def load_or_init_state(
        self,
        db: AsyncSession,
        session: InterviewSession,
    ) -> InterviewState:
        cached = self._state_cache.get(session.id)
        if cached is not None:
            return cached

        parsed_resume: dict | None = None
        if session.resume_id:
            resume = await db.get(Resume, session.resume_id)
            if resume:
                parsed_resume = resume.parsed_content

        state = self.graph.init_state(
            session_id=session.id,
            user_id=session.user_id,
            resume_id=session.resume_id,
            target_company=session.target_company or "目标公司",
            target_position=session.target_position or "目标岗位",
            job_description=session.job_description or "",
            parsed_resume=parsed_resume,
            max_total_questions=session.max_total_questions,
            max_resume_dig_questions=session.max_resume_dig_questions,
            max_tech_qa_questions=session.max_tech_qa_questions,
            max_interview_duration=session.max_interview_duration,
            human_enabled=session.is_human_intervention_enabled,
        )
        state["created_at"] = session.created_at.isoformat()

        self._state_cache[session.id] = state
        return state

    async def ensure_welcome_turn(self, db: AsyncSession, session: InterviewSession) -> InterviewState:
        state = await self.load_or_init_state(db, session)
        if state["message_history"]:
            return state
        state = await self.graph.run_turn(state, db)
        await self._persist_delta(db, session, state)
        return state

    async def handle_candidate_message(
        self,
        db: AsyncSession,
        session: InterviewSession,
        message: str,
    ) -> InterviewState:
        state = await self.load_or_init_state(db, session)
        state["current_answer"] = message
        state = await self.graph.run_turn(state, db)
        await self._persist_delta(db, session, state)
        return state

    async def _persist_delta(self, db: AsyncSession, session: InterviewSession, state: InterviewState) -> None:
        persisted_count = int(state.get("_persisted_messages", 0))
        new_messages = state["message_history"][persisted_count:]

        for item in new_messages:
            role = InterviewMessageRole.INTERVIEWER if item.get("role") == "interviewer" else InterviewMessageRole.CANDIDATE
            db.add(
                InterviewMessage(
                    session_id=session.id,
                    role=role,
                    content=item.get("content", ""),
                    stage=item.get("stage"),
                    question_index=int(item.get("question_index", 0) or 0),
                )
            )

        session.current_stage = state["current_stage"].value
        session.interview_duration_seconds = state["interview_duration_seconds"]
        if state["status"] == "ONGOING":
            session.status = InterviewStatus.ONGOING
        if state["status"] == "ENDED":
            session.status = InterviewStatus.ENDED

        if state["status"] == "ENDED":
            await self._persist_report(db, session, state)

        await db.commit()
        state["_persisted_messages"] = len(state["message_history"])

    async def _persist_report(self, db: AsyncSession, session: InterviewSession, state: InterviewState) -> None:
        if "report" not in state:
            return

        existing = await db.execute(
            select(InterviewReportModel).where(InterviewReportModel.session_id == session.id)
        )
        report = existing.scalar_one_or_none()
        payload = state["report"]
        if report is None:
            report = InterviewReportModel(
                session_id=session.id,
                user_id=session.user_id,
                target_company=payload.get("target_company"),
                target_position=payload.get("target_position"),
                interview_duration_seconds=int(payload.get("interview_duration_seconds", 0)),
                total_questions=int(payload.get("total_questions", 0)),
                overall_score=float(payload.get("overall_score", 0)),
                professional_knowledge_score=float(payload.get("professional_knowledge_score", 0)),
                project_experience_score=float(payload.get("project_experience_score", 0)),
                logical_thinking_score=float(payload.get("logical_thinking_score", 0)),
                communication_score=float(payload.get("communication_score", 0)),
                position_match_score=float(payload.get("position_match_score", 0)),
                highlights=payload.get("highlights", []),
                weaknesses=payload.get("weaknesses", []),
                improvement_suggestions=payload.get("improvement_suggestions", []),
                recommended_knowledge_points=payload.get("recommended_knowledge_points", []),
                interview_summary=payload.get("interview_summary", ""),
                answer_scores=state.get("answer_quality_scores", []),
            )
            db.add(report)
            return

        report.overall_score = float(payload.get("overall_score", report.overall_score))
        report.professional_knowledge_score = float(
            payload.get("professional_knowledge_score", report.professional_knowledge_score)
        )
        report.project_experience_score = float(
            payload.get("project_experience_score", report.project_experience_score)
        )
        report.logical_thinking_score = float(payload.get("logical_thinking_score", report.logical_thinking_score))
        report.communication_score = float(payload.get("communication_score", report.communication_score))
        report.position_match_score = float(payload.get("position_match_score", report.position_match_score))
        report.highlights = payload.get("highlights", report.highlights)
        report.weaknesses = payload.get("weaknesses", report.weaknesses)
        report.improvement_suggestions = payload.get("improvement_suggestions", report.improvement_suggestions)
        report.recommended_knowledge_points = payload.get(
            "recommended_knowledge_points", report.recommended_knowledge_points
        )
        report.interview_summary = payload.get("interview_summary", report.interview_summary)
        report.answer_scores = state.get("answer_quality_scores", report.answer_scores)

    def mark_disconnect(self, session_id: int) -> None:
        self._disconnected_at[session_id] = datetime.now(UTC)

    def cleanup_expired(self, ttl_minutes: int = 15) -> None:
        cutoff = datetime.now(UTC) - timedelta(minutes=ttl_minutes)
        expired = [sid for sid, at in self._disconnected_at.items() if at < cutoff]
        for sid in expired:
            self._disconnected_at.pop(sid, None)
            self._state_cache.pop(sid, None)


interview_service = InterviewService()
