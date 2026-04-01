import pytest
from uuid import uuid4

from app.schemas.interview import InterviewStage
from app.services.interview_graph import InterviewGraphService


class DummyLLM:
    def chat(self, _scenario: str, prompt: str) -> str:
        if "开场" in prompt:
            return "你好，欢迎参加模拟面试。流程是简历深挖、技术问答和反问环节，你准备好了吗？"
        if "简历深挖" in prompt:
            return "你在最近项目中负责了哪些核心模块？请结合一个难点详细说明。"
        if "技术问答" in prompt:
            return "请你设计一个高并发面试系统，重点说明缓存与数据库的权衡。"
        if "候选人反问" in prompt:
            return "这个岗位会有导师机制和季度评估，你还有其他问题吗？"
        if "JSON复盘报告" in prompt:
            return "{}"
        return "好的。"


class DummyKnowledgeService:
    async def hybrid_search(self, db, query: str, top_k: int = 3):
        return [{"id": 1, "title": "缓存一致性", "content": "...", "subject": "CS", "category": "Backend"}]


@pytest.mark.asyncio
async def test_welcome_turn_generates_opening_message():
    svc = InterviewGraphService()
    svc.llm_service = DummyLLM()
    svc.knowledge_service = DummyKnowledgeService()

    state = svc.init_state(
        session_id=100000 + (uuid4().int % 100000),
        user_id=1,
        resume_id=1,
        target_company="测试公司",
        target_position="后端开发",
        job_description="Python FastAPI PostgreSQL",
        parsed_resume={"skills": ["Python"]},
        max_total_questions=12,
        max_resume_dig_questions=4,
        max_tech_qa_questions=6,
        max_interview_duration=3600,
    )

    new_state = await svc.run_turn(state, db=None)
    assert new_state["status"] == "ONGOING"
    assert new_state["current_stage"] == InterviewStage.WELCOME
    assert new_state["message_history"][-1]["role"] == "interviewer"


@pytest.mark.asyncio
async def test_ready_message_moves_to_resume_dig():
    svc = InterviewGraphService()
    svc.llm_service = DummyLLM()
    svc.knowledge_service = DummyKnowledgeService()

    state = svc.init_state(
        session_id=200000 + (uuid4().int % 100000),
        user_id=1,
        resume_id=1,
        target_company="测试公司",
        target_position="后端开发",
        job_description="Python FastAPI PostgreSQL",
        parsed_resume={"skills": ["Python"]},
        max_total_questions=12,
        max_resume_dig_questions=4,
        max_tech_qa_questions=6,
        max_interview_duration=3600,
    )
    state = await svc.run_turn(state, db=None)

    state["current_answer"] = "准备好了"
    state = await svc.run_turn(state, db=None)

    assert state["current_stage"] == InterviewStage.WELCOME
    assert "自我介绍" in state["message_history"][-1]["content"]

    state["current_answer"] = "我是后端工程师，主要负责FastAPI和数据库优化。"
    state = await svc.run_turn(state, db=None)

    assert state["current_stage"] == InterviewStage.RESUME_DIG
    assert state["resume_dig_question_count"] == 1
    assert state["current_question_index"] == 1


@pytest.mark.asyncio
async def test_resume_limit_jumps_to_tech_qa():
    svc = InterviewGraphService()
    svc.llm_service = DummyLLM()
    svc.knowledge_service = DummyKnowledgeService()

    state = svc.init_state(
        session_id=300000 + (uuid4().int % 100000),
        user_id=1,
        resume_id=1,
        target_company="测试公司",
        target_position="后端开发",
        job_description="Python FastAPI PostgreSQL",
        parsed_resume={"skills": ["Python"]},
        max_total_questions=12,
        max_resume_dig_questions=1,
        max_tech_qa_questions=6,
        max_interview_duration=3600,
    )

    state = await svc.run_turn(state, db=None)
    state["current_answer"] = "准备好了"
    state = await svc.run_turn(state, db=None)
    state["current_answer"] = "我主要做接口开发和性能优化。"
    state = await svc.run_turn(state, db=None)

    state["current_answer"] = "我主要负责接口开发"
    state = await svc.run_turn(state, db=None)

    assert state["current_stage"] == InterviewStage.TECH_QA
    assert state["tech_qa_question_count"] >= 1
