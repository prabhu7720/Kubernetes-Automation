"""Best-practice checks: environment independence, DDL/DML separation, transaction control,
client directives, author / id conventions of the generated output."""
from __future__ import annotations

import re
from collections import Counter
from typing import List

from core import models as M
from core.lexer import strip_comments


def validate(ops: List[M.Operation], profile: dict, dialect: str) -> List[M.Finding]:
    f: List[M.Finding] = []
    bp = profile.get("best_practices", {})
    schemas = Counter(o.schema for o in ops if o.schema and o.kind not in (M.TX_CONTROL, M.TRACKER))
    explicit = Counter()
    for o in ops:
        if o.kind in (M.TX_CONTROL, M.TRACKER, M.CLIENT_COMMAND):
            continue
        for m in re.finditer(r"\b\"?([A-Za-z_][\w$#]*)\"?\s*\.\s*\"?[A-Za-z_]", strip_comments(o.statement.sql)):
            if m.group(1).upper() in {s.upper() for s in schemas}:
                explicit[m.group(1).upper()] += 1
    sev_env = "INFO" if bp.get("allow_hardcoded_schema") else "LOW"
    for s, n in explicit.items():
        f.append(M.Finding(sev_env, "ENV_HARDCODED_SCHEMA", f"Schema '{s}' is hard-coded {n} time(s).",
                           "For environment independence use a changelog property, e.g. "
                           "<property name=\"schema\" value=\"" + s + "\"/> and ${schema}.OBJECT, or rely on the "
                           "connection's default schema (liquibase.defaultSchemaName).", "best_practice"))
    ts = Counter()
    for o in ops:
        for m in re.finditer(r"\bTABLESPACE\s+\"?([\w$#]+)\"?", o.statement.sql, re.I):
            ts[m.group(1).upper()] += 1
    if ts and not bp.get("allow_hardcoded_tablespace"):
        f.append(M.Finding("LOW", "ENV_HARDCODED_TABLESPACE", f"Tablespace name(s) hard-coded: {', '.join(ts)}.",
                           "Use a ${tablespace} property if tablespace names differ between environments.", "best_practice"))
    for o in ops:
        loc = f"{o.statement.source}:{o.statement.line_start}"
        if re.search(r"@[A-Za-z_][\w.$#]*\b", re.sub(r"'(?:[^']|'')*'", "", strip_comments(o.sql))) and dialect == "oracle" \
                and o.kind not in (M.CLIENT_COMMAND,):
            f.append(M.Finding("MEDIUM", "ENV_DBLINK", "Database link reference (@dblink) - environment specific.",
                               "Parameterise the db-link name or use a synonym.", "best_practice", loc))
    sources = {}
    for o in ops:
        sources.setdefault(o.statement.source, set()).add("DML" if o.is_dml else ("DDL" if o.is_ddl else "OTHER"))
    for src, kinds in sources.items():
        if {"DML", "DDL"} <= kinds:
            f.append(M.Finding("INFO", "SPLIT_DDL_DML", f"{src} mixes DDL and DML - the agent emitted them as separate "
                               "changeSets.", "", "best_practice"))
    n_commit = sum(1 for o in ops if o.kind == M.TX_CONTROL)
    if n_commit:
        f.append(M.Finding("INFO", "TX_REMOVED", f"{n_commit} COMMIT/ROLLBACK statement(s) removed - Liquibase commits each "
                           "changeSet (house tracker COMMITs are regenerated).", "", "best_practice"))
    n_tr = sum(1 for o in ops if o.kind == M.TRACKER)
    if n_tr:
        f.append(M.Finding("INFO", "TRACKER_REGENERATED", f"{n_tr} existing change-tracker statement(s) ignored and "
                           "regenerated with new changeSet ids.", "", "best_practice"))
    seen = Counter((o.kind, (o.qualified or "").upper()) for o in ops if o.kind.startswith("CREATE") and o.kind not in M.REPLACEABLE_KINDS)
    for (k, n), c in seen.items():
        if c > 1:
            f.append(M.Finding("HIGH", "DUPLICATE_CREATE", f"{k} {n} appears {c} times in the input.", "Remove duplicates.",
                               "conflict"))
    return f
