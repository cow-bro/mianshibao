from __future__ import annotations

import logging
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, Template, TemplateNotFound

logger = logging.getLogger(__name__)


class PromptManager:
    """Load and render prompt templates from app/prompts."""

    def __init__(self, prompt_root: Path | None = None) -> None:
        root = prompt_root or (Path(__file__).resolve().parent.parent / "prompts")
        self.prompt_root = root
        self.env = Environment(
            loader=FileSystemLoader(str(root)),
            autoescape=False,
            trim_blocks=True,
            lstrip_blocks=True,
            undefined=StrictUndefined,
        )

    def render(self, template_name: str, **context: object) -> str:
        try:
            template = self.env.get_template(template_name)
        except TemplateNotFound as exc:
            raise FileNotFoundError(f"prompt template not found: {template_name}") from exc
        return template.render(**context).strip()

    def render_with_fallback(
        self,
        template_name: str,
        fallback_template: str,
        **context: object,
    ) -> str:
        try:
            return self.render(template_name, **context)
        except Exception as exc:  # noqa: BLE001
            logger.warning("render prompt template failed: %s", template_name, exc_info=exc)
            return Template(fallback_template).render(**context).strip()
