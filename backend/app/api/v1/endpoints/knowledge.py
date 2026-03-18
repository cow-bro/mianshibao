"""Knowledge RAG endpoints: ingest, search, ask, upload."""

from fastapi import APIRouter, Depends, Form, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.core.exceptions import AppException
from app.core.response import success_response
from app.models.user import User
from app.schemas.knowledge import (
    AskRequest,
    BookmarkCreateRequest,
    IngestRequest,
    LearningProgressUpdateRequest,
    SearchRequest,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter()

_service = KnowledgeService()

_ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".markdown"}
_MAX_UPLOAD_SIZE = 20 * 1024 * 1024  # 20 MB


@router.post("/ingest")
async def ingest_knowledge(
    request: IngestRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """Ingest knowledge cards (JSON / Markdown) into the vector store."""
    cards = [card.model_dump() for card in request.cards]
    ids = await _service.ingest_cards(db, cards)
    return success_response(data={"ingested_count": len(ids), "ids": ids})


@router.post("/search")
async def search_knowledge(
    request: SearchRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """Hybrid search (vector + keyword) with reranking."""
    results = await _service.hybrid_search(
        db,
        request.query,
        request.top_k,
        scope=request.scope,
        visibility=request.visibility,
        user_id=_.id,
    )
    # Expose only fields that match the schema
    clean = [
        {
            "id": r["id"],
            "title": r["title"],
            "content": r["content"],
            "answer": r.get("answer"),
            "subject": r["subject"],
            "category": r["category"],
            "difficulty": r["difficulty"],
            "tags": r.get("tags"),
            "source_company": r.get("source_company"),
            "rerank_score": r.get("rerank_score", 0.0),
        }
        for r in results
    ]
    return success_response(data={"results": clean})


@router.get("/categories/tree")
async def category_tree(
    subject: str = Query(...),
    position_id: int | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    categories = await _service.list_categories_tree(
        db,
        subject=subject,
        user_id=current_user.id,
        position_id=position_id,
    )
    return success_response(data={"subject": subject, "categories": categories})


@router.get("/points")
async def list_points(
    category_id: int | None = Query(default=None),
    position_id: int | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    subject: str | None = Query(default=None),
    include_private: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    points = await _service.list_points(
        db,
        user_id=current_user.id,
        category_id=category_id,
        position_id=position_id,
        difficulty=difficulty,
        subject=subject,
        include_private=include_private,
    )
    return success_response(data={"points": points})


@router.get("/points/{point_id}")
async def point_detail(
    point_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    detail = await _service.get_point_detail(db, user_id=current_user.id, point_id=point_id)
    return success_response(data=detail)


@router.post("/bookmarks")
async def create_bookmark(
    request: BookmarkCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _service.create_bookmark(db, user_id=current_user.id, point_id=request.knowledge_point_id)
    return success_response(data={"ok": True})


@router.get("/bookmarks/my")
async def my_bookmarks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    items = await _service.list_my_bookmarks(db, user_id=current_user.id)
    return success_response(data={"items": items})


@router.delete("/bookmarks/{knowledge_point_id}")
async def delete_bookmark(
    knowledge_point_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    await _service.remove_bookmark(db, user_id=current_user.id, point_id=knowledge_point_id)
    return success_response(data={"ok": True})


@router.put("/progress")
async def update_learning_progress(
    request: LearningProgressUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    progress = await _service.upsert_learning_progress(
        db,
        user_id=current_user.id,
        point_id=request.knowledge_point_id,
        status=request.status,
        read_duration_seconds=request.read_duration_seconds,
    )
    return success_response(data=progress)


@router.post("/ask")
async def ask_knowledge(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """RAG Q&A: retrieve context and generate a grounded answer."""
    result = await _service.ask_knowledge_base(db, request.question)
    return success_response(data=result)


@router.post("/upload")
async def upload_knowledge_document(
    file: UploadFile,
    subject: str = Form("Computer Science"),
    category: str = Form("General"),
    difficulty: str = Form("MEDIUM"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """Upload a PDF/TXT/MD document — auto-chunk, embed, and store."""
    filename = file.filename or "document.txt"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{suffix}" not in _ALLOWED_EXTENSIONS:
        raise AppException(
            f"unsupported file type .{suffix}, allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
            code=3005,
        )

    content = await file.read()
    if not content:
        raise AppException("empty file", code=3005)
    if len(content) > _MAX_UPLOAD_SIZE:
        raise AppException("file exceeds 20 MB limit", code=3005)

    ids = await _service.ingest_document(
        db, filename, content, subject, category, difficulty
    )
    return success_response(
        data={"ingested_count": len(ids), "ids": ids, "source_file": filename}
    )


@router.post("/library/upload")
async def upload_personal_learning_document(
    file: UploadFile,
    subject: str = Form("Computer Science"),
    category: str = Form("Personal"),
    difficulty: str = Form("MEDIUM"),
    category_id: int | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Upload personal learning docs into user's private knowledge library."""
    filename = file.filename or "document.txt"
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if f".{suffix}" not in _ALLOWED_EXTENSIONS:
        raise AppException(
            f"unsupported file type .{suffix}, allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
            code=3005,
        )

    content = await file.read()
    if not content:
        raise AppException("empty file", code=3005)
    if len(content) > _MAX_UPLOAD_SIZE:
        raise AppException("file exceeds 20 MB limit", code=3005)

    ids = await _service.ingest_document(
        db,
        filename,
        content,
        subject,
        category,
        difficulty,
        owner_user_id=current_user.id,
        category_id=category_id,
    )
    return success_response(
        data={
            "ingested_count": len(ids),
            "ids": ids,
            "source_file": filename,
            "visibility": "PRIVATE",
        }
    )
