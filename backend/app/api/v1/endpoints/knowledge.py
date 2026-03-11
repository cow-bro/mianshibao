"""Knowledge RAG endpoints: ingest, search, ask."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_active_user, get_db
from app.core.response import success_response
from app.models.user import User
from app.schemas.knowledge import AskRequest, IngestRequest, SearchRequest
from app.services.knowledge_service import KnowledgeService

router = APIRouter()

_service = KnowledgeService()


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
    results = await _service.hybrid_search(db, request.query, request.top_k)
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


@router.post("/ask")
async def ask_knowledge(
    request: AskRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_active_user),
):
    """RAG Q&A: retrieve context and generate a grounded answer."""
    result = await _service.ask_knowledge_base(db, request.question)
    return success_response(data=result)
