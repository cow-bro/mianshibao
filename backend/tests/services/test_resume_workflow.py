from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.resume_service import ResumeService
from app.utils import file_parser


class DummyDB:
    def __init__(self) -> None:
        self.commit_count = 0

    async def commit(self) -> None:
        self.commit_count += 1


class DummyLLMFail:
    def chat(self, _scenario: str, _prompt: str) -> str:
        raise RuntimeError("provider timeout")


def _dummy_resume() -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        file_name="resume.pdf",
        file_url="resume-files/raw/1.pdf",
        parsed_content=None,
        overall_score=None,
        dimension_scores=None,
        suggestions=None,
    )


@pytest.mark.asyncio
async def test_parse_resume_stores_chinese_summary_payload(monkeypatch: pytest.MonkeyPatch):
    service = ResumeService()
    db = DummyDB()
    user = SimpleNamespace(id=7)
    resume = _dummy_resume()

    async def fake_get_user_resume(_db, _user_id: int, _resume_id: int):
        return resume

    def fake_extract_resume_text(_resume):
        parsed = {"suffix": ".pdf", "mode": "pdf"}
        text = "姓名: 张三\n教育经历\n某大学\n项目经历\n做了接口开发"
        return text, parsed

    monkeypatch.setattr(service, "_get_user_resume", fake_get_user_resume)
    monkeypatch.setattr(service, "_extract_resume_text", fake_extract_resume_text)

    payload = await service.parse_resume(db=db, user=user, resume_id=1)

    assert "文档信息" in payload
    assert "结构化摘要" in payload
    assert payload["文档信息"]["原始格式"] == ".pdf"
    assert payload["文档信息"]["解析模式"] == "pdf"
    assert "个人信息" in payload["结构化摘要"]
    assert db.commit_count == 1
    assert resume.parsed_content == payload


def test_score_inputs_raw_text_first_and_summary_assist(monkeypatch: pytest.MonkeyPatch):
    service = ResumeService()
    raw_text = "A" * (service.settings.resume_score_max_chars + 300)
    summary = {
        "个人信息": {"姓名": "张三", "邮箱": "a@test.com", "电话": "13812345678"},
        "教育经历": ["某大学 计算机"],
        "工作/实习经历": ["某公司 后端实习"],
        "项目经历": ["面试宝后端改造"],
        "技能关键词": ["Python", "FastAPI"],
    }
    resume = _dummy_resume()
    resume.parsed_content = {"结构化摘要": summary}

    monkeypatch.setattr(service, "_extract_resume_text", lambda _resume: (raw_text, {"mode": "pdf"}))

    main_text, summary_text = service._score_inputs(resume)

    assert len(main_text) == service.settings.resume_score_max_chars
    assert main_text == raw_text[: service.settings.resume_score_max_chars]
    assert "个人信息:" in summary_text
    assert "技能关键词:" in summary_text
    assert "张三" in summary_text


@pytest.mark.asyncio
async def test_score_resume_timeout_fallback_contract(monkeypatch: pytest.MonkeyPatch):
    service = ResumeService()
    service.llm_service = DummyLLMFail()
    db = DummyDB()
    user = SimpleNamespace(id=8)
    resume = _dummy_resume()

    async def fake_get_user_resume(_db, _user_id: int, _resume_id: int):
        return resume

    monkeypatch.setattr(service, "_get_user_resume", fake_get_user_resume)
    monkeypatch.setattr(service, "_extract_resume_text", lambda _resume: ("Python 后端项目经验", {"mode": "pdf"}))

    result = await service.score_resume(db=db, user=user, resume_id=1)

    assert isinstance(result.overall_score, float)
    assert set(result.dimension_scores.keys()) == set(service.SCORE_DIMENSIONS)
    assert result.suggestions
    assert db.commit_count == 1


def test_render_score_prompt_contains_main_and_summary():
    service = ResumeService()
    prompt = service._render_score_prompt("这是原文证据", "这是摘要定位")

    assert "这是原文证据" in prompt
    assert "这是摘要定位" in prompt
    assert "输入优先级" in prompt


def test_parse_score_from_plain_text_without_json():
    service = ResumeService()
    raw = (
        '{"overall_score": 82, "dimension_scores": {'
        '"教育背景与学习潜力": 82, "经历匹配度（实习 / 项目 / 校园）": 78, "经历含金量与成果价值": 75,'
        '"技能相关性": 88, "岗位适配性与发展潜力": 80, "信息完整性与支撑度": 72, "排版规范性与 ATS 适配性": 90},'
        '"suggestions": "1. 教育背景与学习潜力：补充排名证据"}'
    )

    result = service._parse_score_json(raw, resume_text="示例文本")
    assert result.overall_score == 82.0
    assert len(result.dimension_scores) == 7
    assert result.dimension_scores["技能相关性"] == 88.0
    assert "补充排名证据" in result.suggestions


def test_parse_score_json_requires_llm_suggestions():
    service = ResumeService()
    raw = '{"overall_score": 80, "dimension_scores": {"技能相关性": 88}}'

    with pytest.raises(ValueError):
        service._parse_score_json(raw, resume_text="示例文本")


def test_normalize_dimension_scores_missing_fields_default_zero():
    service = ResumeService()
    normalized = service._normalize_dimension_scores({"技能相关性": 85})

    assert normalized["技能相关性"] == 85.0
    assert normalized["教育背景与学习潜力"] == 0.0


def test_clean_suggestion_text_strips_fence():
    text = "```json\n{\"a\":1}\n```"
    cleaned = ResumeService._clean_suggestion_text(text)
    assert cleaned == '{"a":1}'


def test_parse_resume_file_docx_converts_to_pdf_then_extract(monkeypatch: pytest.MonkeyPatch):
    called: dict[str, object] = {}

    def fake_ensure_pdf_bytes(file_name: str, content: bytes):
        called["file_name"] = file_name
        called["content"] = content
        return b"%PDF-mock", "office-pdf"

    def fake_extract_pdf_text(pdf_bytes: bytes) -> str:
        called["pdf_bytes"] = pdf_bytes
        return "简历正文"

    monkeypatch.setattr(file_parser, "_ensure_pdf_bytes", fake_ensure_pdf_bytes)
    monkeypatch.setattr(file_parser, "_extract_pdf_text", fake_extract_pdf_text)

    result = file_parser.parse_resume_file("candidate.docx", b"docx-bytes")

    assert called["file_name"] == "candidate.docx"
    assert called["pdf_bytes"] == b"%PDF-mock"
    assert result["mode"] == "docx->office-pdf"
    assert result["text"] == "简历正文"


def test_normalize_resume_text_keeps_basic_structure():
    raw = "  教育经历\r\n\r\n\r\n• 2023-2024 研究项目  \n\u3000技能：Python；FastAPI  "
    normalized = file_parser._normalize_resume_text(raw)

    assert "教育经历" in normalized
    assert "- 2023-2024 研究项目" in normalized
    assert "技能:Python;FastAPI" in normalized or "技能: Python;FastAPI" in normalized
    assert "\n\n\n" not in normalized
