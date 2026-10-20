"""Risk + impact rules for data migration (DML), grants and comments."""
from __future__ import annotations

import re
from typing import List, Tuple

from core import models as M
from analyzers.context import AnalysisContext

ENV_RE = re.compile(r"'[^']*\b(PROD|PRD|UAT|QA|DEV|SIT|STG|STAGE|TEST)\b[^']*'|https?://|\b\d{1,3}(\.\d{1,3}){3}\b|@[A-Za-z0-9.-]+\.(com|net|org)", re.I)


def analyze(op: M.Operation, res: dict, ctx: AnalysisContext) -> Tuple[List[M.Finding], str]:
    f: List[M.Finding] = []
    d = op.details
    tbl = op.qualified_table
    if op.kind == M.INSERT:
        n = "multiple rows" if d.get("multi_row") else ("rows from a query" if d.get("from_select") else "1 row")
        if not d.get("columns"):
            f.append(ctx.finding(op, "MEDIUM", "INSERT_NO_COLUMNS", "INSERT without a column list breaks when columns are "
                                 "added/reordered.", "Always list target columns."))
        if d.get("from_select"):
            f.append(ctx.finding(op, "MEDIUM", "INSERT_SELECT", "INSERT ... SELECT volume unknown - can generate heavy undo/redo.",
                                 "Run the count pre-check; batch large volumes."))
        _env(op, ctx, f)
        return f, f"Inserts {n} into {tbl}."
    if op.kind in (M.UPDATE, M.DELETE, M.MERGE):
        verb = {"UPDATE": "Updates", "DELETE": "Deletes", "MERGE": "Merges into"}[op.kind]
        scope = f"rows matching: {d['where'][:120]}" if d.get("where") else "ALL rows"
        if op.kind != M.MERGE and not d.get("has_where"):
            f.append(ctx.finding(op, "HIGH", "DML_NO_WHERE", f"{op.kind} on {tbl} has no WHERE clause - affects every row.",
                                 "Confirm intent; run row-count pre-check; batch with COMMIT every N rows for big tables."))
        if op.kind == M.DELETE:
            f.append(ctx.finding(op, "HIGH", "DELETE_DATA", f"DELETE on {tbl} removes data; rollback needs a backup.",
                                 "CREATE TABLE <tbl>_BKP_<release> AS SELECT ... WHERE <same predicate> before the delete."))
        if op.kind == M.UPDATE:
            f.append(ctx.finding(op, "MEDIUM", "UPDATE_DATA", f"UPDATE overwrites {', '.join(d.get('set_columns', [])) or 'columns'}"
                                 f" on {tbl}; previous values are needed for rollback.",
                                 "Back up affected PK + columns before deploy, or accept forward-fix only."))
        f.append(ctx.finding(op, "LOW", "DML_LOCKS", f"Row locks held on {tbl} until COMMIT; long-running DML blocks OLTP.",
                             "Keep DML in its own changeSet; size undo; run off-peak."))
        _env(op, ctx, f)
        return f, f"{verb} {tbl} - {scope}."
    if op.kind in (M.GRANT, M.REVOKE):
        g = ", ".join(d.get("grantees", []))
        if any(x.upper() == "PUBLIC" for x in d.get("grantees", [])):
            f.append(ctx.finding(op, "HIGH", "GRANT_PUBLIC", "Privilege granted to PUBLIC.", "Grant to a role instead."))
        if d.get("with_grant_option"):
            f.append(ctx.finding(op, "MEDIUM", "GRANT_OPTION", "WITH GRANT OPTION allows re-granting.", "Avoid unless required."))
        verb = "Grants" if op.kind == M.GRANT else "Revokes"
        return f, f"{verb} {d.get('privileges')} on {op.qualified} {'to' if op.kind == M.GRANT else 'from'} {g}."
    if op.kind == M.COMMENT:
        tgt = f"{op.qualified}.{d['column']}" if d.get("target") == "COLUMN" else op.qualified
        return f, f"Sets comment on {d.get('target', '').lower()} {tgt}."
    if op.kind == M.TX_CONTROL:
        return f, "Transaction control (handled by Liquibase; removed from generated changeSets)."
    if op.kind == M.CLIENT_COMMAND:
        f.append(ctx.finding(op, "MEDIUM", "CLIENT_COMMAND", f"Client directive '{op.sql[:40]}' is not SQL and will fail "
                             "under Liquibase.", "Removed from generated output.", "syntax"))
        return f, "SQL*Plus/psql client directive (removed)."
    if op.kind == M.OTHER:
        f.append(ctx.finding(op, "MEDIUM", "UNRECOGNISED", f"Statement type '{op.name}' not recognised - emitted as raw "
                             "<sql> with a manual rollback placeholder.", "Review manually."))
        return f, f"Unclassified statement ({op.name})."
    return f, ""


def _env(op, ctx, f):
    m = ENV_RE.search(op.sql)
    if m:
        f.append(ctx.finding(op, "MEDIUM", "ENV_SPECIFIC_DATA", f"Data looks environment specific ({m.group(0)[:40]}).",
                             "Use Liquibase changelog parameters (${...}) or contexts per environment.", "best_practice"))
