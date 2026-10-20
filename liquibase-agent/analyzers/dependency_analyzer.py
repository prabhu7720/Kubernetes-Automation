"""Cross-operation analysis: ordering, invalidation windows and FK index coverage."""
from __future__ import annotations

import re
from typing import List

from core import models as M
from analyzers.context import AnalysisContext


def analyze_release(ops: List[M.Operation], ctx: AnalysisContext) -> List[M.Finding]:
    f: List[M.Finding] = []
    sch = ctx.schema
    created_at = {}
    for op in ops:
        if op.kind in (M.CREATE_TABLE, M.CREATE_TABLE_AS):
            created_at.setdefault(sch.key(op.schema, op.name), op.seq)

    for op in ops:
        # ---- ordering: objects depending on a table created later in the release
        deps = []
        if op.kind in (M.CREATE_INDEX, M.CREATE_TRIGGER, M.ADD_COLUMN, M.ADD_CONSTRAINT, M.COMMENT, M.GRANT):
            deps.append(sch.key(op.details.get("table_schema") or op.schema, op.table))
        if op.kind == M.CREATE_TABLE:
            for c in op.details.get("constraints", []):
                if c.ctype == "FOREIGN KEY":
                    deps.append(sch.key(c.ref_schema or op.schema, c.ref_table))
        if op.kind == M.CREATE_VIEW:
            for r in op.details.get("references", []):
                s, _, n = r.rpartition(".")
                deps.append(sch.key(s or op.schema, n))
        for dk in deps:
            if dk in created_at and created_at[dk] > op.seq:
                f.append(ctx.finding(op, "HIGH", "ORDER_DEPENDENCY", f"{op.kind} {op.name} (step {op.seq}) depends on "
                                     f"{dk}, which is only created at step {created_at[dk]}.",
                                     "Reorder: create referenced objects first.", "conflict"))

        # ---- dropped / renamed columns still referenced by code objects
        if op.kind in (M.DROP_COLUMN, M.RENAME_COLUMN):
            cols = op.details.get("columns") or [op.details.get("column")]
            cols = [c.upper() for c in cols if c]
            candidates = {}
            latest = {}
            # latest definition (before this drop) of each code object created in this release
            for prev in ops:
                if prev.seq >= op.seq:
                    break
                if prev.kind in (M.CREATE_VIEW, M.CREATE_TRIGGER, M.CREATE_PROCEDURE, M.CREATE_FUNCTION,
                                 M.CREATE_PACKAGE_BODY):
                    latest[sch.key(prev.schema, prev.name)] = prev
                elif prev.kind in (M.DROP_VIEW, M.DROP_TRIGGER, M.DROP_ROUTINE):
                    latest.pop(sch.key(prev.schema, prev.name), None)
            for k, prev in latest.items():
                used = _refs(prev.sql, op.table, cols)
                if used:
                    candidates[k] = (prev.object_type, used)
            for dep in op.details.get("_dependents", []):      # baseline objects
                if dep["name"] not in candidates and dep["name"] not in latest:
                    candidates[dep["name"]] = (dep["type"], dep["columns"])
            for later in ops:
                if later.seq <= op.seq:
                    continue
                k = sch.key(later.schema, later.name)
                if k in candidates and later.kind in M.REPLACEABLE_KINDS:
                    still = _refs(later.sql, op.table, cols)
                    otype, used = candidates.pop(k)
                    if still:
                        f.append(ctx.finding(later, "HIGH", "STILL_REFERENCES_DROPPED", f"{otype} {k} is re-created at step "
                                             f"{later.seq} but still references dropped column(s) {', '.join(still)}.",
                                             "Remove the column from the object body.", "conflict"))
                    else:
                        f.append(ctx.finding(op, "MEDIUM", "INVALID_WINDOW", f"{otype} {k} references {', '.join(used)} and is "
                                             f"INVALID between step {op.seq} and its re-creation at step {later.seq}. DML on "
                                             f"{op.table} fails in that window (ORA-04098 for triggers).",
                                             "Deploy these changeSets together in one maintenance window / same "
                                             "liquibase update run; quiesce application writes."))
            for k, (otype, used) in candidates.items():
                f.append(ctx.finding(op, "HIGH", "DEPENDENT_INVALIDATED", f"{otype} {k} references {op.table}."
                                     f"{', '.join(used)} which is dropped at step {op.seq} and is not re-created afterwards.",
                                     f"Add CREATE OR REPLACE for {k} without these columns.", "conflict"))

    # ---- FK columns without supporting index (final state)
    for tk, t in sch.tables.items():
        if t.origin != "new" and not _touched(tk, ops, sch):
            continue
        for c in t.constraints.values():
            if c.ctype != "FOREIGN KEY" or not c.columns:
                continue
            if not sch.covering_index(t.schema, t.name, c.columns):
                f.append(M.Finding("MEDIUM", "FK_NO_INDEX", f"FK {c.name or '(unnamed)'} on {tk} ({', '.join(c.columns)}) has no supporting "
                                   "index - parent DELETE/UPDATE does full scans and (Oracle) locks the child table.",
                                   f"CREATE INDEX IDX_{t.name[:12]}_{'_'.join(c.columns)[:12]} ON {tk} ({', '.join(c.columns)});",
                                   "risk", tk))
    return f


def _touched(tk, ops, sch):
    return any(sch.key(o.schema, o.table or o.name) == tk and o.kind == M.ADD_CONSTRAINT for o in ops)


def _refs(sql: str, table: str, cols: List[str]) -> List[str]:
    u = (sql or "").upper()
    if not table or not re.search(r"\b" + re.escape(table.upper()) + r"\b", u):
        return []
    return [c for c in cols if re.search(r"(?<![\w$#])" + re.escape(c) + r"(?![\w$#])", u)]
