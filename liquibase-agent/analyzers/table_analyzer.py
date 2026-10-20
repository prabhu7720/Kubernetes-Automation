"""Risk + impact rules for table level operations."""
from __future__ import annotations

import re
from typing import List, Tuple

from core import models as M
from analyzers.context import AnalysisContext


def _type_parts(t: str):
    m = re.match(r"\s*([A-Za-z0-9_ ]+?)\s*(\(([^)]*)\))?\s*$", t or "")
    if not m:
        return (t or "").upper(), []
    base = m.group(1).upper().strip()
    args = [a.strip().split()[0] for a in (m.group(3) or "").split(",") if a.strip()]
    return base, args


_FAMILY = {
    "VARCHAR2": "STR", "VARCHAR": "STR", "NVARCHAR2": "STR", "NVARCHAR": "STR", "CHAR": "STR", "NCHAR": "STR",
    "CHARACTER VARYING": "STR", "TEXT": "STR", "CLOB": "LOB", "NCLOB": "LOB", "BLOB": "BIN",
    "NUMBER": "NUM", "NUMERIC": "NUM", "DECIMAL": "NUM", "INT": "NUM", "INTEGER": "NUM", "BIGINT": "NUM",
    "SMALLINT": "NUM", "TINYINT": "NUM", "FLOAT": "NUM", "DOUBLE": "NUM", "REAL": "NUM",
    "DATE": "DT", "TIMESTAMP": "DT", "DATETIME": "DT", "DATETIME2": "DT", "TIMESTAMP WITH TIME ZONE": "DT",
    "TIMESTAMPTZ": "DT", "TIME": "DT",
}


def compare_types(old: str, new: str) -> Tuple[str, str]:
    """Return (verdict, detail). verdict in SAME|WIDEN|NARROW|CHANGE|UNKNOWN."""
    if not old or not new:
        return "UNKNOWN", ""
    ob, oa = _type_parts(old)
    nb, na = _type_parts(new)
    if ob == nb and oa == na:
        return "SAME", ""
    if _FAMILY.get(ob, ob) != _FAMILY.get(nb, nb):
        return "CHANGE", f"{old} -> {new} changes the data type family"
    try:
        if oa and na:
            o, n = [int(x) for x in oa if x.isdigit()], [int(x) for x in na if x.isdigit()]
            if o and n:
                if n[0] < o[0] or (len(o) > 1 and len(n) > 1 and n[1] < o[1]):
                    return "NARROW", f"{old} -> {new} reduces length/precision"
                return "WIDEN", f"{old} -> {new}"
        if oa and not na:
            return "WIDEN", f"{old} -> {new}"
        if na and not oa:
            return "NARROW", f"{old} -> {new} adds a length/precision limit"
    except ValueError:
        pass
    return "CHANGE", f"{old} -> {new}"


def analyze(op: M.Operation, res: dict, ctx: AnalysisContext) -> Tuple[List[M.Finding], str]:
    f = []
    d = op.details
    tbl = op.qualified_table
    new_tbl = ctx.is_new_table(op.schema, op.table)
    k = op.kind
    prof = ctx.profile

    if k in (M.CREATE_TABLE, M.CREATE_TABLE_AS):
        cols = d.get("columns", [])
        cons = d.get("constraints", [])
        pk = [c for c in cons if c.ctype == "PRIMARY KEY"]
        uks = [c for c in cons if c.ctype == "UNIQUE"]
        fks = [c for c in cons if c.ctype == "FOREIGN KEY"]
        cks = [c for c in cons if c.ctype == "CHECK"]
        parts = [f"Creates table {tbl} with {len(cols)} column(s)"]
        if pk:
            parts.append(f"primary key {pk[0].name or '(unnamed)'} ({', '.join(pk[0].columns)})")
        if uks:
            parts.append(f"{len(uks)} unique constraint(s) [{', '.join(u.name or '?' for u in uks)}]")
        if fks:
            parts.append("foreign key(s) to " + ", ".join(
                f"{(c.ref_schema + '.') if c.ref_schema else ''}{c.ref_table}" for c in fks))
        if cks:
            parts.append(f"{len(cks)} check constraint(s)")
        if d.get("tablespace"):
            parts.append(f"tablespace {d['tablespace']}")
        if d.get("nologging"):
            parts.append("NOLOGGING")
        impact = "; ".join(parts) + ". New empty object - no impact on existing data or sessions."
        if k == M.CREATE_TABLE_AS:
            impact = f"Creates table {tbl} populated from a query (CTAS). Copies data; constraints/indexes/grants are NOT copied."
            f.append(ctx.finding(op, "MEDIUM", "CTAS", "CREATE TABLE AS SELECT copies data without constraints, "
                                 "defaults, indexes or grants.", "Add constraints/indexes explicitly; check source row count."))
        if not pk and k == M.CREATE_TABLE and not d.get("temporary"):
            f.append(ctx.finding(op, "MEDIUM", "NO_PK", f"Table {tbl} has no primary key.",
                                 "Add a primary key - required for replication/CDC (GoldenGate, Debezium) and Liquibase diff."))
        if d.get("nologging"):
            f.append(ctx.finding(op, "MEDIUM", "NOLOGGING", f"{tbl} is created NOLOGGING - direct-path loads are not "
                                 "written to redo and cannot be recovered from archive logs / Data Guard standby.",
                                 "Take an RMAN backup after load or switch to LOGGING once loaded; confirm with DBA if "
                                 "FORCE LOGGING is enabled on the database."))
        if ctx.dialect == "oracle" and not d.get("tablespace") and prof.get("tablespace", {}).get("enforce"):
            f.append(ctx.finding(op, "LOW", "NO_TABLESPACE", f"No TABLESPACE clause for {tbl}; it will land in the "
                                 "user's default tablespace.", f"Add TABLESPACE {_ts(prof, op)}"))
        for c in fks:
            if c.on_delete and "CASCADE" in c.on_delete.upper():
                f.append(ctx.finding(op, "MEDIUM", "ON_DELETE_CASCADE", f"FK {c.name or '(unnamed)'} uses ON DELETE CASCADE - deleting a "
                                     f"parent row in {c.ref_table} silently deletes child rows.",
                                     "Confirm this is intended; index the FK column to avoid full scans on parent delete."))
        req = [x.upper() for x in prof.get("required_columns", [])]
        if req and k == M.CREATE_TABLE and not re.search(prof.get("required_columns_exempt_regex", "$^"), op.name, re.I):
            have = {c.name.upper() for c in cols}
            miss = [x for x in req if x not in have]
            if miss:
                f.append(ctx.finding(op, "LOW", "MISSING_STD_COLUMNS", f"{tbl} is missing standard audit column(s): "
                                     f"{', '.join(miss)}.", "Add the house-standard audit columns.", "best_practice"))
        for c in cols:
            t = (c.data_type or "").upper()
            if ctx.dialect == "oracle" and re.match(r"^VARCHAR\s*\(", t):
                f.append(ctx.finding(op, "LOW", "ORA_VARCHAR", f"{tbl}.{c.name} uses VARCHAR; Oracle recommends VARCHAR2.",
                                     "Use VARCHAR2(n [BYTE|CHAR])."))
            if re.match(r"^(FLOAT|REAL|DOUBLE)", t) and re.search(r"AMT|AMOUNT|PRICE|BAL|COST|RATE", c.name, re.I):
                f.append(ctx.finding(op, "MEDIUM", "FLOAT_MONEY", f"{tbl}.{c.name} looks monetary but uses {t}.",
                                     "Use NUMBER/DECIMAL with explicit precision and scale."))
        return f, impact

    if k == M.DROP_TABLE:
        before = res.get("before")
        deps = ctx.schema.dependents_on_table(op.schema, op.name)
        impact = f"Drops table {tbl} and ALL of its data, indexes, triggers and grants."
        f.append(ctx.finding(op, "CRITICAL", "DROP_TABLE", f"DROP TABLE {tbl} permanently removes data.",
                             "Take a backup (expdp / CTAS copy) first. Prefer RENAME + deferred drop in a later release."))
        if d.get("purge"):
            f.append(ctx.finding(op, "CRITICAL", "DROP_PURGE", "PURGE bypasses the Oracle recycle bin - no FLASHBACK TABLE recovery.",
                                 "Remove PURGE so FLASHBACK TABLE ... TO BEFORE DROP remains possible."))
        if d.get("cascade"):
            f.append(ctx.finding(op, "HIGH", "DROP_CASCADE", "CASCADE CONSTRAINTS silently drops referencing foreign keys "
                                 "on other tables.", "List referencing FKs in the pre-check and recreate them in rollback if needed."))
        if deps:
            f.append(ctx.finding(op, "HIGH", "DROP_DEPENDENTS", "Dependent objects will be invalidated/dropped: " +
                                 ", ".join(f"{x['type']} {x['name']}" for x in deps[:10]),
                                 "Drop/recreate dependents explicitly in the same release."))
        if before is None:
            f.append(ctx.finding(op, "HIGH", "DROP_NO_BASELINE", f"Definition of {tbl} unknown - rollback cannot recreate it.",
                                 "Provide the current DDL with --baseline so the agent can generate an exact rollback.", "rollback"))
        return f, impact

    if k == M.TRUNCATE_TABLE:
        f.append(ctx.finding(op, "CRITICAL", "TRUNCATE", f"TRUNCATE {tbl} deletes all rows, is DDL (auto-commit) and "
                             "cannot be rolled back.", "Back up the data first (CTAS to a _BKP table) and generate a restore rollback."))
        return f, f"Removes all rows from {tbl} (irreversible, auto-commits)."

    if k == M.ADD_COLUMN:
        cols = d.get("columns", [])
        names = ", ".join(f"{c.name} {c.data_type}".strip() for c in cols)
        impact = f"Adds column(s) {names} to {tbl}."
        for c in cols:
            if c.nullable is False and c.default is None and not new_tbl:
                f.append(ctx.finding(op, "HIGH", "ADD_NOT_NULL_NO_DEFAULT", f"{tbl}.{c.name} is NOT NULL without DEFAULT - "
                                     "fails if the table already has rows.",
                                     "Add as NULL, backfill in a DML changeset, then add the NOT NULL constraint."))
            elif c.nullable is False and c.default is not None and not new_tbl:
                msg = {"oracle": "Oracle 11g+ adds NOT NULL DEFAULT as metadata-only (fast).",
                       "postgresql": "PostgreSQL 11+ adds non-volatile defaults without a table rewrite.",
                       "mysql": "MySQL < 8.0.12 rebuilds the table (use ALGORITHM=INSTANT on 8.0+).",
                       "mariadb": "MariaDB 10.3+ supports instant ADD COLUMN.",
                       "mssql": "SQL Server Enterprise adds NOT NULL DEFAULT as metadata-only; Standard rewrites."}[ctx.dialect]
                f.append(ctx.finding(op, "INFO", "ADD_NOT_NULL_DEFAULT", msg))
            if c.primary_key or c.unique:
                f.append(ctx.finding(op, "MEDIUM", "ADD_COLUMN_UNIQUE", f"{c.name} adds a unique/PK index on an existing table.",
                                     "Ensure values will be unique; build during low traffic."))
        if not new_tbl:
            f.append(ctx.finding(op, "LOW", "APP_COMPAT_ADD", f"Applications using SELECT * or positional INSERT on {tbl} "
                                 "may break.", "Verify no positional INSERT/SELECT * usage in application code."))
        return f, impact

    if k == M.MODIFY_COLUMN:
        before = res.get("before") or {}
        parts = []
        for c in d.get("columns", []):
            old = before.get((d.get("old_name") or c.name).upper())
            desc = []
            if d.get("rename"):
                desc.append(f"renames {d['old_name']} -> {c.name}")
            if c.data_type:
                desc.append(f"type {(old.data_type + ' -> ') if old and old.data_type else ''}{c.data_type}")
                verdict, detail = compare_types(old.data_type if old else "", c.data_type)
                if verdict == "NARROW":
                    f.append(ctx.finding(op, "HIGH", "TYPE_NARROW", f"{tbl}.{c.name}: {detail} - fails or truncates "
                                         "if existing data exceeds the new size.", "Run the max-length pre-check below."))
                elif verdict == "CHANGE":
                    f.append(ctx.finding(op, "HIGH", "TYPE_CHANGE", f"{tbl}.{c.name}: {detail}. Oracle requires the column "
                                         "to be empty for most type changes; PostgreSQL rewrites the table.",
                                         "Use add-new-column / copy / swap (expand-contract) pattern."))
                elif verdict == "UNKNOWN" and not new_tbl:
                    f.append(ctx.finding(op, "MEDIUM", "TYPE_UNKNOWN_OLD", f"Current type of {tbl}.{c.name} is unknown - "
                                         "cannot verify narrowing or generate an exact rollback.",
                                         "Supply the current DDL via --baseline."))
                if ctx.dialect in ("mysql", "mariadb"):
                    f.append(ctx.finding(op, "HIGH", "MYSQL_MODIFY_RESETS", "MySQL MODIFY/CHANGE replaces the whole column "
                                         "definition - DEFAULT, NOT NULL, COMMENT and charset not restated are lost.",
                                         "Restate the full column definition."))
                if ctx.dialect == "postgresql":
                    f.append(ctx.finding(op, "MEDIUM", "PG_TYPE_REWRITE", "ALTER COLUMN TYPE takes an ACCESS EXCLUSIVE lock and "
                                         "may rewrite the table.", "Run in a maintenance window; set lock_timeout."))
            if c.nullable is False:
                desc.append("sets NOT NULL")
                if not new_tbl:
                    f.append(ctx.finding(op, "HIGH", "SET_NOT_NULL", f"Making {tbl}.{c.name} NOT NULL fails if any row "
                                         "contains NULL and scans the full table under lock.",
                                         "Run the NULL-count pre-check; backfill first. Oracle: ADD CONSTRAINT ... CHECK "
                                         "(col IS NOT NULL) NOVALIDATE then VALIDATE to reduce locking."))
            elif c.nullable is True:
                desc.append("makes column NULLABLE")
                f.append(ctx.finding(op, "MEDIUM", "SET_NULLABLE", f"{tbl}.{c.name} becomes nullable. Rollback "
                                     "(back to NOT NULL) will fail once NULL rows are written.",
                                     "Rollback must clean/backfill NULL rows before re-applying NOT NULL."))
            if c.default is not None:
                desc.append(f"default {c.default}")
            parts.append(f"{c.name}: " + ", ".join(desc or ["redefined"]))
        if d.get("drop_default"):
            parts.append("drops column default")
        return f, f"Modifies {tbl} - " + "; ".join(parts) + "."

    if k == M.DROP_COLUMN:
        cols = d.get("columns", [])
        impl = res.get("implicit") or {}
        impact = f"Drops column(s) {', '.join(cols)} from {tbl} - data in these columns is permanently lost."
        if d.get("set_unused"):
            impact = f"Marks column(s) {', '.join(cols)} on {tbl} UNUSED (logically dropped, irreversible)."
        f.append(ctx.finding(op, "HIGH", "DROP_COLUMN", f"Dropping {', '.join(cols)} from {tbl} destroys data; "
                             "rollback can restore structure but NOT the data.",
                             "Back up the column data (CREATE TABLE ..._BKP AS SELECT pk, cols) before deploying."))
        if impl.get("constraints") or impl.get("indexes"):
            names = list(impl.get("constraints", {}).keys()) + [x.split(".")[-1] for x in impl.get("indexes", {})]
            f.append(ctx.finding(op, "HIGH", "IMPLICIT_DROPS", "Also implicitly drops: " + ", ".join(names),
                                 "Rollback re-creates them (generated). Check no FK relies on a dropped index."))
        elif d.get("cascade"):
            f.append(ctx.finding(op, "MEDIUM", "CASCADE_CONSTRAINTS", "CASCADE CONSTRAINTS drops any constraint "
                                 "referencing the column(s); without a baseline the exact list is unknown.",
                                 "Supply --baseline so rollback can re-create them."))
        if ctx.dialect == "oracle" and not new_tbl and not d.get("set_unused"):
            f.append(ctx.finding(op, "MEDIUM", "ORA_DROP_COLUMN_REWRITE", "Oracle DROP COLUMN rewrites every block of the "
                                 "table (long-running, generates undo/redo).",
                                 "For large tables: ALTER TABLE ... SET UNUSED (instant) now, DROP UNUSED COLUMNS "
                                 "CHECKPOINT 10000 off-peak."))
        f.append(ctx.finding(op, "MEDIUM", "APP_COMPAT_DROP", "Application code / ORM mappings still referencing the "
                             "column will fail after deploy.", "Deploy code that stops using the column first (expand/contract)."))
        return f, impact

    if k in (M.RENAME_COLUMN, M.RENAME_TABLE):
        what = f"column {d.get('column')} -> {d.get('new_name')}" if k == M.RENAME_COLUMN else f"table -> {d.get('new_name')}"
        f.append(ctx.finding(op, "HIGH", "RENAME", f"Renaming {what} on {tbl} breaks application SQL, views, "
                             "synonyms and PL/SQL referencing the old name.",
                             "Coordinate with application release; recompile invalid objects after deploy."))
        return f, f"Renames {what} on {tbl}."

    if k == M.ADD_CONSTRAINT:
        c = d.get("constraint")
        if not isinstance(c, M.Constraint):
            return f, f"Adds a constraint on {tbl}."
        impact = f"Adds {c.ctype} constraint {c.name or ''} on {tbl} ({', '.join(c.columns) or c.check_expr or ''})."
        if c.ctype == "FOREIGN KEY":
            impact += f" References {c.ref_table} ({', '.join(c.ref_columns)})."
        if not new_tbl:
            if c.ctype == "FOREIGN KEY" and d.get("validate", True):
                rec = {"oracle": "ADD ... ENABLE NOVALIDATE, then ALTER TABLE ... ENABLE VALIDATE CONSTRAINT off-peak.",
                       "postgresql": "ADD ... NOT VALID, then VALIDATE CONSTRAINT in a later changeset.",
                       }.get(ctx.dialect, "Run the orphan-row pre-check; deploy off-peak.")
                f.append(ctx.finding(op, "MEDIUM", "FK_VALIDATION", f"Validating {c.name} scans {tbl} and locks it; fails "
                                     "if orphan rows exist.", rec))
            if c.ctype in ("PRIMARY KEY", "UNIQUE"):
                f.append(ctx.finding(op, "MEDIUM", "UNIQUE_ON_EXISTING", f"{c.ctype} {c.name} builds an index on existing "
                                     "data and fails on duplicates.", "Run the duplicate pre-check below."))
            if c.ctype == "CHECK":
                f.append(ctx.finding(op, "MEDIUM", "CHECK_ON_EXISTING", f"CHECK {c.name} validates all existing rows.",
                                     "Run the violation pre-check below."))
        return f, impact

    if k == M.DROP_CONSTRAINT:
        con = res.get("before")
        name = d.get("constraint_name") or d.get("ctype")
        ctype = con.ctype if con else (d.get("ctype") or _guess_ctype(name, ctx.profile))
        impact = f"Drops {ctype or 'constraint'} {name} from {tbl}."
        if ctype == "FOREIGN KEY":
            f.append(ctx.finding(op, "MEDIUM", "DROP_FK", f"Referential integrity enforced by {name} is removed - orphan "
                                 "rows can be created; re-adding it on rollback will then fail.",
                                 "Rollback must clean orphans first (see generated rollback notes)."))
        elif ctype in ("PRIMARY KEY", "UNIQUE"):
            f.append(ctx.finding(op, "HIGH", "DROP_PK_UK", f"Dropping {ctype} {name} also drops its index (unless KEEP INDEX) "
                                 "and fails if foreign keys reference it.", "Check referencing FKs in pre-check."))
        else:
            f.append(ctx.finding(op, "MEDIUM", "DROP_CONSTRAINT", f"Data rule {name} is no longer enforced."))
        if con is None:
            f.append(ctx.finding(op, "MEDIUM", "DROP_CONS_NO_BASELINE", f"Definition of {name} unknown - rollback "
                                 "re-creation must be completed manually.", "Supply --baseline DDL.", "rollback"))
        return f, impact

    if k == M.ALTER_TABLE_RAW:
        f.append(ctx.finding(op, "MEDIUM", "ALTER_RAW", f"ALTER TABLE action '{d.get('action')}' is passed through as raw "
                             "SQL; rollback must be written manually.", "Review and add an explicit rollback."))
        return f, f"Alters {tbl}: {d.get('action_text', '')[:120]}"
    return f, ""


def _guess_ctype(name: str, profile: dict) -> str:
    n = (name or "").upper()
    rules = profile.get("naming", {}).get("prefixes", {})
    for ctype, key in (("PRIMARY KEY", "primary_key"), ("FOREIGN KEY", "foreign_key"), ("UNIQUE", "unique"),
                       ("CHECK", "check")):
        p = (rules.get(key) or "").upper()
        if p and n.startswith(p):
            return ctype
    if n.startswith("FK"):
        return "FOREIGN KEY"
    if n.startswith("PK"):
        return "PRIMARY KEY"
    if n.startswith(("UK", "UQ")):
        return "UNIQUE"
    if n.startswith(("CK", "CHK")):
        return "CHECK"
    return ""


def _ts(prof, op):
    return prof.get("tablespace", {}).get("default_data", "<TABLESPACE>").format(schema=op.schema or "")
