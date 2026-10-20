"""Risk + impact rules for indexes and sequences."""
from __future__ import annotations

from typing import List, Tuple

from core import models as M
from analyzers.context import AnalysisContext


def before_apply(op: M.Operation, ctx: AnalysisContext) -> List[M.Finding]:
    """Checks needing the schema state *before* the index is registered."""
    f = []
    if op.kind == M.CREATE_INDEX:
        cols = [c["name"] for c in op.details.get("columns", []) if not c.get("expression")]
        if cols:
            cover = ctx.schema.covering_index(op.details.get("table_schema") or op.schema, op.table, cols)
            if cover and cover.upper() != op.name.upper():
                f.append(ctx.finding(op, "LOW", "REDUNDANT_INDEX", f"Index {op.name} ({', '.join(cols)}) duplicates the "
                                     f"leading columns of existing index/constraint {cover}.",
                                     "Remove the redundant index - it adds DML overhead with no read benefit."))
    return f


def analyze(op: M.Operation, res: dict, ctx: AnalysisContext) -> Tuple[List[M.Finding], str]:
    f: List[M.Finding] = []
    d = op.details
    if op.kind == M.CREATE_INDEX:
        cols = ", ".join(("" if not c.get("descending") else "") + c["name"] + (" DESC" if c.get("descending") else "")
                         for c in d.get("columns", []))
        kind = "UNIQUE index" if d.get("unique") else ("BITMAP index" if d.get("bitmap") else "index")
        tbl = f"{(d.get('table_schema') or op.schema) + '.' if (d.get('table_schema') or op.schema) else ''}{op.table}"
        impact = f"Creates {kind} {op.qualified} on {tbl} ({cols})"
        if d.get("tablespace"):
            impact += f" in tablespace {d['tablespace']}"
        new_tbl = ctx.is_new_table(d.get("table_schema") or op.schema, op.table)
        impact += ". " + ("Table is new in this release - no lock impact." if new_tbl else
                          "Index build reads the whole table; DML may be blocked during the build.")
        if not new_tbl:
            if ctx.dialect == "oracle" and not d.get("online"):
                f.append(ctx.finding(op, "MEDIUM", "INDEX_LOCK", f"CREATE INDEX on existing table {op.table} without ONLINE "
                                     "takes a table lock that blocks DML for the duration of the build.",
                                     "Add ONLINE (Enterprise Edition) or deploy in a low-traffic window."))
            if ctx.dialect == "postgresql" and not d.get("concurrently"):
                f.append(ctx.finding(op, "MEDIUM", "INDEX_LOCK", "CREATE INDEX without CONCURRENTLY blocks writes on "
                                     f"{op.table}.", "Use CREATE INDEX CONCURRENTLY (changeSet runInTransaction=\"false\")."))
            if ctx.dialect in ("mysql", "mariadb") and not d.get("online"):
                f.append(ctx.finding(op, "LOW", "INDEX_LOCK", "InnoDB builds secondary indexes online by default, but "
                                     "metadata locks can queue behind long transactions.",
                                     "Append ALGORITHM=INPLACE, LOCK=NONE and set lock_wait_timeout."))
            if ctx.dialect == "mssql" and not d.get("online"):
                f.append(ctx.finding(op, "MEDIUM", "INDEX_LOCK", "Index build without ONLINE = ON blocks writes.",
                                     "Use WITH (ONLINE = ON) on Enterprise / Azure SQL."))
            if d.get("unique"):
                f.append(ctx.finding(op, "MEDIUM", "UNIQUE_INDEX_EXISTING", f"Unique index on existing data fails if "
                                     "duplicates exist.", "Run the duplicate pre-check."))
        if d.get("concurrently"):
            f.append(ctx.finding(op, "INFO", "CONCURRENTLY", "CREATE INDEX CONCURRENTLY cannot run inside a transaction - "
                                 "changeSet is generated with runInTransaction=\"false\"; a failed build leaves an INVALID index."))
        if d.get("bitmap"):
            f.append(ctx.finding(op, "MEDIUM", "BITMAP_OLTP", "Bitmap indexes cause severe lock contention under concurrent "
                                 "DML.", "Use bitmap indexes only on read-mostly / DW tables."))
        if d.get("functional"):
            f.append(ctx.finding(op, "INFO", "FUNCTION_INDEX", "Function-based index emitted as <sql> (no native Liquibase "
                                 "change type)."))
        if ctx.dialect == "oracle" and not d.get("tablespace") and ctx.profile.get("tablespace", {}).get("enforce"):
            f.append(ctx.finding(op, "LOW", "NO_TABLESPACE", f"Index {op.name} has no TABLESPACE clause."))
        tbl_def = ctx.schema.table(d.get("table_schema") or op.schema, op.table)
        if tbl_def and tbl_def.columns:
            missing = [c["name"] for c in d.get("columns", []) if not c.get("expression")
                       and c["name"].upper() not in tbl_def.columns]
            if missing:
                f.append(ctx.finding(op, "HIGH", "INDEX_COL_MISSING", f"Index column(s) {', '.join(missing)} do not exist on "
                                     f"{op.table} at this point in the release.", "Fix column names or statement order.", "conflict"))
        return f, impact

    if op.kind == M.DROP_INDEX:
        before = res.get("before")
        impact = f"Drops index {op.qualified}" + (f" on {before['table_key']} ({', '.join(before['columns'])})" if before else "") + "."
        f.append(ctx.finding(op, "MEDIUM", "DROP_INDEX", "Queries relying on this index may regress to full scans.",
                             "Check execution plans / AWR for statements using the index before dropping."))
        if before:
            tkey = before["table_key"]
            t = ctx.schema.tables.get(tkey)
            if t:
                for c in t.constraints.values():
                    if c.ctype == "FOREIGN KEY" and [x.upper() for x in c.columns] == [x.upper() for x in before["columns"][:len(c.columns)]]:
                        f.append(ctx.finding(op, "HIGH", "DROP_FK_INDEX", f"Index supports FK {c.name}; without it, parent "
                                             "DELETE/UPDATE causes full scans and child-table locks.", "Keep the index."))
        else:
            f.append(ctx.finding(op, "LOW", "DROP_INDEX_NO_BASELINE", "Index definition unknown - rollback cannot recreate it "
                                 "exactly.", "Supply --baseline DDL.", "rollback"))
        return f, impact

    if op.kind == M.CREATE_SEQUENCE:
        impact = f"Creates sequence {op.qualified} (start {d.get('start') or 1}, increment {d.get('increment') or 1}" + \
                 (", NOCACHE" if d.get("cache") == "0" else (f", cache {d['cache']}" if d.get("cache") else "")) + ")."
        if d.get("cache") == "0":
            f.append(ctx.finding(op, "LOW", "SEQ_NOCACHE", f"{op.name} is NOCACHE - every NEXTVAL updates the data dictionary; "
                                 "contention under high insert rates / RAC.", "Use CACHE 20+ (NOORDER) unless gap-free ids are mandated."))
        if d.get("start") and str(d["start"]) not in ("1", "0") and ctx.profile.get("warn_hardcoded_sequence_start", True):
            f.append(ctx.finding(op, "LOW", "SEQ_HARDCODED_START", f"Sequence starts at {d['start']} - value may be "
                                 "environment specific.", "Derive START WITH from MAX(id)+1 per environment or use a "
                                 "Liquibase property.", "best_practice"))
        return f, impact

    if op.kind == M.DROP_SEQUENCE:
        f.append(ctx.finding(op, "HIGH", "DROP_SEQUENCE", "Dropping a sequence breaks triggers/code using NEXTVAL; recreating "
                             "it resets the current value.", "Rollback recreates it starting above the current max id."))
        return f, f"Drops sequence {op.qualified}."
    if op.kind == M.ALTER_SEQUENCE:
        return f, f"Alters sequence {op.qualified}."
    return f, ""
