"""Tiny XML helpers (stdlib only) - escaping, element building, indentation."""
from __future__ import annotations

from typing import Dict, Optional
from xml.sax.saxutils import escape, quoteattr


def attrs(a: Dict[str, Optional[str]]) -> str:
    return "".join(f" {k}={quoteattr(str(v))}" for k, v in a.items() if v is not None and v != "")


def el(tag: str, a: Optional[Dict] = None, body: Optional[str] = None) -> str:
    if body is None or body == "":
        return f"<{tag}{attrs(a or {})}/>"
    if "\n" in body or body.startswith("<"):
        return f"<{tag}{attrs(a or {})}>\n{indent(body, 4)}\n</{tag}>"
    return f"<{tag}{attrs(a or {})}>{body}</{tag}>"


def cdata(s: str) -> str:
    s = s.replace("]]>", "]]]]><![CDATA[>")
    return f"<![CDATA[\n{s.rstrip()}\n]]>"


def text(s: str) -> str:
    return escape(s or "")


def indent(block: str, n: int) -> str:
    pad = " " * n
    out, in_cdata = [], False
    for ln in block.split("\n"):
        if in_cdata:
            out.append(ln)
            if "]]>" in ln:
                in_cdata = False
            continue
        out.append(pad + ln if ln.strip() else ln)
        if "<![CDATA[" in ln and "]]>" not in ln.split("<![CDATA[", 1)[1]:
            in_cdata = True
    return "\n".join(out)
