"""Schemas for the knowledge RAG module."""

from __future__ import annotations

from datetime import datetime

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
    scope: str | None = None
    visibility: str = "BOTH"


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


# ── Category / Learning ──────────────────────────────────
class KnowledgeCategoryTreeItem(BaseModel):
    id: int
    name: str
    code: str
    parent_id: int | None = None
    subject: str
    sort_order: int
    point_count: int = 0
    read_count: int = 0
    children: list["KnowledgeCategoryTreeItem"] = Field(default_factory=list)


class CategoryTreeResponse(BaseModel):
    subject: str
    categories: list[KnowledgeCategoryTreeItem]


class KnowledgePointListItem(BaseModel):
    id: int
    title: str
    subject: str
    category: str
    difficulty: str
    is_bookmarked: bool = False
    learning_status: str = "UNREAD"
    is_owned_by_me: bool = False


class PointsListResponse(BaseModel):
    points: list[KnowledgePointListItem]


class KnowledgePointDetailResponse(BaseModel):
    id: int
    title: str
    subject: str
    category: str
    content: str
    answer: str | None = None
    difficulty: str
    tags: list[str] = Field(default_factory=list)
    is_bookmarked: bool = False
    learning_status: str = "UNREAD"
    is_owned_by_me: bool = False
    related_point_ids: list[int] = Field(default_factory=list)


class BookmarkCreateRequest(BaseModel):
    knowledge_point_id: int


class BookmarkItem(BaseModel):
    bookmark_id: int
    knowledge_point_id: int
    title: str
    subject: str
    category: str
    created_at: datetime


class BookmarkListResponse(BaseModel):
    items: list[BookmarkItem]


class LearningProgressUpdateRequest(BaseModel):
    knowledge_point_id: int
    status: str = Field(description="UNREAD | READING | MASTERED")
    read_duration_seconds: float = 0


class LearningProgressResponse(BaseModel):
    knowledge_point_id: int
    status: str
    read_duration_seconds: float
    last_read_at: datetime | None = None


class PersonalUploadResponse(BaseModel):
    ingested_count: int
    ids: list[int]
    source_file: str
    visibility: str
