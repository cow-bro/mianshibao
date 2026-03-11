"""Schemas for the knowledge RAG module."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Ingestion ──────────────────────────────────────────────
class KnowledgeCardInput(BaseModel):
    subject: str = "Computer Science"
    category: str = "General"
    type: str = "KNOWLEDGE"
    difficulty: str = "MEDIUM"
    title: str
    content: str
    answer: str | None = None
    source_company: str | None = None
    tags: list[str] = Field(default_factory=list)


class IngestRequest(BaseModel):
    cards: list[KnowledgeCardInput]


class IngestResponse(BaseModel):
    ingested_count: int
    ids: list[int]


# ── Search ─────────────────────────────────────────────────
class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=20)


class KnowledgeSearchItem(BaseModel):
    id: int
    title: str
    content: str
    answer: str | None = None
    subject: str
    category: str
    difficulty: str
    tags: list[str] | None = None
    source_company: str | None = None
    rerank_score: float


class SearchResponse(BaseModel):
    results: list[KnowledgeSearchItem]


# ── Q&A ────────────────────────────────────────────────────
class AskRequest(BaseModel):
    question: str


class ReferenceItem(BaseModel):
    id: int
    title: str
    subject: str
    category: str


class AskResponse(BaseModel):
    answer: str
    references: list[ReferenceItem]


# ── Upload ─────────────────────────────────────────────────
class UploadResponse(BaseModel):
    ingested_count: int
    ids: list[int]
    source_file: str
