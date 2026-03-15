from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.core.response import success_response
from app.models.interview_report import InterviewReport
from app.models.user import User
from app.schemas.interview import InterviewStartRequest, InterviewStartResponse
from app.services.interview_service import interview_service

router = APIRouter()
service = interview_service


@router.post("/sessions", summary="Create interview session")
async def create_interview_session(
    payload: InterviewStartRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    session = await service.create_session(db=db, user=current_user, payload=payload)
    data = InterviewStartResponse(
        session_id=session.id,
        status=session.status.value,
        current_stage=session.current_stage or "WELCOME",
    )
    return success_response(data=data.model_dump())


@router.get("/sessions/{session_id}/report", summary="Get interview report")
async def get_interview_report(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    session = await service.get_owned_session(db, session_id=session_id, user_id=current_user.id)
    result = await db.execute(select(InterviewReport).where(InterviewReport.session_id == session.id))
    report = result.scalar_one_or_none()
    if report is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="report not ready")

    return success_response(
        data={
            "session_id": report.session_id,
            "overall_score": report.overall_score,
            "professional_knowledge_score": report.professional_knowledge_score,
            "project_experience_score": report.project_experience_score,
            "logical_thinking_score": report.logical_thinking_score,
            "communication_score": report.communication_score,
            "position_match_score": report.position_match_score,
            "highlights": report.highlights,
            "weaknesses": report.weaknesses,
            "improvement_suggestions": report.improvement_suggestions,
            "recommended_knowledge_points": report.recommended_knowledge_points,
            "interview_summary": report.interview_summary,
            "answer_scores": report.answer_scores,
        }
    )


@router.post("/sessions/{session_id}/end", summary="End interview session")
async def end_interview_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
) -> dict:
    session = await service.get_owned_session(db, session_id=session_id, user_id=current_user.id)
    state = await service.end_session(db=db, session=session, message="结束面试")
    return success_response(
        data={
            "session_id": session.id,
            "status": state["status"],
            "current_stage": state["current_stage"].value,
            "report_ready": state["status"] == "ENDED",
        }
    )


@router.post("/{session_id}/human-intervention/enable", summary="Enable human intervention (reserved)")
async def human_enable(session_id: int) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"session {session_id}: not implemented")


@router.post("/{session_id}/human-intervention/pause", summary="Pause for human intervention (reserved)")
async def human_pause(session_id: int) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"session {session_id}: not implemented")


@router.post("/{session_id}/human-intervention/message", summary="Send human operator message (reserved)")
async def human_message(session_id: int) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"session {session_id}: not implemented")


@router.post("/{session_id}/human-intervention/resume", summary="Resume AI interview (reserved)")
async def human_resume(session_id: int) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"session {session_id}: not implemented")


@router.put("/{session_id}/report/adjust", summary="Adjust interview report (reserved)")
async def adjust_report(session_id: int) -> None:
    raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail=f"session {session_id}: not implemented")
