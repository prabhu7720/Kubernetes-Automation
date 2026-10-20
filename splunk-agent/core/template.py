"""Minimal, strict placeholder renderer for SPL templates (``{{key}}``)."""

from __future__ import annotations

from typing import Callable

from core.exceptions import TemplateRenderError
from core.models import TOKEN_RE


def placeholders(template: str) -> set[str]:
    return set(TOKEN_RE.findall(template or ""))


def render(template: str, resolve: Callable[[str], str | None]) -> str:
    """Replace every ``{{key}}`` using *resolve*; unknown keys raise ``TemplateRenderError``."""

    def _sub(match) -> str:
        key = match.group(1)
        value = resolve(key)
        if value is None:
            raise TemplateRenderError(f"Unresolved placeholder '{{{{{key}}}}}'")
        return str(value)

    return TOKEN_RE.sub(_sub, template or "")
