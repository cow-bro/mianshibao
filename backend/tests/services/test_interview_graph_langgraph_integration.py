import pytest
from uuid import uuid4

from app.schemas.interview import InterviewStage
from app.services.interview_graph import InterviewGraphService


class DummyLLM:
    def chat(self, _scenario: str, prompt: str) -> str:
        if "开场" in prompt:
            return "你好，欢迎来到模拟面试，流程是简历深挖、技术问答和反问环节，你准备好了吗？"
        if "简历深挖" in prompt:
            return "你在项目里是如何定位并解决性能瓶颈的？请给出具体指标。"
        if "技术问答" in prompt:
            return "如果系统并发上涨10倍，你会如何设计缓存与数据库的限流降级策略？"
        if "候选人反问" in prompt:
            return "这个岗位强调工程质量和稳定性，你还有其他想了解的吗？"
        if "JSON复盘报告" in prompt:
            return "{}"
        return "好的。"


class DummyKnowledgeService:
    async def hybrid_search(self, db, query: str, top_k: int = 3):
        return [
            {
                "id": 101,
                "title": "缓存一致性",
                "content": "延迟双删与失效策略",
                "subject": "Backend",
                "category": "Architecture",
            }
        ]


def _make_service() -> InterviewGraphService:
    svc = InterviewGraphService()
    svc.llm_service = DummyLLM()
    svc.knowledge_service = DummyKnowledgeService()
    return svc


def _init_state(svc: InterviewGraphService, session_id: int):
    return svc.init_state(
        session_id=session_id,
        user_id=1,
        resume_id=1,
        target_company="测试公司",
        target_position="后端开发",
        job_description="Python FastAPI PostgreSQL Redis",
        parsed_resume={"projects": [{"name": "面试系统", "stack": ["FastAPI", "PostgreSQL"]}]},
        max_total_questions=6,
        max_resume_dig_questions=1,
        max_tech_qa_questions=1,
        max_interview_duration=3600,
    )


@pytest.mark.asyncio
async def test_langgraph_full_stage_chain():
    svc = _make_service()

    session_id = 900000 + (uuid4().int % 100000)
    state = _init_state(svc, session_id=session_id)

    state = await svc.run_turn(state, db=None)
    assert state["current_stage"] == InterviewStage.WELCOME

    state["current_answer"] = "准备好了"
    state = await svc.run_turn(state, db=None)
    assert state["current_stage"] == InterviewStage.WELCOME

    state["current_answer"] = "我是后端方向候选人，重点做过高并发系统优化。"
    state = await svc.run_turn(state, db=None)
    assert state["current_stage"] == InterviewStage.RESUME_DIG

    state["current_answer"] = "我负责接口和缓存优化。"
    state = await svc.run_turn(state, db=None)
    assert state["current_stage"] == InterviewStage.TECH_QA

    state["current_answer"] = "我会做分层缓存和数据库读写隔离。"
    state = await svc.run_turn(state, db=None)
    assert state["current_stage"] == InterviewStage.CANDIDATE_QUESTION

    state["current_answer"] = "没有问题了，谢谢"
    state = await svc.run_turn(state, db=None)
    assert state["current_stage"] == InterviewStage.END
    assert state["status"] == "ENDED"
    report = svc.ensure_report(state)
    assert isinstance(report, dict)


@pytest.mark.asyncio
async def test_langgraph_checkpoint_restore_roundtrip():
    writer = _make_service()
    session_id = 910000 + (uuid4().int % 100000)
    state = _init_state(writer, session_id=session_id)

    state = await writer.run_turn(state, db=None)
    state["current_answer"] = "准备好了"
    state = await writer.run_turn(state, db=None)
    state["current_answer"] = "我是后端候选人，做过缓存和数据库优化。"
    state = await writer.run_turn(state, db=None)
    state["current_answer"] = "我负责接口和缓存优化。"
    state = await writer.run_turn(state, db=None)

    reader = _make_service()
    restored = reader.load_state_from_checkpoint(session_id)

    if restored is None:
        pytest.skip("checkpoint backend unavailable in current environment")

    assert restored["session_id"] == str(session_id)
    assert restored["current_stage"] in {InterviewStage.TECH_QA, InterviewStage.CANDIDATE_QUESTION}
    assert len(restored.get("message_history", [])) >= 2