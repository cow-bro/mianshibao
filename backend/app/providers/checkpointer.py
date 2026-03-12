"""LangGraph checkpointer bootstrap with graceful fallback."""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class NoopCheckpointer:
    """Placeholder checkpointer used when langgraph is not installed."""

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}


def build_checkpointer():
    """Prefer PostgresSaver when available, fallback to in-memory saver."""
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except Exception:  # pragma: no cover - optional dependency in local env
        PostgresSaver = None  # type: ignore[assignment]

    try:
        from langgraph.checkpoint.memory import InMemorySaver
    except Exception:
        logger.warning("langgraph not installed, using NoopCheckpointer")
        return NoopCheckpointer()

    if PostgresSaver is None:
        logger.warning("PostgresSaver not available, using InMemorySaver")
        return InMemorySaver()

    settings = get_settings()
    sync_dsn = settings.database_url.replace("+psycopg_async", "+psycopg")

    try:
        checkpointer = PostgresSaver.from_conn_string(sync_dsn)
        setup = getattr(checkpointer, "setup", None)
        if callable(setup):
            setup()
        logger.info("Interview graph checkpointer initialized with PostgreSQL")
        return checkpointer
    except Exception:
        logger.exception("Failed to initialize PostgresSaver, fallback to InMemorySaver")
        return InMemorySaver()
