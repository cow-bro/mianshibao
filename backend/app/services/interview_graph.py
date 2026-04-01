from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except Exception:  # pragma: no cover - optional dependency safety
    END = "__end__"  # type: ignore[assignment]
    START = "__start__"  # type: ignore[assignment]
    StateGraph = None  # type: ignore[assignment]
    LANGGRAPH_AVAILABLE = False

from app.providers.llm_factory import LLMService
from app.providers.checkpointer import build_checkpointer
from app.schemas.interview import InterviewReport, InterviewStage, InterviewState
from app.services.knowledge_service import KnowledgeService
from app.utils.prompt_manager import PromptManager

logger = logging.getLogger(__name__)


class InterviewGraphService:
    """State-machine based interview orchestration service."""

    def __init__(self) -> None:
        self.llm_service = LLMService()
        self.knowledge_service = KnowledgeService()
        self.checkpointer = build_checkpointer()
        self.prompt_manager = PromptManager()
        self._runtime_db = None
        self._token_callback = None
        self.graph = self._build_graph()

    @staticmethod
    def now_iso() -> str:
        return datetime.now(UTC).isoformat()

    @staticmethod
    def _thread_id(session_id: str | int) -> str:
        return f"interview-session-{session_id}"

    def _config_for_state(self, state: InterviewState) -> dict[str, dict[str, str]]:
        return {
            "configurable": {
                "thread_id": self._thread_id(state["session_id"]),
            }
        }

    @staticmethod
    def _supports_checkpointer(checkpointer: Any) -> bool:
        sync_methods = ("get_tuple", "put", "put_writes")
        async_methods = ("aget_tuple", "aput", "aput_writes")
        return all(hasattr(checkpointer, method) for method in sync_methods) or all(
            hasattr(checkpointer, method) for method in async_methods
        )

    def _build_graph(self):
        if not LANGGRAPH_AVAILABLE or StateGraph is None:
            logger.warning("LangGraph not available, using fallback state dispatcher")
            return None

        workflow = StateGraph(InterviewState)
        workflow.add_node("route", self._route_node)
        workflow.add_node("welcome", self._welcome_node)
        workflow.add_node("resume_dig", self._resume_dig_node)
        workflow.add_node("tech_qa", self._tech_qa_node)
        workflow.add_node("candidate_question", self._candidate_question_node)
        workflow.add_node("end", self._end_node)
        workflow.add_node("human_waiting", self._human_waiting_node)

        workflow.add_edge(START, "route")
        workflow.add_conditional_edges(
            "route",
            self._route_selector,
            {
                "welcome": "welcome",
                "resume_dig": "resume_dig",
                "tech_qa": "tech_qa",
                "candidate_question": "candidate_question",
                "end": "end",
                "human_waiting": "human_waiting",
            },
        )
        workflow.add_edge("welcome", END)
        workflow.add_edge("resume_dig", END)
        workflow.add_edge("tech_qa", END)
        workflow.add_edge("candidate_question", END)
        workflow.add_edge("end", END)
        workflow.add_edge("human_waiting", END)

        compile_kwargs: dict[str, Any] = {}
        if self._supports_checkpointer(self.checkpointer):
            compile_kwargs["checkpointer"] = self.checkpointer
        else:
            logger.warning("LangGraph checkpointer unsupported, compiling without checkpointer")

        return workflow.compile(**compile_kwargs)

    def load_state_from_checkpoint(self, session_id: int) -> InterviewState | None:
        if self.graph is None or not hasattr(self.graph, "get_state"):
            return None

        config = {"configurable": {"thread_id": self._thread_id(session_id)}}
        try:
            snapshot = self.graph.get_state(config)
            values = getattr(snapshot, "values", None)
            if not isinstance(values, dict) or not values:
                return None
            return self._normalize_state(values)
        except Exception:
            logger.exception("Failed to load checkpoint state for session_id=%s", session_id)
            return None

    def init_state(
        self,
        *,
        session_id: int,
        user_id: int,
        resume_id: int | None,
        target_company: str,
        target_position: str,
        job_description: str,
        parsed_resume: dict | None,
        max_total_questions: int,
        max_resume_dig_questions: int,
        max_tech_qa_questions: int,
        max_interview_duration: int,
        human_enabled: bool = False,
    ) -> InterviewState:
        now = self.now_iso()
        return {
            "session_id": str(session_id),
            "user_id": str(user_id),
            "resume_id": str(resume_id or ""),
            "target_company": target_company,
            "target_position": target_position,
            "job_description": job_description,
            "status": "INIT",
            "current_stage": InterviewStage.WELCOME,
            "current_question_index": 0,
            "resume_dig_question_count": 0,
            "tech_qa_question_count": 0,
            "candidate_question_rounds": 0,
            "max_total_questions": max_total_questions,
            "max_resume_dig_questions": max_resume_dig_questions,
            "max_tech_qa_questions": max_tech_qa_questions,
            "interview_start_time": now,
            "interview_duration_seconds": 0,
            "max_interview_duration": max_interview_duration,
            "parsed_resume": parsed_resume or {},
            "current_resume_focus": None,
            "current_tech_stack_focus": self._extract_skills(job_description),
            "message_history": [],
            "current_question": None,
            "current_answer": None,
            "answer_quality_scores": [],
            "is_human_intervention_enabled": human_enabled,
            "human_intervention_status": None,
            "human_operator_id": None,
            "created_at": now,
            "updated_at": now,
            "trace_id": uuid4().hex,
            "_persisted_messages": 0,
        }

    async def run_turn(self, state: InterviewState, db, token_callback=None) -> InterviewState:
        state = self._normalize_state(state)
        if self.graph is None:
            return await self._run_turn_fallback(state, db, token_callback=token_callback)

        config = self._config_for_state(state)
        self._runtime_db = db
        self._token_callback = token_callback
        try:
            result = await asyncio.to_thread(self.graph.invoke, state, config)
            return self._normalize_state(result)
        except Exception:
            logger.exception("LangGraph invocation failed, fallback to local dispatcher")
            return await self._run_turn_fallback(state, db, token_callback=token_callback)
        finally:
            self._runtime_db = None
            self._token_callback = None

    async def _run_turn_fallback(self, state: InterviewState, db, token_callback=None) -> InterviewState:
        state["updated_at"] = self.now_iso()
        state["interview_duration_seconds"] = self._calculate_duration_seconds(state)
        self._token_callback = token_callback

        self._record_candidate_answer_if_needed(state)

        if self._is_end_signal(state.get("current_answer")):
            state["current_stage"] = InterviewStage.END

        if state["is_human_intervention_enabled"] and state.get("human_intervention_status") == InterviewStage.HUMAN_INTERVENTION_WAITING:
            return self._human_waiting_node(state)

        stage = state["current_stage"]
        if stage == InterviewStage.WELCOME:
            return self._welcome_node(state)
        if stage == InterviewStage.RESUME_DIG:
            return self._resume_dig_node(state)
        if stage == InterviewStage.TECH_QA:
            self._runtime_db = db
            try:
                return self._tech_qa_node(state)
            finally:
                self._runtime_db = None
                self._token_callback = None
        if stage == InterviewStage.CANDIDATE_QUESTION:
            return self._candidate_question_node(state)
        if stage == InterviewStage.END:
            return self._end_node(state)
        self._token_callback = None
        return state

    def _route_node(self, state: InterviewState) -> InterviewState:
        state["updated_at"] = self.now_iso()
        state["interview_duration_seconds"] = self._calculate_duration_seconds(state)
        self._record_candidate_answer_if_needed(state)

        if self._is_end_signal(state.get("current_answer")):
            state["current_stage"] = InterviewStage.END

        if state["is_human_intervention_enabled"] and state.get("human_intervention_status") == InterviewStage.HUMAN_INTERVENTION_WAITING:
            state["_next_node"] = "human_waiting"
            return state

        stage = state["current_stage"]
        if stage == InterviewStage.WELCOME:
            state["_next_node"] = "welcome"
        elif stage == InterviewStage.RESUME_DIG:
            state["_next_node"] = "resume_dig"
        elif stage == InterviewStage.TECH_QA:
            state["_next_node"] = "tech_qa"
        elif stage == InterviewStage.CANDIDATE_QUESTION:
            state["_next_node"] = "candidate_question"
        else:
            state["_next_node"] = "end"
        return state

    @staticmethod
    def _route_selector(state: InterviewState) -> str:
        next_node = str(state.get("_next_node") or "end")
        if next_node in {"welcome", "resume_dig", "tech_qa", "candidate_question", "human_waiting", "end"}:
            return next_node
        return "end"

    @staticmethod
    def _normalize_state(state: dict[str, Any]) -> InterviewState:
        normalized = dict(state)
        current_stage = normalized.get("current_stage")
        if isinstance(current_stage, str):
            normalized["current_stage"] = InterviewStage(current_stage)
        human_stage = normalized.get("human_intervention_status")
        if isinstance(human_stage, str):
            normalized["human_intervention_status"] = InterviewStage(human_stage)
        return normalized  # type: ignore[return-value]

    def _welcome_node(self, state: InterviewState) -> InterviewState:
        if not state["message_history"]:
            message = self._generate_welcome(state)
            self._append_interviewer_message(state, message, InterviewStage.WELCOME)
            state["status"] = "ONGOING"
            return state

        candidate_input = (state.get("current_answer") or "").strip()
        if not candidate_input:
            return state

        if self._looks_like_candidate_question(candidate_input):
            state["current_stage"] = InterviewStage.CANDIDATE_QUESTION
            msg = self._generate_candidate_question_response(state, candidate_input)
            self._append_interviewer_message(state, msg, InterviewStage.CANDIDATE_QUESTION)
            return state

        if not state.get("opening_intro_requested"):
            if self._is_ready_signal(candidate_input):
                state["opening_intro_requested"] = True
                intro_request = "很好，我们正式开始。请先做一个1分钟左右的自我介绍，重点讲与你应聘岗位最相关的项目和技术栈。"
                self._append_interviewer_message(state, intro_request, InterviewStage.WELCOME)
                return state

            state["opening_intro_requested"] = True
            intro_request = "在进入正式提问前，请你先做一个简短自我介绍，突出与你应聘岗位最相关的经历。"
            self._append_interviewer_message(state, intro_request, InterviewStage.WELCOME)
            return state

        state["current_stage"] = InterviewStage.RESUME_DIG
        self._ask_resume_question(state)
        return state

    def _resume_dig_node(self, state: InterviewState) -> InterviewState:
        if self._should_jump_to_tech(state):
            state["current_stage"] = InterviewStage.TECH_QA
            state["rag_retrieved_knowledge"] = []
            self._ask_tech_question(state)
            return state

        if self._is_time_or_total_limit(state):
            state["current_stage"] = InterviewStage.CANDIDATE_QUESTION
            return self._candidate_question_node(state)

        self._ask_resume_question(state)
        return state

    def _tech_qa_node(self, state: InterviewState) -> InterviewState:
        if self._should_move_to_candidate_question(state):
            state["current_stage"] = InterviewStage.CANDIDATE_QUESTION
            return self._candidate_question_node(state)

        if self._is_time_or_total_limit(state):
            state["current_stage"] = InterviewStage.CANDIDATE_QUESTION
            return self._candidate_question_node(state)

        query = " ".join(
            x
            for x in [
                state.get("target_position", ""),
                state.get("job_description", ""),
                state.get("current_answer", ""),
            ]
            if x
        )

        try:
            db = self._runtime_db
            rag = []
            if db is not None:
                try:
                    asyncio.get_running_loop()
                    logger.warning("Skip RAG retrieval in sync fallback path due active event loop")
                except RuntimeError:
                    rag = asyncio.run(self.knowledge_service.hybrid_search(db, query=query[:500], top_k=3))
        except Exception:
            logger.exception("RAG retrieval failed, falling back to JD-only prompt")
            rag = []

        state["rag_retrieved_knowledge"] = rag
        self._ask_tech_question(state)
        return state

    def _candidate_question_node(self, state: InterviewState) -> InterviewState:
        answer = (state.get("current_answer") or "").strip()

        if not answer:
            invitation = "我的问题基本问完了，你有什么想问我的吗？"
            self._append_interviewer_message(state, invitation, InterviewStage.CANDIDATE_QUESTION)
            return state

        if self._is_no_more_question(answer) or state["candidate_question_rounds"] >= 2:
            state["current_stage"] = InterviewStage.END
            return self._end_node(state)

        state["candidate_question_rounds"] += 1
        reply = self._generate_candidate_question_response(state, answer)
        self._append_interviewer_message(state, reply, InterviewStage.CANDIDATE_QUESTION)
        return state

    def _end_node(self, state: InterviewState) -> InterviewState:
        state["status"] = "ENDED"
        if not state["message_history"] or state["message_history"][-1].get("stage") != InterviewStage.END.value:
            closing = "今天的模拟面试到这里，感谢你的认真作答。稍后我会给出完整复盘报告。"
            self._append_interviewer_message(state, closing, InterviewStage.END)
        return state

    def ensure_report(self, state: InterviewState) -> dict[str, Any]:
        if "report" in state and isinstance(state["report"], dict):
            return state["report"]
        state["report"] = self._generate_report(state)
        return state["report"]

    def _human_waiting_node(self, state: InterviewState) -> InterviewState:
        text = "当前面试已暂停，正在等待人工面试官接入。"
        self._append_interviewer_message(state, text, InterviewStage.HUMAN_INTERVENTION_WAITING)
        return state

    def _ask_resume_question(self, state: InterviewState) -> None:
        prompt = self.prompt_manager.render_with_fallback(
            "interview/resume_dig_question.md",
            """
{{ interviewer_role }}

你是{{ target_company }}的{{ target_position }}资深校招面试官，当前处于【简历深挖】阶段。
候选人简历：{{ parsed_resume_json }}
目标岗位JD：{{ job_description }}
当前简历深挖焦点：{{ current_resume_focus }}
历史对话：{{ history_json }}
当前已问简历深挖题数：{{ resume_dig_question_count }}
简历深挖题数上限：{{ max_resume_dig_questions }}

请生成1个精准的追问问题，要求：
1. 遵循STAR法则分层追问，不能重复；
2. 优先针对和JD最匹配的项目/经历/技能栈；
3. 对简历中的“精通/熟练掌握/项目亮点”进行深度追问；
4. 问题具体、有针对性；
5. 语气自然专业。

只返回问题文本。
""",
            interviewer_role=self._interviewer_role_prompt(),
            target_company=state["target_company"],
            target_position=state["target_position"],
            parsed_resume_json=json.dumps(state["parsed_resume"], ensure_ascii=False),
            job_description=state["job_description"],
            current_resume_focus=state.get("current_resume_focus") or "请你先选择最匹配JD的项目或经历",
            history_json=json.dumps(state["message_history"][-10:], ensure_ascii=False),
            resume_dig_question_count=state["resume_dig_question_count"],
            max_resume_dig_questions=state["max_resume_dig_questions"],
        )

        question = self._chat_with_optional_stream("INTERVIEW", prompt)
        state["current_stage"] = InterviewStage.RESUME_DIG
        state["resume_dig_question_count"] += 1
        state["current_question_index"] += 1
        self._append_interviewer_message(state, question, InterviewStage.RESUME_DIG)

    def _ask_tech_question(self, state: InterviewState) -> None:
        rag_points = state.get("rag_retrieved_knowledge") or []
        prompt = self.prompt_manager.render_with_fallback(
            "interview/tech_qa_question.md",
            """
{{ interviewer_role }}

你是{{ target_company }}的{{ target_position }}资深校招面试官，当前处于【技术问答】阶段。
目标岗位JD：{{ job_description }}
核心技能栈（从JD提取）：{{ tech_stack_focus_json }}
历史对话：{{ history_json }}
当前已问技术问答题数：{{ tech_qa_question_count }}
技术问答题数上限：{{ max_tech_qa_questions }}
当前难度趋势：{{ answer_quality_scores_json }}
RAG检索到的相关知识点：{{ rag_points_json }}

请生成1个精准的技术问题，要求：
1. 基于JD核心技能栈和检索知识点，不要超纲；
2. 难度递进并结合历史评分动态调整；
3. 优先场景题/设计题；
4. 若候选人上题有漏洞可追问。

只返回问题文本。
""",
            interviewer_role=self._interviewer_role_prompt(),
            target_company=state["target_company"],
            target_position=state["target_position"],
            job_description=state["job_description"],
            tech_stack_focus_json=json.dumps(state.get("current_tech_stack_focus") or [], ensure_ascii=False),
            history_json=json.dumps(state["message_history"][-12:], ensure_ascii=False),
            tech_qa_question_count=state["tech_qa_question_count"],
            max_tech_qa_questions=state["max_tech_qa_questions"],
            answer_quality_scores_json=json.dumps(state["answer_quality_scores"][-4:], ensure_ascii=False),
            rag_points_json=json.dumps(rag_points, ensure_ascii=False),
        )

        question = self._chat_with_optional_stream("INTERVIEW", prompt)
        state["current_stage"] = InterviewStage.TECH_QA
        state["tech_qa_question_count"] += 1
        state["current_question_index"] += 1
        self._append_interviewer_message(state, question, InterviewStage.TECH_QA)

    def _generate_welcome(self, state: InterviewState) -> str:
        prompt = self.prompt_manager.render_with_fallback(
            "interview/welcome.md",
            """
{{ interviewer_role }}

你是{{ target_company }}的{{ target_position }}资深校招面试官，现在开始一场模拟面试。
候选人简历：{{ parsed_resume_json }}
岗位JD：{{ job_description }}

请生成100字以内个性化开场：
1. 亲切自然；
2. 结合简历1个细节；
3. 简述流程（简历深挖→技术问答→候选人反问）；
4. 询问是否准备好。

只返回开场文本。
""",
            interviewer_role=self._interviewer_role_prompt(),
            target_company=state["target_company"],
            target_position=state["target_position"],
            parsed_resume_json=json.dumps(state["parsed_resume"], ensure_ascii=False),
            job_description=state["job_description"],
        )
        return self._chat_with_optional_stream("INTERVIEW", prompt)

    def _generate_candidate_question_response(self, state: InterviewState, candidate_input: str) -> str:
        prompt = self.prompt_manager.render_with_fallback(
            "interview/candidate_question_response.md",
            """
{{ interviewer_role }}

你是{{ target_company }}的{{ target_position }}资深校招面试官，当前处于【候选人反问】环节。
历史对话：{{ history_json }}
候选人问题：{{ candidate_input }}
岗位JD：{{ job_description }}

请给出专业、友好、真实的回答，不编造具体公司内部信息。回答后继续邀请候选人提问。
只返回文本。
""",
            interviewer_role=self._interviewer_role_prompt(),
            target_company=state["target_company"],
            target_position=state["target_position"],
            history_json=json.dumps(state["message_history"][-12:], ensure_ascii=False),
            candidate_input=candidate_input,
            job_description=state["job_description"],
        )
        return self._chat_with_optional_stream("INTERVIEW", prompt)

    def _chat_with_optional_stream(self, scenario: str, prompt: str) -> str:
        callback = self._token_callback
        get_provider = getattr(self.llm_service, "get_provider", None)
        if not callable(get_provider):
            return self.llm_service.chat(scenario, prompt)

        provider = get_provider(scenario)
        if callback is None:
            return provider.chat(prompt)

        chunks: list[str] = []
        try:
            for part in provider.chat_stream(prompt):
                if not part:
                    continue
                chunks.append(part)
                try:
                    callback(part)
                except Exception:
                    logger.exception("token callback failed")
        except Exception:
            logger.exception("stream generation failed, fallback to non-stream chat")
            return provider.chat(prompt)

        merged = "".join(chunks).strip()
        if merged:
            return merged
        return provider.chat(prompt)

    def _record_candidate_answer_if_needed(self, state: InterviewState) -> None:
        answer = (state.get("current_answer") or "").strip()
        if not answer:
            return

        if not state.get("message_history") or state["message_history"][-1].get("role") != "candidate":
            state["message_history"].append(
                {
                    "role": "candidate",
                    "content": answer,
                    "timestamp": self.now_iso(),
                    "stage": state["current_stage"].value,
                }
            )

        if state["current_stage"] not in {InterviewStage.RESUME_DIG, InterviewStage.TECH_QA}:
            return

        if not state.get("current_question"):
            return

        score = self._score_answer(answer, state["current_stage"]) 
        state["answer_quality_scores"].append(
            {
                "question_index": state["current_question_index"],
                "question": state["current_question"],
                "answer": answer,
                "score": score,
                "dimension": "项目经验" if state["current_stage"] == InterviewStage.RESUME_DIG else "专业知识",
                "comment": "回答较完整" if score >= 7 else "回答深度不足，建议补充原理和权衡",
            }
        )

    def _append_interviewer_message(self, state: InterviewState, text: str, stage: InterviewStage) -> None:
        clean = text.strip()
        state["current_question"] = clean
        state["current_answer"] = None
        state["message_history"].append(
            {
                "role": "interviewer",
                "content": clean,
                "timestamp": self.now_iso(),
                "stage": stage.value,
                "question_index": state["current_question_index"],
            }
        )

    @staticmethod
    def _extract_skills(job_description: str) -> list[str]:
        pool = [
            "Python",
            "FastAPI",
            "PostgreSQL",
            "Redis",
            "LangChain",
            "LangGraph",
            "Docker",
            "SQL",
            "算法",
            "系统设计",
        ]
        text = (job_description or "").lower()
        selected = [skill for skill in pool if skill.lower() in text]
        return selected or ["Python", "系统设计"]

    def _generate_report(self, state: InterviewState) -> dict[str, Any]:
        prompt = self.prompt_manager.render_with_fallback(
            "interview/report_generation.md",
            """
你是资深校招面试评委，请基于信息生成JSON复盘报告。
目标公司：{{ target_company }}
目标岗位：{{ target_position }}
面试时长：{{ interview_duration_seconds }}
总题数：{{ current_question_index }}
岗位JD：{{ job_description }}
候选人简历：{{ parsed_resume_json }}
完整对话历史：{{ message_history_json }}
回答评分：{{ answer_quality_scores_json }}

JSON字段必须满足 InterviewReport 模型。
只返回 JSON。
""",
            target_company=state["target_company"],
            target_position=state["target_position"],
            interview_duration_seconds=state["interview_duration_seconds"],
            current_question_index=state["current_question_index"],
            job_description=state["job_description"],
            parsed_resume_json=json.dumps(state["parsed_resume"], ensure_ascii=False),
            message_history_json=json.dumps(state["message_history"], ensure_ascii=False),
            answer_quality_scores_json=json.dumps(state["answer_quality_scores"], ensure_ascii=False),
        )

        try:
            raw = self.llm_service.chat("INTERVIEW", prompt)
        except Exception:
            logger.exception("Report generation LLM call failed, using fallback report")
            raw = ""
        try:
            parsed = json.loads(self._extract_json(raw))
            parsed.setdefault("generated_at", datetime.now(UTC).isoformat())
            report = InterviewReport(**parsed)
            return report.model_dump(mode="json")
        except Exception:
            logger.exception("Failed to parse report JSON, using fallback report")

        avg_score_10 = self._average_score(state)
        avg_score_100 = round(avg_score_10 * 10, 1)
        return InterviewReport(
            session_id=state["session_id"],
            user_id=state["user_id"],
            target_company=state.get("target_company") or "未指定",
            target_position=state.get("target_position") or "未指定",
            interview_duration_seconds=state["interview_duration_seconds"],
            total_questions=state["current_question_index"],
            overall_score=avg_score_100,
            professional_knowledge_score=avg_score_100,
            project_experience_score=avg_score_100,
            logical_thinking_score=max(0.0, avg_score_100 - 3),
            communication_score=min(100.0, avg_score_100 + 2),
            position_match_score=avg_score_100,
            highlights=[
                "回答结构较清晰，能够按问题逐步展开。",
                "对关键技术点有基本理解。",
                "沟通表达总体流畅。",
            ],
            weaknesses=[
                "部分问题缺少原理级解释。",
                "场景题中的取舍分析不够充分。",
            ],
            improvement_suggestions=[
                "针对JD核心技术栈做专题复盘，每个知识点补齐原理、优缺点和适用场景。",
                "对项目经历按STAR法整理，确保每段经历都能回答背景、任务、行动、结果。",
                "每周做2-3道系统设计场景题，训练容量估算与架构权衡表达。",
            ],
            recommended_knowledge_points=[
                {"id": "N/A", "title": "缓存策略与一致性", "link": ""},
                {"id": "N/A", "title": "数据库索引与查询优化", "link": ""},
            ],
            interview_summary="候选人在基础技术和沟通方面表现稳定，但在原理深度与场景化权衡上仍有提升空间。",
            generated_at=datetime.now(UTC),
        ).model_dump(mode="json")

    @staticmethod
    def _extract_json(text: str) -> str:
        text = text.strip()
        if text.startswith("{") and text.endswith("}"):
            return text
        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            raise ValueError("no json body found")
        return match.group(0)

    def _interviewer_role_prompt(self) -> str:
        return self.prompt_manager.render_with_fallback(
            "interviewer.txt",
            "你是结构化面试官。请按阶段提问：自我介绍、项目追问、算法基础、系统设计、总结反馈。",
        )

    @staticmethod
    def _score_answer(answer: str, stage: InterviewStage) -> float:
        length_score = min(6.0, len(answer) / 40)
        detail_bonus = 2.0 if any(k in answer.lower() for k in ["因为", "所以", "trade-off", "优化", "瓶颈"]) else 0.5
        stage_bonus = 1.5 if stage == InterviewStage.TECH_QA and any(k in answer.lower() for k in ["索引", "并发", "事务", "缓存"]) else 0.8
        return round(min(10.0, length_score + detail_bonus + stage_bonus), 1)

    @staticmethod
    def _average_score(state: InterviewState) -> float:
        scores = [float(item.get("score", 0)) for item in state.get("answer_quality_scores", [])]
        if not scores:
            return 6.0
        return round(sum(scores) / len(scores), 2)

    @staticmethod
    def _is_time_or_total_limit(state: InterviewState) -> bool:
        return (
            state["current_question_index"] >= state["max_total_questions"]
            or state["interview_duration_seconds"] >= state["max_interview_duration"]
        )

    @staticmethod
    def _should_jump_to_tech(state: InterviewState) -> bool:
        answer = (state.get("current_answer") or "").lower()
        if state["resume_dig_question_count"] >= state["max_resume_dig_questions"]:
            return True
        return any(k in answer for k in ["简历部分没问题", "进入技术", "继续技术", "下一部分"])

    def _should_move_to_candidate_question(self, state: InterviewState) -> bool:
        if state["tech_qa_question_count"] >= state["max_tech_qa_questions"]:
            return True
        if state["current_question_index"] >= state["max_total_questions"]:
            return True
        trend = [float(x.get("score", 0)) for x in state.get("answer_quality_scores", [])[-2:]]
        return len(trend) == 2 and all(x >= 8.5 for x in trend)

    @staticmethod
    def _is_end_signal(text: str | None) -> bool:
        if not text:
            return False
        lowered = text.lower()
        return any(x in lowered for x in ["结束面试", "退出", "stop interview", "结束吧"])

    @staticmethod
    def _is_no_more_question(text: str | None) -> bool:
        if not text:
            return False
        lowered = text.lower()
        return any(x in lowered for x in ["没有问题", "没问题了", "谢谢", "no question", "没有了"])

    @staticmethod
    def _is_ready_signal(text: str | None) -> bool:
        if not text:
            return False
        lowered = text.lower()
        return any(x in lowered for x in ["准备好了", "开始", "可以开始", "ready", "go", "开始吧"])

    @staticmethod
    def _looks_like_candidate_question(text: str) -> bool:
        if "?" in text or "？" in text:
            return True
        lowered = text.lower()
        triggers = ["薪资", "工作时间", "加班", "晋升", "福利", "年假", "面试流程"]
        return any(x in lowered for x in triggers)

    @staticmethod
    def _calculate_duration_seconds(state: InterviewState) -> int:
        try:
            start = datetime.fromisoformat(state["interview_start_time"])
        except Exception:
            return 0
        now = datetime.now(UTC)
        if start.tzinfo is None:
            start = start.replace(tzinfo=UTC)
        return int((now - start).total_seconds())
