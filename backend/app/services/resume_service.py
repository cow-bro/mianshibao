from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.models.resume import Resume
from app.models.user import User
from app.providers.llm_factory import LLMService
from app.providers.storage import download_bytes, upload_bytes
from app.schemas.resume import ResumeOptimizeResult, ResumeScoreResult
from app.utils.file_parser import convert_resume_to_preview_pdf, parse_resume_file
from app.utils.prompt_manager import PromptManager


logger = logging.getLogger(__name__)


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
        text, parsed = self._extract_resume_text(resume)
        summary = self._build_structured_summary(text)

        parsed_payload = {
            "文档信息": {
                "文件名": resume.file_name,
                "原始格式": parsed.get("suffix", ""),
                "解析模式": parsed.get("mode", ""),
                "文本长度": len(text),
            },
            "结构化摘要": summary,
        }

        resume.parsed_content = parsed_payload
        await db.commit()
        return parsed_payload

    async def score_resume(self, db: AsyncSession, user: User, resume_id: int) -> ResumeScoreResult:
        resume = await self._get_user_resume(db, user.id, resume_id)
        text, summary_text = self._score_inputs(resume)
        timeout_sec = max(30, int(self.settings.resume_score_timeout_seconds))
        reduced_text = text[: max(1600, int(self.settings.resume_score_max_chars * 0.55))]
        minimal_text = text[: max(1100, int(self.settings.resume_score_max_chars * 0.35))]
        candidate_texts = [text, reduced_text, minimal_text]

        result: ResumeScoreResult | None = None
        last_error: Exception | None = None
        for idx, candidate_text in enumerate(candidate_texts):
            current_timeout = timeout_sec if idx == 0 else max(timeout_sec, 120)
            if idx < 2:
                prompt = self._render_score_prompt(candidate_text, summary_text)
            else:
                prompt = self._render_score_prompt_minimal(candidate_text)
            try:
                raw = await asyncio.wait_for(
                    asyncio.to_thread(self.llm_service.chat, "RESUME_PARSING", prompt),
                    timeout=current_timeout,
                )
                result = self._parse_score_json(raw, resume_text=candidate_text)
                break
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "resume score attempt failed: attempt=%s timeout=%s err=%s",
                    idx + 1,
                    current_timeout,
                    repr(exc),
                )
                continue

        if result is None:
            # Return deterministic fallback only when both attempts failed.
            if last_error is not None:
                logger.error("resume score fallback triggered after retries: %s", str(last_error))
            result = self._build_timeout_fallback_result(text)

        resume.overall_score = result.overall_score
        resume.dimension_scores = result.dimension_scores
        resume.suggestions = result.suggestions
        await db.commit()
        return result

    def _render_score_prompt(self, resume_text: str, resume_summary: str) -> str:
        return self.prompt_manager.render_with_fallback(
            "resume/score.md",
            (
                "你是资深HR，请根据以下简历内容，按7个维度打分（0-100）并给出可执行修改建议。\n"
                "输入优先级：先使用简历原文证据，再参考结构化摘要定位信息，不得用摘要覆盖原文事实。\n"
                "请严格输出 JSON，禁止输出 JSON 以外内容。\n"
                "JSON 格式:\n"
                "{\"overall_score\": 0-100, \"dimension_scores\": {\"教育背景与学习潜力\": 0-100, \"经历匹配度（实习 / 项目 / 校园）\": 0-100, \"经历含金量与成果价值\": 0-100, \"技能相关性\": 0-100, \"岗位适配性与发展潜力\": 0-100, \"信息完整性与支撑度\": 0-100, \"排版规范性与 ATS 适配性\": 0-100}, \"suggestions\": \"1. 教育背景与学习潜力：...\\n2. 经历匹配度（实习 / 项目 / 校园）：...\\n3. 经历含金量与成果价值：...\\n4. 技能相关性：...\\n5. 岗位适配性与发展潜力：...\\n6. 信息完整性与支撑度：...\\n7. 排版规范性与 ATS 适配性：...\"}\n\n"
                "简历原文:\n{{ resume_text }}\n\n"
                "结构化摘要（仅用于定位，不可覆盖原文）:\n{{ resume_summary }}"
            ),
            resume_text=resume_text,
            resume_summary=resume_summary,
        )

    def _render_score_prompt_minimal(self, resume_text: str) -> str:
        return (
            "你是资深HR，请仅输出JSON，不要解释。"
            "按7个维度给0-100分并给可执行建议。"
            "JSON格式："
            "{\"overall_score\":number,\"dimension_scores\":{\"教育背景与学习潜力\":number,\"经历匹配度（实习 / 项目 / 校园）\":number,\"经历含金量与成果价值\":number,\"技能相关性\":number,\"岗位适配性与发展潜力\":number,\"信息完整性与支撑度\":number,\"排版规范性与 ATS 适配性\":number},\"suggestions\":\"...\"}"
            f"\n简历原文:\n{resume_text}"
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

    def _extract_resume_text(self, resume: Resume) -> tuple[str, dict]:
        raw_bytes = self._read_resume_bytes(resume.file_url)
        try:
            parsed = parse_resume_file(resume.file_name, raw_bytes)
        except Exception as exc:
            raise AppException("resume parse failed", code=2002) from exc

        text = str(parsed.get("text", "")).strip()
        if not text:
            raise AppException("resume text extraction failed", code=2002)
        return text, parsed

    def _resume_text_for_llm(self, resume: Resume) -> str:
        text, _ = self._extract_resume_text(resume)
        return text

    def _score_inputs(self, resume: Resume) -> tuple[str, str]:
        text, _ = self._extract_resume_text(resume)
        main_text = text[: self.settings.resume_score_max_chars]

        parsed = dict(resume.parsed_content or {})
        summary = parsed.get("结构化摘要") if isinstance(parsed, dict) else None
        if not isinstance(summary, dict):
            summary = self._build_structured_summary(text)
        summary_text = self._summary_to_text(summary)
        return main_text, summary_text

    def _build_structured_summary(self, text: str) -> dict:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        compact_lines = lines[:120]

        email_match = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)
        phone_match = re.search(r"(?:\+?86[-\s]?)?1[3-9]\d{9}", text)
        name_match = re.search(r"(?m)^(?:姓名[:：]\s*)?([\u4e00-\u9fa5]{2,4})\b", text)

        sections = self._split_sections(compact_lines)
        skills = self._extract_skills(text)

        return {
            "个人信息": {
                "姓名": name_match.group(1) if name_match else None,
                "邮箱": email_match.group(0) if email_match else None,
                "电话": phone_match.group(0) if phone_match else None,
            },
            "教育经历": sections.get("教育经历", [])[:4],
            "工作/实习经历": sections.get("工作/实习经历", [])[:5],
            "项目经历": sections.get("项目经历", [])[:6],
            "技能关键词": skills[:20],
        }

    def _split_sections(self, lines: list[str]) -> dict[str, list[str]]:
        buckets: dict[str, list[str]] = {
            "教育经历": [],
            "工作/实习经历": [],
            "项目经历": [],
        }
        current = "项目经历"

        for line in lines:
            lower = line.lower()
            if any(k in line for k in ["教育", "学历", "学校", "院校"]):
                current = "教育经历"
                continue
            if any(k in line for k in ["实习", "工作", "任职", "公司", "经历"]):
                current = "工作/实习经历"
                continue
            if any(k in line for k in ["项目", "课题", "系统", "平台", "作品"]):
                current = "项目经历"
                continue

            if len(line) <= 1:
                continue
            if re.fullmatch(r"[-_—=]+", line):
                continue
            if "http" in lower and len(line) > 90:
                continue

            buckets[current].append(line)

        return buckets

    def _extract_skills(self, text: str) -> list[str]:
        candidates = re.split(r"[\n,，;；、/| ]+", text)
        allow = re.compile(r"^[A-Za-z0-9+#._-]{2,24}$")
        seen: set[str] = set()
        result: list[str] = []
        for token in candidates:
            skill = token.strip()
            if not skill:
                continue
            if not allow.fullmatch(skill):
                continue
            low = skill.lower()
            if low in seen:
                continue
            seen.add(low)
            result.append(skill)
        return result

    def _summary_to_text(self, summary: dict) -> str:
        if not summary:
            return "无结构化摘要"

        parts: list[str] = []
        personal = summary.get("个人信息", {}) if isinstance(summary, dict) else {}
        if isinstance(personal, dict):
            kv = [f"{k}:{v}" for k, v in personal.items() if v]
            if kv:
                parts.append("个人信息: " + " | ".join(kv))

        for key in ["教育经历", "工作/实习经历", "项目经历"]:
            values = summary.get(key, []) if isinstance(summary, dict) else []
            if isinstance(values, list) and values:
                parts.append(f"{key}: " + " || ".join(str(v) for v in values[:4]))

        skills = summary.get("技能关键词", []) if isinstance(summary, dict) else []
        if isinstance(skills, list) and skills:
            parts.append("技能关键词: " + ", ".join(str(v) for v in skills[:15]))

        return "\n".join(parts) if parts else "无结构化摘要"

    def _parse_score_json(self, content: str, resume_text: str) -> ResumeScoreResult:
        payload = self._extract_json(content)
        normalized_scores = self._normalize_dimension_scores(payload.get("dimension_scores", {}))

        overall_raw = payload.get("overall_score")
        if overall_raw is None:
            overall = self._weighted_overall(normalized_scores)
        else:
            overall = round(max(0.0, min(100.0, float(overall_raw))), 1)

        suggestions = str(payload.get("suggestions", "")).strip()
        if not suggestions:
            raise ValueError("llm suggestions missing in score payload")

        return ResumeScoreResult(
            overall_score=overall,
            dimension_scores=normalized_scores,
            suggestions=suggestions,
        )

    @staticmethod
    def _clean_suggestion_text(content: str) -> str:
        text = content.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
        return text.strip()

    def _extract_json(self, content: str) -> dict:
        cleaned = self._sanitize_json_text(content)
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        match = re.search(r"\{[\s\S]*\}", cleaned)
        if not match:
            raise ValueError("json not found")
        body = self._sanitize_json_text(match.group(0))
        return json.loads(body)

    @staticmethod
    def _sanitize_json_text(content: str) -> str:
        # Remove illegal control chars that frequently appear in OCR/model outputs.
        # Keep CR/LF/TAB for readability and parser compatibility.
        return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", content)

    def _normalize_dimension_scores(self, scores: object) -> dict[str, float]:
        if not isinstance(scores, dict):
            scores = {}
        # Keep missing dimensions as 0 to avoid injecting non-LLM defaults.
        normalized: dict[str, float] = {name: 0.0 for name in self.SCORE_DIMENSIONS}
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
            suggestions="评分服务当前不可用，请稍后重试。",
        )

    @staticmethod
    def _normalize_label(text: str) -> str:
        return re.sub(r"[\s（）()/_-]+", "", text).lower()


