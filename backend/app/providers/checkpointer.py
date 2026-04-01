"""LangGraph checkpointer bootstrap with graceful fallback."""

from __future__ import annotations

import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_CHECKPOINTER_CONTEXTS: list[object] = []


class NoopCheckpointer:
    """Placeholder checkpointer used when langgraph is not installed."""

    def __init__(self) -> None:
        self.store: dict[str, dict] = {}


def build_checkpointer():
    """Prefer PostgresSaver and fallback by environment policy."""
    settings = get_settings()
    env = (settings.environment or "dev").lower()
    is_production = env in {"prod", "production"}
    allow_memory_fallback = (
        settings.langgraph_allow_inmemory_checkpointer
        if not is_production
        else settings.langgraph_allow_inmemory_checkpointer_in_production
    )

    def _fatal_or_warn(message: str, *, with_exception: bool = False):
        if allow_memory_fallback:
            if with_exception:
                logger.exception(message)
            else:
                logger.warning(message)
            return
        if with_exception:
            logger.critical(message, exc_info=True)
        else:
            logger.critical(message)
        raise RuntimeError(message)

    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except Exception:  # pragma: no cover - optional dependency in local env
        PostgresSaver = None  # type: ignore[assignment]

    try:
        from langgraph.checkpoint.memory import InMemorySaver
    except Exception:
        _fatal_or_warn(
            f"langgraph memory checkpointer unavailable in environment={env}; cannot initialize interview graph state store",
            with_exception=True,
        )
        return NoopCheckpointer()

    if PostgresSaver is None:
        _fatal_or_warn(
            f"PostgresSaver unavailable in environment={env}; falling back to InMemorySaver",
        )
        return InMemorySaver()

    sync_dsn = (
        settings.database_url.replace("+psycopg_async", "").replace("+psycopg", "")
    )

    try:
        manager = PostgresSaver.from_conn_string(sync_dsn)
        checkpointer = manager.__enter__() if hasattr(manager, "__enter__") else manager
        if hasattr(manager, "__enter__"):
            _CHECKPOINTER_CONTEXTS.append(manager)
        setup = getattr(checkpointer, "setup", None)
        if callable(setup):
            setup()
        logger.info("Interview graph checkpointer initialized with PostgreSQL (environment=%s)", env)
        return checkpointer
    except Exception:
        _fatal_or_warn(
            f"Failed to initialize PostgresSaver in environment={env}; falling back to InMemorySaver",
            with_exception=True,
        )
        return InMemorySaver()
