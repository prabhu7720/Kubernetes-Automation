"""Access to the editable text templates in ``templates/`` (string.Template syntax: $var)."""

from __future__ import annotations

import json
import string
from pathlib import Path
from typing import Any

import yaml


class TemplateStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def text(self, relative: str, default: str = "") -> str:
        path = self.root / relative
        return path.read_text(encoding="utf-8") if path.is_file() else default

    def yaml(self, relative: str, default: Any = None) -> Any:
        text = self.text(relative)
        return (yaml.safe_load(text) or default) if text else default

    def json(self, relative: str, default: Any = None) -> Any:
        text = self.text(relative)
        return json.loads(text) if text else default

    def substitute(self, relative: str, default: str = "", **values: Any) -> str:
        return string.Template(self.text(relative, default)).safe_substitute(
            {k: ("" if v is None else v) for k, v in values.items()})
