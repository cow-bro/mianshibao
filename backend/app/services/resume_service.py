from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

from fastapi import UploadFile
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import PromptTemplate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import AppException
from app.models.resume import Resume
from app.models.user import User
from app.providers.llm_factory import LLMService
from app.providers.storage import download_bytes, upload_bytes
from app.schemas.resume import ResumeOptimizeResult, ResumeScoreResult, ResumeStructured
from app.utils.file_parser import parse_resume_file


class ResumeService:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.llm_service = LLMService()

    async def upload_resume(self, db: AsyncSession, user: User, file: UploadFile) -> Resume:
        content = await file.read()
        if not content:
            raise AppException("empty file", code=2001)

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
            parsed_content=None,
            overall_score=None,
            dimension_scores=None,
            suggestions=None,
        )
        db.add(resume)
        await db.commit()
        await db.refresh(resume)
        return resume

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
        text = self._resume_text_for_llm(resume)

        prompt = (
            "你是资深HR，请根据以下简历内容，从完整性、经历匹配度、技能相关性、排版规范性四个维度打分（0-100），"
            "并给出具体的修改建议。\n"
            "请严格输出 JSON，格式如下:\n"
            "{\"overall_score\": 0-100, \"dimension_scores\": {\"完整性\": 0-100, \"经历匹配度\": 0-100, \"技能相关性\": 0-100, \"排版规范性\": 0-100}, \"suggestions\": \"...\"}\n\n"
            f"简历内容:\n{text}"
        )
        raw = self.llm_service.chat("RESUME_PARSING", prompt)
        result = self._parse_score_json(raw)

        resume.overall_score = result.overall_score
        resume.dimension_scores = result.dimension_scores
        resume.suggestions = result.suggestions
        await db.commit()
        return result

    async def optimize_resume(self, db: AsyncSession, user: User, resume_id: int) -> ResumeOptimizeResult:
        resume = await self._get_user_resume(db, user.id, resume_id)
        text = self._resume_text_for_llm(resume)

        prompt = (
            "你是资深HR，请使用 STAR 法则润色以下简历经历描述。"
            "要求：保留事实，不要虚构，突出结果与量化指标，输出优化后的完整文本。\n\n"
            f"简历原文:\n{text}"
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
        prompt = PromptTemplate.from_template(
            "你是简历结构化专家。请将简历文本转为结构化 JSON。\n"
            "{few_shot_examples}\n\n"
            "输出要求:\n{format_instructions}\n\n"
            "简历文本:\n{text}"
        )
        formatted = prompt.format(
            few_shot_examples=few_shot_examples,
            format_instructions=parser.get_format_instructions(),
            text=text,
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

    def _parse_score_json(self, content: str) -> ResumeScoreResult:
        try:
            payload = json.loads(content)
            return ResumeScoreResult(**payload)
        except Exception:
            # Fallback if model does not return JSON.
            return ResumeScoreResult(
                overall_score=70.0,
                dimension_scores={
                    "完整性": 70.0,
                    "经历匹配度": 70.0,
                    "技能相关性": 70.0,
                    "排版规范性": 70.0,
                },
                suggestions=content[:1000],
            )
