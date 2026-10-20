"""Naming convention validation (rules in the profile 'naming' section)."""
from __future__ import annotations

import re
from typing import List

from core import models as M


def _rule(p, key):
    return (p.get("naming", {}).get("prefixes", {}) or {}).get(key)


def validate(ops: List[M.Operation], profile: dict, dialect: str) -> List[M.Finding]:
    f: List[M.Finding] = []
    nm = profile.get("naming", {})
    if not nm.get("enabled", True):
        return f
    obj_re = re.compile(nm.get("object_regex", r"^[A-Z][A-Z0-9_$#]*$"))

    def chk(op, name, key, what):
        if not name:
            return
        pat = _rule(profile, key)
        if pat and not re.search(pat, name, re.I):
            f.append(M.Finding(nm.get("severity", "LOW"), "NAMING_PREFIX", f"{what} '{name}' does not match convention {pat}.",
                               "Rename to follow the house naming standard.", "naming", f"{op.statement.source}:{op.statement.line_start}"))

    for op in ops:
        loc = f"{op.statement.source}:{op.statement.line_start}"
        k = op.kind
        if k.startswith("CREATE") and op.name and not obj_re.match(op.name) and nm.get("uppercase", True):
            f.append(M.Finding("MEDIUM", "NAMING_CASE", f"Object name '{op.name}' is not UPPER_SNAKE_CASE "
                               "(quoted mixed-case identifiers must be quoted forever).", "Use unquoted upper-case names.",
                               "naming", loc))
        if k == M.CREATE_TABLE:
            chk(op, op.name, "table", "Table")
            for c in op.details.get("constraints", []):
                if not c.name:
                    f.append(M.Finding("MEDIUM", "UNNAMED_CONSTRAINT", f"Unnamed {c.ctype} on {op.name} - database generates "
                                       "a different SYS_ name in every environment (rollback/diff cannot reference it).",
                                       "Name every constraint explicitly.", "naming", loc))
                    continue
                chk(op, c.name, {"PRIMARY KEY": "primary_key", "FOREIGN KEY": "foreign_key", "UNIQUE": "unique",
                                 "CHECK": "check"}[c.ctype], c.ctype.title())
            for c in op.details.get("columns", []):
                if nm.get("uppercase", True) and not re.match(r"^[A-Z][A-Z0-9_$#]*$", c.name):
                    f.append(M.Finding("LOW", "NAMING_CASE", f"Column '{c.name}' is not UPPER_SNAKE_CASE.", "", "naming", loc))
        elif k == M.ADD_CONSTRAINT:
            c = op.details.get("constraint")
            if isinstance(c, M.Constraint):
                if not c.name:
                    f.append(M.Finding("MEDIUM", "UNNAMED_CONSTRAINT", f"Unnamed {c.ctype} added to {op.table}.",
                                       "Name the constraint.", "naming", loc))
                else:
                    chk(op, c.name, {"PRIMARY KEY": "primary_key", "FOREIGN KEY": "foreign_key", "UNIQUE": "unique",
                                     "CHECK": "check"}[c.ctype], c.ctype.title())
        elif k == M.CREATE_INDEX:
            chk(op, op.name, "unique_index" if op.details.get("unique") else "index", "Index")
        elif k == M.CREATE_SEQUENCE:
            chk(op, op.name, "sequence", "Sequence")
        elif k == M.CREATE_TRIGGER:
            chk(op, op.name, "trigger", "Trigger")
        elif k == M.CREATE_VIEW:
            chk(op, op.name, "materialized_view" if op.details.get("materialized") else "view", "View")
        elif k == M.CREATE_PROCEDURE:
            chk(op, op.name, "procedure", "Procedure")
        elif k == M.CREATE_FUNCTION:
            chk(op, op.name, "function", "Function")
        elif k in (M.CREATE_PACKAGE, M.CREATE_PACKAGE_BODY) and not op.object_type.startswith("TYPE"):
            chk(op, op.name, "package", "Package")
    return f


def validate_author(author: str, profile: dict) -> List[M.Finding]:
    pat = profile.get("naming", {}).get("author_regex")
    if pat and not re.match(pat, author or ""):
        return [M.Finding("MEDIUM", "AUTHOR_FORMAT", f"changeSet author '{author}' does not match {pat}.",
                          "Use the team/service account author name.", "naming")]
    return []
