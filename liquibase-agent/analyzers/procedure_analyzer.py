"""Risk + impact rules for views, triggers, procedures, functions, packages and blocks."""
from __future__ import annotations

import re
from typing import List, Tuple

from core import models as M
from core.lexer import strip_comments
from analyzers.context import AnalysisContext


def before_apply(op: M.Operation, ctx: AnalysisContext) -> List[M.Finding]:
    """Compile-time checks against the schema state at this point of the release."""
    f = []
    if op.kind == M.CREATE_TRIGGER and op.table:
        t = ctx.schema.table(op.details.get("table_schema") or op.schema, op.table)
        if t is None and ctx.schema.has_baseline:
            f.append(ctx.finding(op, "HIGH", "TRIGGER_TABLE_MISSING", f"Trigger table {op.table} does not exist at this "
                                 "point in the release.", "Create the table before the trigger.", "conflict"))
        if t and t.columns:
            bad = [c for c in op.details.get("columns_used", []) if c not in t.columns]
            if bad:
                f.append(ctx.finding(op, "HIGH", "TRIGGER_BAD_COLUMNS", f"Trigger references :NEW/:OLD column(s) not on "
                                     f"{op.table}: {', '.join(bad)} - trigger will compile INVALID (ORA-04098 on DML).",
                                     "Fix the trigger body or statement order.", "conflict"))
    if op.kind in (M.CREATE_TRIGGER, M.CREATE_PROCEDURE, M.CREATE_FUNCTION, M.CREATE_PACKAGE_BODY, M.PLSQL_BLOCK):
        body = strip_comments(op.sql)
        for m in re.finditer(r"INSERT\s+INTO\s+([\w$#\".]+)\s*\(([^)]*)\)", body, re.I):
            tname = m.group(1).replace('"', "")
            sch, _, nm = tname.rpartition(".")
            t = ctx.schema.table(sch or op.schema, nm)
            if t and t.columns:
                cols = [c.strip().strip('"').upper() for c in m.group(2).split(",") if c.strip()]
                bad = [c for c in cols if c not in t.columns]
                if bad:
                    f.append(ctx.finding(op, "HIGH", "PLSQL_BAD_COLUMNS", f"{op.name} inserts into {nm} column(s) that do not "
                                         f"exist at this point: {', '.join(bad)} - object will be INVALID.",
                                         "Align the column list with the table definition.", "conflict"))
        for m in re.finditer(r"([\w$#\".]+)\.NEXTVAL", body, re.I):
            seq = m.group(1).replace('"', "")
            sch, _, nm = seq.rpartition(".")
            if ctx.schema.has_baseline and not ctx.schema.object_exists("SEQUENCE", sch or op.schema, nm):
                f.append(ctx.finding(op, "MEDIUM", "SEQ_NOT_FOUND", f"Sequence {seq} used by {op.name} not found in "
                                     "baseline or earlier in the release.", "", "conflict"))
    return f


def analyze(op: M.Operation, res: dict, ctx: AnalysisContext) -> Tuple[List[M.Finding], str]:
    f: List[M.Finding] = []
    d = op.details
    body = strip_comments(op.sql)
    ub = body.upper()
    existed = res.get("existed")
    replaced_known = existed and res.get("before") is not None

    def common_plsql():
        if re.search(r"WHEN\s+OTHERS\s+THEN\s+NULL", ub):
            f.append(ctx.finding(op, "MEDIUM", "SWALLOW_EXCEPTIONS", f"{op.name} swallows all errors (WHEN OTHERS THEN NULL).",
                                 "Log and re-raise (RAISE;)."))
        if re.search(r"EXECUTE\s+IMMEDIATE|DBMS_SQL\.|\bEXEC\s*\(|sp_executesql", body, re.I):
            f.append(ctx.finding(op, "MEDIUM", "DYNAMIC_SQL", f"{op.name} uses dynamic SQL - not validated at compile time; "
                                 "injection risk if concatenating input.", "Use bind variables; review statements."))
        if re.search(r"\bDBMS_OUTPUT\.", ub):
            f.append(ctx.finding(op, "LOW", "DBMS_OUTPUT", "DBMS_OUTPUT left in production code."))

    if op.kind == M.CREATE_VIEW:
        cols = d.get("columns") or []
        impact = (f"{'Replaces' if existed else 'Creates'} {'materialized ' if d.get('materialized') else ''}view "
                  f"{op.qualified}" + (f" exposing {len(cols)} column(s)" if cols else "") +
                  (f" over {', '.join(d.get('references', [])[:8])}" if d.get("references") else "") + ".")
        if existed:
            impact += " Existing view definition is overwritten; dependent objects are invalidated and recompiled on next use."
            if not replaced_known:
                f.append(ctx.finding(op, "HIGH", "REPLACE_NO_PREVIOUS", f"{op.name} already exists but its current definition "
                                     "is unknown - rollback cannot restore it automatically.",
                                     "Export the current view DDL (DBMS_METADATA.GET_DDL) into --baseline.", "rollback"))
        elif op.or_replace and not ctx.schema.has_baseline:
            f.append(ctx.finding(op, "MEDIUM", "REPLACE_UNKNOWN", f"CREATE OR REPLACE {op.name}: without a baseline the agent "
                                 "cannot tell whether a previous version exists. Rollback defaults to DROP VIEW.",
                                 "If the view exists today, supply its DDL via --baseline so rollback restores it."))
        if d.get("force"):
            f.append(ctx.finding(op, "LOW", "VIEW_FORCE", "FORCE creates the view even if it does not compile.",
                                 "Post-check: view STATUS must be VALID."))
        if re.search(r"SELECT\s+(\w+\.)?\*", d.get("select", ""), re.I):
            f.append(ctx.finding(op, "MEDIUM", "VIEW_SELECT_STAR", "SELECT * in a view freezes the column list at creation time.",
                                 "List columns explicitly."))
        if d.get("materialized"):
            f.append(ctx.finding(op, "MEDIUM", "MVIEW", "Materialized view: initial build and refresh cost on source tables.",
                                 "Define refresh method/schedule; build off-peak."))
        if re.search(r"ROW_NUMBER\s*\(\s*\)\s*OVER", ub) or len(re.findall(r"\bJOIN\b", ub)) >= 6:
            f.append(ctx.finding(op, "LOW", "VIEW_COMPLEX", f"Complex view ({len(re.findall(r'JOIN', ub))} joins / analytic "
                                 "functions).", "Validate execution plan for main access paths after deploy."))
        return f, impact

    if op.kind == M.CREATE_TRIGGER:
        ev = " OR ".join(d.get("events", []))
        impact = (f"{'Replaces' if existed else 'Creates'} {d.get('timing', '')} {ev} "
                  f"{'row-level ' if d.get('row_level') else 'statement-level '}trigger {op.qualified} on {op.table}. "
                  f"Fires on every {ev.lower()} against {op.table}.")
        if existed and not replaced_known:
            f.append(ctx.finding(op, "HIGH", "REPLACE_NO_PREVIOUS", f"Trigger {op.name} already exists; previous source unknown, "
                                 "rollback cannot restore it.", "Supply --baseline.", "rollback"))
        if d.get("row_level"):
            f.append(ctx.finding(op, "MEDIUM", "TRIGGER_OVERHEAD", f"Row-level trigger adds per-row overhead to all "
                                 f"{ev} on {op.table} (bulk loads/batch jobs slow down).",
                                 "Benchmark batch jobs; consider disabling during bulk loads."))
        if re.search(r"\bCOMMIT\b|\bROLLBACK\b", ub) and "AUTONOMOUS_TRANSACTION" not in ub:
            f.append(ctx.finding(op, "HIGH", "TRIGGER_COMMIT", "COMMIT/ROLLBACK inside a trigger raises ORA-04092.",
                                 "Remove transaction control from the trigger."))
        if "AUTONOMOUS_TRANSACTION" in ub:
            f.append(ctx.finding(op, "MEDIUM", "AUTONOMOUS_TX", "Autonomous transaction: writes persist even when the "
                                 "triggering statement rolls back.", "Confirm this is intended (logging only)."))
        own = (op.table or "").upper()
        if d.get("row_level") and own and re.search(r"(FROM|JOIN)\s+([\w$#\"]+\.)?\"?" + re.escape(own) + r"\b", ub) \
                and ctx.dialect == "oracle" and not d.get("compound"):
            f.append(ctx.finding(op, "HIGH", "MUTATING_TABLE", f"Row trigger queries its own table {op.table} - ORA-04091 "
                                 "mutating table at runtime.", "Use a compound trigger or move logic to the application."))
        if re.search(r"\bINSERT\s+INTO\b", ub):
            f.append(ctx.finding(op, "LOW", "TRIGGER_WRITES", "Trigger writes to another table (audit pattern); "
                                 "that table's growth/purge policy must be defined.", "Add a retention/purge job for audit rows."))
        common_plsql()
        return f, impact

    if op.kind in (M.CREATE_PROCEDURE, M.CREATE_FUNCTION, M.CREATE_PACKAGE, M.CREATE_PACKAGE_BODY):
        refs = d.get("references", [])
        impact = (f"{'Replaces' if existed else 'Creates'} {op.object_type.lower()} {op.qualified}" +
                  (f"; touches {', '.join(refs[:8])}" if refs else "") + ".")
        if existed and not replaced_known:
            f.append(ctx.finding(op, "HIGH", "REPLACE_NO_PREVIOUS", f"{op.name} exists; previous source unknown - rollback "
                                 "cannot restore it.", "Supply --baseline.", "rollback"))
        elif op.or_replace and not ctx.schema.has_baseline:
            f.append(ctx.finding(op, "MEDIUM", "REPLACE_UNKNOWN", f"CREATE OR REPLACE {op.name} without baseline - rollback "
                                 "defaults to DROP.", "Provide the current source if it already exists."))
        if re.search(r"\bCOMMIT\b", ub) and op.kind != M.CREATE_PACKAGE:
            f.append(ctx.finding(op, "MEDIUM", "PROC_COMMIT", f"{op.name} issues COMMIT - callers lose transaction control.",
                                 "Let the caller own the transaction unless this is a batch job."))
        if re.search(r"\b(CREATE|ALTER|DROP|TRUNCATE)\s+(TABLE|INDEX)", ub):
            f.append(ctx.finding(op, "HIGH", "PROC_DDL", f"{op.name} performs DDL at runtime (implicit commits)."))
        common_plsql()
        if ctx.dialect == "oracle" and op.kind != M.CREATE_PACKAGE_BODY:
            f.append(ctx.finding(op, "INFO", "INVALIDATION", "Replacing PL/SQL invalidates dependants; active sessions "
                                 "may get ORA-04068 (existing state of packages discarded).",
                                 "Deploy during low traffic; recompile invalid objects after deploy."))
        return f, impact

    if op.kind == M.PLSQL_BLOCK:
        f.append(ctx.finding(op, "MEDIUM", "ANON_BLOCK", "Anonymous PL/SQL block - effects cannot be auto-rolled back "
                             "and re-runs must be idempotent.", "Write an explicit rollback block; guard with existence checks."))
        common_plsql()
        return f, "Executes an anonymous PL/SQL block" + (f" touching {', '.join(d.get('references', [])[:6])}" if d.get("references") else "") + "."

    if op.kind in (M.DROP_VIEW, M.DROP_TRIGGER, M.DROP_ROUTINE):
        before = res.get("before")
        if before is None:
            f.append(ctx.finding(op, "MEDIUM", "DROP_NO_SOURCE", f"Source of {op.qualified} unknown - rollback cannot recreate it.",
                                 "Supply --baseline DDL.", "rollback"))
        f.append(ctx.finding(op, "MEDIUM", "DROP_CODE_OBJECT", f"Callers of {op.qualified} will fail after the drop.",
                             "Confirm no application / job references remain."))
        return f, f"Drops {op.object_type.lower()} {op.qualified}."
    return f, ""
