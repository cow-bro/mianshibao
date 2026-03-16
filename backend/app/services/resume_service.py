from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from langchain_core.output_parsers import PydanticOutputParser
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.models.resume import Resume
from app.models.user import User
from app.providers.llm_factory import LLMService
from app.providers.storage import download_bytes, upload_bytes
from app.schemas.resume import ResumeOptimizeResult, ResumeScoreResult, ResumeStructured
from app.utils.file_parser import convert_resume_to_preview_pdf, parse_resume_file
from app.utils.prompt_manager import PromptManager


class ResumeService:
    SCORE_DIMENSIONS: list[str] = [
        "教育背景与学习潜力",
        "经历匹配度（实习 / 项目 / 校园）",
        "经历含金量与成果价值",
        "技能相关性",
        "岗位适配性与发展潜力",
        "信息完整性与支撑度",
        "排版规范性与 ATS 适配性",
    ]
    SCORE_WEIGHTS: dict[str, float] = {
        "教育背景与学习潜力": 0.30,
        "经历匹配度（实习 / 项目 / 校园）": 0.20,
        "经历含金量与成果价值": 0.20,
        "技能相关性": 0.15,
        "岗位适配性与发展潜力": 0.10,
        "信息完整性与支撑度": 0.03,
        "排版规范性与 ATS 适配性": 0.02,
    }
    SCORE_ALIAS_MAP: dict[str, str] = {
        "教育背景": "教育背景与学习潜力",
        "学习潜力": "教育背景与学习潜力",
        "经历匹配度": "经历匹配度（实习 / 项目 / 校园）",
        "匹配度": "经历匹配度（实习 / 项目 / 校园）",
        "实习项目校园": "经历匹配度（实习 / 项目 / 校园）",
        "经历含金量": "经历含金量与成果价值",
        "成果价值": "经历含金量与成果价值",
        "技能": "技能相关性",
        "岗位适配性": "岗位适配性与发展潜力",
        "岗位适配": "岗位适配性与发展潜力",
        "发展潜力": "岗位适配性与发展潜力",
        "信息完整性": "信息完整性与支撑度",
        "完整性": "信息完整性与支撑度",
        "排版规范性": "排版规范性与 ATS 适配性",
        "ats适配性": "排版规范性与 ATS 适配性",
        "排版": "排版规范性与 ATS 适配性",
    }
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = LLMService()
        self.prompt_manager = PromptManager()

    async def upload_resume(self, db: AsyncSession, user: User, file: UploadFile) -> tuple[Resume, bool]:
        content = await file.read()
        if not content:
            raise AppException("empty file", code=2001)

        file_hash = hashlib.sha256(content).hexdigest()
        stmt = select(Resume).where(Resume.user_id == user.id, Resume.file_hash == file_hash)
        result = await db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing, False

        suffix = Path(file.filename or "resume.bin").suffix
        object_name = f"raw/{user.id}/{uuid.uuid4().hex}{suffix}"
        file_url = upload_bytes(
            bucket_name=self.settings.minio_resume_bucket,
            object_name=object_name,
            data=content,
            content_type=file.content_type or "application/octet-stream",
        )

        resume = Resume(
            user_id=user.id,
            file_url=file_url,
            file_name=file.filename or object_name,
            file_hash=file_hash,
            parsed_content=None,
            overall_score=None,
            dimension_scores=None,
            suggestions=None,
        )
        db.add(resume)
        await db.commit()
        await db.refresh(resume)
        return resume, True

    async def parse_resume(self, db: AsyncSession, user: User, resume_id: int) -> dict:
        resume = await self._get_user_resume(db, user.id, resume_id)
        raw_bytes = self._read_resume_bytes(resume.file_url)
        try:
            parsed = parse_resume_file(resume.file_name, raw_bytes)
        except Exception as exc:
            raise AppException("resume parse failed", code=2002) from exc
        text = parsed.get("text", "").strip()
        if not text:
            raise AppException("resume text extraction failed", code=2002)

        structured = self._extract_structured_with_dual_engine(text)
        resume.parsed_content = structured
        await db.commit()
        return structured

    async def score_resume(self, db: AsyncSession, user: User, resume_id: int) -> ResumeScoreResult:
        resume = await self._get_user_resume(db, user.id, resume_id)
        text = self._resume_text_for_score(resume)
        timeout_sec = max(30, int(self.settings.resume_score_timeout_seconds))
        reduced_text = text[: max(1600, int(self.settings.resume_score_max_chars * 0.55))]
        candidate_texts = [text, reduced_text]

        result: ResumeScoreResult | None = None
        for idx, candidate_text in enumerate(candidate_texts):
            current_timeout = timeout_sec if idx == 0 else max(timeout_sec, 120)
            prompt = self._render_score_prompt(candidate_text)
            try:
                raw = await asyncio.wait_for(
                    asyncio.to_thread(self.llm_service.chat, "RESUME_PARSING", prompt),
                    timeout=current_timeout,
                )
                result = self._parse_score_json(raw, resume_text=candidate_text)
                break
            except Exception:
                continue

        if result is None:
            # Return deterministic fallback only when both attempts failed.
            result = self._build_timeout_fallback_result(text)

        resume.overall_score = result.overall_score
        resume.dimension_scores = result.dimension_scores
        resume.suggestions = result.suggestions
        await db.commit()
        return result

    def _render_score_prompt(self, resume_text: str) -> str:
        return self.prompt_manager.render_with_fallback(
            "resume/score.md",
            (
                "你是资深HR，请根据以下简历内容，按7个维度打分（0-100）并给出可执行修改建议。\n"
                "请严格输出 JSON，禁止输出 JSON 以外内容。\n"
                "JSON 格式:\n"
                "{\"overall_score\": 0-100, \"dimension_scores\": {\"教育背景与学习潜力\": 0-100, \"经历匹配度（实习 / 项目 / 校园）\": 0-100, \"经历含金量与成果价值\": 0-100, \"技能相关性\": 0-100, \"岗位适配性与发展潜力\": 0-100, \"信息完整性与支撑度\": 0-100, \"排版规范性与 ATS 适配性\": 0-100}, \"suggestions\": \"1. 教育背景与学习潜力：...\\n2. 经历匹配度（实习 / 项目 / 校园）：...\\n3. 经历含金量与成果价值：...\\n4. 技能相关性：...\\n5. 岗位适配性与发展潜力：...\\n6. 信息完整性与支撑度：...\\n7. 排版规范性与 ATS 适配性：...\"}\n\n"
                "简历内容:\n{{ resume_text }}"
            ),
            resume_text=resume_text,
        )

    async def optimize_resume(self, db: AsyncSession, user: User, resume_id: int) -> ResumeOptimizeResult:
        resume = await self._get_user_resume(db, user.id, resume_id)
        text = self._resume_text_for_llm(resume)

        prompt = self.prompt_manager.render_with_fallback(
            "resume/optimize.md",
            (
                "你是资深HR，请使用 STAR 法则润色以下简历经历描述。"
                "要求：保留事实，不要虚构，突出结果与量化指标，输出优化后的完整文本。\n\n"
                "简历原文:\n{{ resume_text }}"
            ),
            resume_text=text,
        )
        optimized_content = self.llm_service.chat("RESUME_PARSING", prompt)

        object_name = f"optimized/{user.id}/{resume.id}_optimized.txt"
        optimized_url = upload_bytes(
            bucket_name=self.settings.minio_resume_bucket,
            object_name=object_name,
            data=optimized_content.encode("utf-8"),
            content_type="text/plain",
        )

        parsed = dict(resume.parsed_content or {})
        parsed["optimized_file_url"] = optimized_url
        parsed["optimized_content_preview"] = optimized_content[:500]
        resume.parsed_content = parsed
        await db.commit()

        return ResumeOptimizeResult(optimized_content=optimized_content, optimized_file_url=optimized_url)

    async def download_optimized_resume(self, db: AsyncSession, user: User, resume_id: int) -> tuple[bytes, str]:
        resume = await self._get_user_resume(db, user.id, resume_id)
        parsed = resume.parsed_content or {}
        optimized_file_url = parsed.get("optimized_file_url")
        if not optimized_file_url:
            raise AppException("optimized resume not found, run optimize first", code=2003)

        data = self._read_resume_bytes(optimized_file_url)
        filename = f"resume_{resume_id}_optimized.txt"
        return data, filename

    async def preview_resume_pdf(self, db: AsyncSession, user: User, resume_id: int) -> tuple[bytes, str]:
        resume = await self._get_user_resume(db, user.id, resume_id)
        raw_data = self._read_resume_bytes(resume.file_url)
        pdf_data = convert_resume_to_preview_pdf(resume.file_name, raw_data)
        preview_name = f"resume_{resume.id}_preview.pdf"
        return pdf_data, preview_name

    async def _get_user_resume(self, db: AsyncSession, user_id: int, resume_id: int) -> Resume:
        stmt = select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        result = await db.execute(stmt)
        resume = result.scalar_one_or_none()
        if resume is None:
            raise AppException("resume not found", code=2004)
        return resume

    def _read_resume_bytes(self, file_url: str) -> bytes:
        try:
            bucket_name, object_name = file_url.split("/", 1)
        except ValueError as exc:
            raise AppException("invalid file url", code=2005) from exc
        return download_bytes(bucket_name, object_name)

    def _extract_structured_with_dual_engine(self, text: str) -> dict:
        parser = PydanticOutputParser(pydantic_object=ResumeStructured)
        few_shot_examples = (
            "示例输入: 张三, zhangsan@example.com, 13812345678, 本科计算机\n"
            "示例输出: {\"personal_info\": {\"name\": \"张三\", \"email\": \"zhangsan@example.com\", \"phone\": \"13812345678\"},"
            " \"education_experiences\": [], \"work_experiences\": [], \"project_experiences\": [], \"skills\": []}"
        )
        formatted = self.prompt_manager.render_with_fallback(
            "resume/parse_structured.md",
            (
                "你是简历结构化专家。请将简历文本转为结构化 JSON。\n"
                "{{ few_shot_examples }}\n\n"
                "输出要求:\n{{ format_instructions }}\n\n"
                "简历文本:\n{{ resume_text }}"
            ),
            few_shot_examples=few_shot_examples,
            format_instructions=parser.get_format_instructions(),
            resume_text=text,
        )

        try:
            response = self.llm_service.chat("RESUME_PARSING", formatted)
            structured = parser.parse(response)
            return structured.model_dump()
        except Exception:
            # Rule-based fallback keeps minimal usable info.
            return self._rule_based_extract(text)

    def _rule_based_extract(self, text: str) -> dict:
        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        phone_match = re.search(r"(?:\+?86[-\s]?)?1[3-9]\d{9}", text)
        return ResumeStructured(
            personal_info={
                "name": None,
                "email": email_match.group(0) if email_match else None,
                "phone": phone_match.group(0) if phone_match else None,
                "summary": None,
            },
            education_experiences=[],
            work_experiences=[],
            project_experiences=[],
            skills=[],
        ).model_dump()

    def _resume_text_for_llm(self, resume: Resume) -> str:
        if resume.parsed_content:
            return json.dumps(resume.parsed_content, ensure_ascii=False)

        raw_bytes = self._read_resume_bytes(resume.file_url)
        parsed = parse_resume_file(resume.file_name, raw_bytes)
        return str(parsed.get("text", ""))

    def _resume_text_for_score(self, resume: Resume) -> str:
        parsed = dict(resume.parsed_content or {})
        if not parsed:
            raw_text = self._resume_text_for_llm(resume)
            return raw_text[: self.settings.resume_score_max_chars]

        compact = {
            "personal_info": parsed.get("personal_info", {}),
            "education_experiences": self._compact_items(parsed.get("education_experiences"), limit=3),
            "work_experiences": self._compact_items(parsed.get("work_experiences"), limit=3),
            "project_experiences": self._compact_items(parsed.get("project_experiences"), limit=3),
            "skills": self._compact_items(parsed.get("skills"), limit=25),
        }
        text = json.dumps(compact, ensure_ascii=False)
        return text[: self.settings.resume_score_max_chars]

    def _compact_items(self, value: object, limit: int) -> list | object:
        if isinstance(value, list):
            items = value[:limit]
            return [self._compact_items(item, limit=4) for item in items]
        if isinstance(value, dict):
            compact: dict[str, object] = {}
            for key, val in value.items():
                if key in {"optimized_file_url", "optimized_content_preview"}:
                    continue
                compact[key] = self._compact_items(val, limit=4)
            return compact
        if isinstance(value, str):
            return value[:280]
        return value

    def _parse_score_json(self, content: str, resume_text: str) -> ResumeScoreResult:
        try:
            payload = self._extract_json(content)
            normalized_scores = self._normalize_dimension_scores(payload.get("dimension_scores", {}))
            overall = self._weighted_overall(normalized_scores)
            llm_suggestions = str(payload.get("suggestions", "")).strip()
            suggestions = self._compose_rubric_suggestions(normalized_scores, llm_suggestions)
            return ResumeScoreResult(
                overall_score=overall,
                dimension_scores=normalized_scores,
                suggestions=suggestions,
            )
        except Exception:
            return self._build_timeout_fallback_result(resume_text)

    def _extract_json(self, content: str) -> dict:
        try:
            return json.loads(content)
        except Exception:
            pass

        match = re.search(r"\{[\s\S]*\}", content)
        if not match:
            raise ValueError("json not found")
        return json.loads(match.group(0))

    def _normalize_dimension_scores(self, scores: object) -> dict[str, float]:
        if not isinstance(scores, dict):
            scores = {}
        normalized: dict[str, float] = {name: 70.0 for name in self.SCORE_DIMENSIONS}
        for key, value in scores.items():
            key_text = str(key).strip()
            key_norm = self._normalize_label(key_text)
            target = key_text if key_text in normalized else self.SCORE_ALIAS_MAP.get(key_norm)
            if not target:
                for candidate in self.SCORE_DIMENSIONS:
                    if self._normalize_label(candidate) == key_norm:
                        target = candidate
                        break
            if target and target in normalized:
                try:
                    normalized[target] = round(max(0.0, min(100.0, float(value))), 1)
                except Exception:
                    continue
        return normalized

    def _weighted_overall(self, dimension_scores: dict[str, float]) -> float:
        total = 0.0
        for dim, weight in self.SCORE_WEIGHTS.items():
            total += float(dimension_scores.get(dim, 70.0)) * weight
        return round(total, 1)

    def _build_timeout_fallback_result(self, resume_text: str) -> ResumeScoreResult:
        base = min(85, max(58, int(58 + len(resume_text) / 350)))
        dimension_scores = {
            "教育背景与学习潜力": float(base),
            "经历匹配度（实习 / 项目 / 校园）": float(max(55, base - 2)),
            "经历含金量与成果价值": float(max(52, base - 4)),
            "技能相关性": float(max(55, base - 1)),
            "岗位适配性与发展潜力": float(max(54, base - 3)),
            "信息完整性与支撑度": float(min(92, base + 4)),
            "排版规范性与 ATS 适配性": float(min(90, base + 2)),
        }
        return ResumeScoreResult(
            overall_score=self._weighted_overall(dimension_scores),
            dimension_scores=dimension_scores,
            suggestions=self._compose_rubric_suggestions(dimension_scores, ""),
        )

    def _compose_rubric_suggestions(self, dimension_scores: dict[str, float], llm_suggestions: str) -> str:
        llm_map = self._extract_dimension_suggestion_map(llm_suggestions)
        lines: list[str] = []

        for idx, dim in enumerate(self.SCORE_DIMENSIONS, start=1):
            score_100 = float(dimension_scores.get(dim, 70.0))
            action = self._default_action_by_score(dim, score_100)
            llm_note = llm_map.get(dim, "").strip()
            if llm_note:
                llm_note = re.sub(rf"^\s*{re.escape(dim)}\s*[：:]\s*", "", llm_note)
                llm_note = llm_note[:220]
                action = llm_note

            lines.append(
                f"{idx}. {dim}：得分说明：{score_100:.1f}/100。"
                f"核心优势/扣分项：{self._score_brief(score_100)}。"
                f"优化建议：{action}"
            )

        return "\n".join(lines)

    @staticmethod
    def _normalize_label(text: str) -> str:
        return re.sub(r"[\s（）()/_-]+", "", text).lower()

    @staticmethod
    def _score_brief(score_100: float) -> str:
        if score_100 >= 85:
            return "当前维度表现较强，建议重点保留并补充更有竞争力的量化证据"
        if score_100 >= 70:
            return "当前维度达到可用水平，但存在关键说服力不足"
        if score_100 >= 60:
            return "当前维度偏弱，已影响整体竞争力"
        return "当前维度明显短板，建议优先整改"

    @staticmethod
    def _default_action_by_score(dim: str, score_100: float) -> str:
        if score_100 >= 85:
            return f"保留该维度强项表达，补充1-2个更高含金量的量化成果，并与目标岗位能力要求建立直接映射。"
        if score_100 >= 70:
            return f"围绕{dim}补齐证据链，至少增加1条可验证成果数据，并将描述改为STAR闭环。"
        if score_100 >= 60:
            return f"优先重写{dim}相关内容，删除空泛表述，补充时间、角色、动作、结果四要素。"
        return f"将{dim}作为最高优先级整改项，先补全事实信息，再增加强相关的实践与量化结果。"

    def _extract_dimension_suggestion_map(self, text: str) -> dict[str, str]:
        if not text:
            return {}

        points: list[tuple[int, str]] = []
        for dim in self.SCORE_DIMENSIONS:
            match = re.search(rf"{re.escape(dim)}\s*[：:]", text)
            if match:
                points.append((match.start(), dim))

        if not points:
            return {}

        points.sort(key=lambda item: item[0])
        result: dict[str, str] = {}
        for idx, (start, dim) in enumerate(points):
            end = points[idx + 1][0] if idx + 1 < len(points) else len(text)
            segment = text[start:end].strip()
            cleaned = re.sub(r"^\s*\d+[.、)）]\s*", "", segment)
            cleaned = re.sub(rf"^\s*{re.escape(dim)}\s*[：:]\s*", "", cleaned).strip()
            if cleaned:
                result[dim] = cleaned
        return result

