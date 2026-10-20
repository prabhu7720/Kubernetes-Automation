"""Template loader: one file may hold several named templates separated by
'<!-- @template NAME -->' (XML) or '-- @template NAME' (SQL) markers.
Templates use ${placeholder} (string.Template) syntax and can be customised freely."""
from __future__ import annotations

import os
import re
from string import Template
from typing import Dict

_MARK = re.compile(r"^\s*(?:<!--\s*@template\s+(\w+)\s*-->|--\s*@template\s+(\w+))\s*$", re.M)


class Templates:
    def __init__(self, directory: str):
        self.dir = directory
        self.t: Dict[str, Template] = {}
        for fn in sorted(os.listdir(directory)):
            if fn.endswith((".xml", ".sql")):
                self._load(os.path.join(directory, fn))

    def _load(self, path):
        text = open(path, encoding="utf-8").read()
        marks = list(_MARK.finditer(text))
        for i, m in enumerate(marks):
            name = m.group(1) or m.group(2)
            end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
            body = text[m.end():end].strip("\n")
            self.t[name] = Template(body)

    def render(self, name: str, **kw) -> str:
        if name not in self.t:
            raise KeyError(f"Template '{name}' not found in {self.dir}")
        return self.t[name].safe_substitute(**{k: ("" if v is None else v) for k, v in kw.items()})
