"""Pre-check / post-check SQL generation (read-only queries, per dialect)."""
from __future__ import annotations

from typing import List, Optional

from core import models as M


def _lit(s):
    return "'" + (s or "").replace("'", "''") + "'"


class CheckGenerator:
    def __init__(self, dialect: str, profile: dict, schema_model):
        self.d = dialect
        self.p = profile
        self.sm = schema_model
        self.dict = profile.get("oracle_dictionary_prefix", "ALL")

    # ------------------------------------------------------------- primitives
    def _own(self, schema) -> str:
        if schema:
            s = schema.upper() if self.d == "oracle" else schema
            return _lit(s)
        return {"oracle": "SYS_CONTEXT('USERENV','CURRENT_SCHEMA')", "postgresql": "current_schema()",
                "mysql": "DATABASE()", "mariadb": "DATABASE()", "mssql": "SCHEMA_NAME()"}[self.d]

    def _n(self, name) -> str:
        return _lit(name.upper() if self.d == "oracle" else name)

    def q(self, schema, name):
        return f"{schema}.{name}" if schema else name

    def exists(self, otype: str, schema, name, table=None) -> str:
        o, n, D = self._own(schema), self._n(name), self.dict
        t = otype.upper()
        if self.d == "oracle":
            m = {"TABLE": f"SELECT COUNT(*) FROM {D}_TABLES WHERE OWNER = {o} AND TABLE_NAME = {n}",
                 "INDEX": f"SELECT COUNT(*) FROM {D}_INDEXES WHERE OWNER = {o} AND INDEX_NAME = {n}",
                 "SEQUENCE": f"SELECT COUNT(*) FROM {D}_SEQUENCES WHERE SEQUENCE_OWNER = {o} AND SEQUENCE_NAME = {n}",
                 "CONSTRAINT": f"SELECT COUNT(*) FROM {D}_CONSTRAINTS WHERE OWNER = {o} AND CONSTRAINT_NAME = {n}"}
            return m.get(t, f"SELECT COUNT(*) FROM {D}_OBJECTS WHERE OWNER = {o} AND OBJECT_NAME = {n} AND OBJECT_TYPE = {_lit(t)}")
        if self.d == "postgresql":
            m = {"TABLE": f"SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = {o} AND table_name = {n}",
                 "INDEX": f"SELECT COUNT(*) FROM pg_indexes WHERE schemaname = {o} AND indexname = {n}",
                 "SEQUENCE": f"SELECT COUNT(*) FROM information_schema.sequences WHERE sequence_schema = {o} AND sequence_name = {n}",
                 "VIEW": f"SELECT COUNT(*) FROM information_schema.views WHERE table_schema = {o} AND table_name = {n}",
                 "TRIGGER": f"SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema = {o} AND trigger_name = {n}",
                 "CONSTRAINT": f"SELECT COUNT(*) FROM information_schema.table_constraints WHERE constraint_schema = {o} AND constraint_name = {n}"}
            return m.get(t, f"SELECT COUNT(*) FROM information_schema.routines WHERE routine_schema = {o} AND routine_name = {n}")
        if self.d in ("mysql", "mariadb"):
            m = {"TABLE": f"SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = {o} AND TABLE_NAME = {n} AND TABLE_TYPE = 'BASE TABLE'",
                 "INDEX": f"SELECT COUNT(DISTINCT INDEX_NAME) FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = {o} AND INDEX_NAME = {n}" +
                          (f" AND TABLE_NAME = {_lit(table)}" if table else ""),
                 "VIEW": f"SELECT COUNT(*) FROM information_schema.VIEWS WHERE TABLE_SCHEMA = {o} AND TABLE_NAME = {n}",
                 "TRIGGER": f"SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA = {o} AND TRIGGER_NAME = {n}",
                 "SEQUENCE": f"SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA = {o} AND TABLE_NAME = {n} AND TABLE_TYPE = 'SEQUENCE'",
                 "CONSTRAINT": f"SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA = {o} AND CONSTRAINT_NAME = {n}"}
            return m.get(t, f"SELECT COUNT(*) FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA = {o} AND ROUTINE_NAME = {n}")
        # mssql
        code = {"TABLE": "U", "VIEW": "V", "TRIGGER": "TR", "PROCEDURE": "P", "FUNCTION": "FN", "SEQUENCE": "SO"}.get(t)
        if t == "INDEX":
            return (f"SELECT COUNT(*) FROM sys.indexes WHERE name = {n} AND object_id = OBJECT_ID({_lit(self.q(schema, table))})")
        if t == "CONSTRAINT":
            return f"SELECT COUNT(*) FROM sys.objects WHERE name = {n} AND type IN ('PK','UQ','F','C','D')"
        if code:
            return f"SELECT CASE WHEN OBJECT_ID({_lit(self.q(schema, name))}, {_lit(code)}) IS NULL THEN 0 ELSE 1 END"
        return f"SELECT COUNT(*) FROM sys.objects WHERE name = {n}"

    def column_exists(self, schema, table, col) -> str:
        o, t, c = self._own(schema), self._n(table), self._n(col)
        if self.d == "oracle":
            return f"SELECT COUNT(*) FROM {self.dict}_TAB_COLUMNS WHERE OWNER = {o} AND TABLE_NAME = {t} AND COLUMN_NAME = {c}"
        if self.d == "mssql":
            return f"SELECT CASE WHEN COL_LENGTH({_lit(self.q(schema, table))}, {_lit(col)}) IS NULL THEN 0 ELSE 1 END"
        return f"SELECT COUNT(*) FROM information_schema.columns WHERE table_schema = {o} AND table_name = {t} AND column_name = {c}"

    def column_def(self, schema, table, cols: List[str]) -> str:
        o, t = self._own(schema), self._n(table)
        inl = ", ".join(self._n(c) for c in cols)
        if self.d == "oracle":
            return (f"SELECT COLUMN_NAME, DATA_TYPE, DATA_LENGTH, DATA_PRECISION, DATA_SCALE, NULLABLE, DATA_DEFAULT "
                    f"FROM {self.dict}_TAB_COLUMNS WHERE OWNER = {o} AND TABLE_NAME = {t} AND COLUMN_NAME IN ({inl})")
        if self.d == "mssql":
            return (f"SELECT c.name, ty.name AS data_type, c.max_length, c.precision, c.scale, c.is_nullable FROM sys.columns c "
                    f"JOIN sys.types ty ON ty.user_type_id = c.user_type_id WHERE c.object_id = OBJECT_ID({_lit(self.q(schema, table))}) "
                    f"AND c.name IN ({inl})")
        return (f"SELECT column_name, data_type, character_maximum_length, numeric_precision, numeric_scale, is_nullable, "
                f"column_default FROM information_schema.columns WHERE table_schema = {o} AND table_name = {t} "
                f"AND column_name IN ({inl})")

    def invalid_objects(self, schema) -> Optional[str]:
        o = self._own(schema)
        if self.d == "oracle":
            return f"SELECT OBJECT_TYPE, OBJECT_NAME, STATUS FROM {self.dict}_OBJECTS WHERE OWNER = {o} AND STATUS <> 'VALID' ORDER BY OBJECT_TYPE, OBJECT_NAME"
        if self.d == "postgresql":
            return f"SELECT indexrelid::regclass AS invalid_index FROM pg_index WHERE NOT indisvalid"
        return None

    def errors(self, schema, name) -> Optional[str]:
        if self.d == "oracle":
            return (f"SELECT TYPE, LINE, POSITION, TEXT FROM {self.dict}_ERRORS WHERE OWNER = {self._own(schema)} "
                    f"AND NAME = {self._n(name)} ORDER BY SEQUENCE")
        return None

    def dependents(self, schema, name) -> Optional[str]:
        if self.d == "oracle":
            return (f"SELECT OWNER, NAME, TYPE FROM {self.dict}_DEPENDENCIES WHERE REFERENCED_OWNER = {self._own(schema)} "
                    f"AND REFERENCED_NAME = {self._n(name)} ORDER BY TYPE, NAME")
        if self.d == "postgresql":
            return (f"SELECT DISTINCT dependent_view.relname AS dependent FROM pg_depend JOIN pg_rewrite ON pg_depend.objid = pg_rewrite.oid "
                    f"JOIN pg_class dependent_view ON pg_rewrite.ev_class = dependent_view.oid JOIN pg_class src ON pg_depend.refobjid = src.oid "
                    f"WHERE src.relname = {_lit(name)}")
        if self.d in ("mysql", "mariadb"):
            return (f"SELECT TABLE_NAME FROM information_schema.VIEWS WHERE TABLE_SCHEMA = {self._own(schema)} "
                    f"AND VIEW_DEFINITION LIKE {_lit('%' + name + '%')}")
        return (f"SELECT referencing_schema_name, referencing_entity_name FROM sys.dm_sql_referencing_entities("
                f"{_lit(self.q(schema, name))}, 'OBJECT')")

    def locks(self, schema, table) -> Optional[str]:
        if self.d == "oracle":
            return ("SELECT s.SID, s.SERIAL#, s.USERNAME, s.PROGRAM, s.STATUS, lo.LOCKED_MODE FROM V$LOCKED_OBJECT lo "
                    "JOIN DBA_OBJECTS o ON o.OBJECT_ID = lo.OBJECT_ID JOIN V$SESSION s ON s.SID = lo.SESSION_ID "
                    f"WHERE o.OWNER = {self._own(schema)} AND o.OBJECT_NAME = {self._n(table)}")
        if self.d == "postgresql":
            return (f"SELECT l.pid, a.usename, a.state, l.mode, a.query FROM pg_locks l JOIN pg_stat_activity a ON a.pid = l.pid "
                    f"WHERE l.relation = {_lit(self.q(schema, table))}::regclass")
        if self.d in ("mysql", "mariadb"):
            return "SELECT * FROM information_schema.INNODB_TRX ORDER BY trx_started"
        return (f"SELECT request_session_id, request_mode, request_status FROM sys.dm_tran_locks "
                f"WHERE resource_associated_entity_id = OBJECT_ID({_lit(self.q(schema, table))})")

    def row_count(self, schema, table, where=None) -> str:
        return f"SELECT COUNT(*) FROM {self.q(schema, table)}" + (f" WHERE {where}" if where else "")

    # ------------------------------------------------------------- per operation
    def for_operation(self, op: M.Operation, res: dict) -> dict:
        pre, post = [], []
        P = lambda sql, exp, why: pre.append({"sql": sql, "expect": exp, "purpose": why})
        Q = lambda sql, exp, why: post.append({"sql": sql, "expect": exp, "purpose": why})
        k, d, s = op.kind, op.details, op.schema
        tbl = op.table or op.name
        tschema = d.get("table_schema") or s
        if k in (M.CREATE_TABLE, M.CREATE_TABLE_AS):
            P(self.exists("TABLE", s, op.name), "0", f"{op.qualified} must not exist yet")
            Q(self.exists("TABLE", s, op.name), "1", f"{op.qualified} created")
            cols = [c.name for c in d.get("columns", [])]
            if cols:
                Q(self.column_def(s, op.name, cols), f"{len(cols)} rows", "Column definitions as designed")
            if self.d == "oracle":
                Q(f"SELECT CONSTRAINT_NAME, CONSTRAINT_TYPE, STATUS, VALIDATED FROM {self.dict}_CONSTRAINTS WHERE OWNER = "
                  f"{self._own(s)} AND TABLE_NAME = {self._n(op.name)} ORDER BY CONSTRAINT_TYPE", "all ENABLED/VALIDATED",
                  "Constraints enabled")
                Q(f"SELECT GRANTEE, PRIVILEGE FROM {self.dict}_TAB_PRIVS WHERE TABLE_SCHEMA = {self._own(s)} AND TABLE_NAME = "
                  f"{self._n(op.name)} ORDER BY GRANTEE", "expected roles", "Grants applied")
            for c in d.get("constraints", []):
                if c.ctype == "FOREIGN KEY" and c.ref_table:
                    P(self.exists("TABLE", c.ref_schema or s, c.ref_table), "1", f"FK parent {c.ref_table} exists")
        elif k == M.DROP_TABLE:
            P(self.exists("TABLE", s, op.name), "1", "Table exists")
            P(self.row_count(s, op.name), "record value", "Row count to be lost - confirm backup taken")
            dep = self.dependents(s, op.name)
            if dep:
                P(dep, "review", "Objects depending on the table")
            Q(self.exists("TABLE", s, op.name), "0", "Table dropped")
        elif k == M.TRUNCATE_TABLE:
            P(self.row_count(s, tbl), "record value", "Rows to be removed")
            Q(self.row_count(s, tbl), "0", "Table empty")
        elif k == M.ADD_COLUMN:
            for c in d.get("columns", []):
                P(self.column_exists(s, tbl, c.name), "0", f"{tbl}.{c.name} must not exist yet")
                Q(self.column_exists(s, tbl, c.name), "1", f"{tbl}.{c.name} added")
                if c.nullable is False:
                    P(self.row_count(s, tbl), "0 (or DEFAULT supplied)", "NOT NULL add needs empty table or default")
                    Q(self.row_count(s, tbl, f"{c.name} IS NULL"), "0", f"No NULLs in {c.name}")
            Q(self.column_def(s, tbl, [c.name for c in d.get("columns", [])]), "as designed", "New column definition")
        elif k == M.MODIFY_COLUMN:
            for c in d.get("columns", []):
                P(self.column_def(s, tbl, [d.get("old_name") or c.name]), "record value", "Current definition (rollback reference)")
                if c.nullable is False:
                    P(self.row_count(s, tbl, f"{c.name} IS NULL"), "0", f"NULLs would block NOT NULL on {c.name}")
                if c.data_type and any(x in c.data_type.upper() for x in ("CHAR", "TEXT")):
                    fn = "LENGTH" if self.d in ("oracle", "postgresql", "mysql", "mariadb") else "LEN"
                    P(f"SELECT MAX({fn}({c.name})) FROM {self.q(s, tbl)}", f"<= new length of {c.data_type}",
                      "Longest existing value fits new size")
                if c.data_type and any(x in c.data_type.upper() for x in ("NUMBER", "NUMERIC", "DECIMAL", "INT")):
                    P(f"SELECT MIN({c.name}), MAX({c.name}) FROM {self.q(s, tbl)}", f"fits {c.data_type}",
                      "Existing values fit new precision")
                Q(self.column_def(s, tbl, [c.name]), "as designed", "New definition applied")
            dep = self.dependents(s, tbl)
            if dep:
                P(dep, "review", "Dependent objects that will be invalidated")
        elif k == M.DROP_COLUMN:
            cols = d.get("columns", [])
            for c in cols:
                P(self.column_exists(s, tbl, c), "1", f"{tbl}.{c} exists")
                Q(self.column_exists(s, tbl, c), "0", f"{tbl}.{c} dropped")
            P(self.row_count(s, tbl, " OR ".join(f"{c} IS NOT NULL" for c in cols)), "record value",
              "Rows holding data that will be lost")
            dep = self.dependents(s, tbl)
            if dep:
                P(dep, "review", "Dependent views/triggers/PLSQL referencing the table")
            if self.d == "oracle":
                P(f"SELECT c.CONSTRAINT_NAME, c.CONSTRAINT_TYPE FROM {self.dict}_CONS_COLUMNS cc JOIN {self.dict}_CONSTRAINTS c "
                  f"ON c.OWNER = cc.OWNER AND c.CONSTRAINT_NAME = cc.CONSTRAINT_NAME WHERE cc.OWNER = {self._own(s)} AND "
                  f"cc.TABLE_NAME = {self._n(tbl)} AND cc.COLUMN_NAME IN ({', '.join(self._n(c) for c in cols)})",
                  "review", "Constraints removed by CASCADE CONSTRAINTS")
                P(f"SELECT INDEX_NAME, COLUMN_NAME FROM {self.dict}_IND_COLUMNS WHERE TABLE_OWNER = {self._own(s)} AND TABLE_NAME = "
                  f"{self._n(tbl)} AND COLUMN_NAME IN ({', '.join(self._n(c) for c in cols)})", "review",
                  "Indexes that Oracle drops with the column")
        elif k in (M.RENAME_COLUMN, M.RENAME_TABLE):
            dep = self.dependents(s, tbl)
            if dep:
                P(dep, "review", "Objects referencing the old name")
            if k == M.RENAME_COLUMN:
                Q(self.column_exists(s, tbl, d["new_name"]), "1", "Renamed column present")
            else:
                Q(self.exists("TABLE", s, d["new_name"]), "1", "Renamed table present")
        elif k == M.ADD_CONSTRAINT:
            c = d.get("constraint")
            if isinstance(c, M.Constraint):
                if c.name:
                    P(self.exists("CONSTRAINT", s, c.name), "0", f"Constraint name {c.name} free")
                    Q(self.exists("CONSTRAINT", s, c.name), "1", f"Constraint {c.name} created")
                cols = ", ".join(c.columns)
                if c.ctype in ("PRIMARY KEY", "UNIQUE") and c.columns:
                    P(f"SELECT {cols}, COUNT(*) FROM {self.q(s, tbl)} GROUP BY {cols} HAVING COUNT(*) > 1", "0 rows",
                      "No duplicates")
                if c.ctype == "PRIMARY KEY":
                    P(self.row_count(s, tbl, " OR ".join(f"{x} IS NULL" for x in c.columns)), "0", "No NULL key values")
                if c.ctype == "FOREIGN KEY" and c.columns:
                    on = " AND ".join(f"p.{pc} = c.{cc}" for cc, pc in zip(c.columns, c.ref_columns or c.columns))
                    nn = " AND ".join(f"c.{cc} IS NOT NULL" for cc in c.columns)
                    P(f"SELECT COUNT(*) FROM {self.q(s, tbl)} c WHERE {nn} AND NOT EXISTS (SELECT 1 FROM "
                      f"{self.q(c.ref_schema or s, c.ref_table)} p WHERE {on})", "0", "No orphan child rows")
                    if not self.sm.covering_index(s, tbl, c.columns):
                        P(f"-- No index found on {tbl} ({cols}) - consider indexing the FK column(s)", "", "FK index advisory")
                if c.ctype == "CHECK" and c.check_expr:
                    P(self.row_count(s, tbl, f"NOT ({c.check_expr})"), "0", "No rows violate the check")
                if self.d == "oracle" and c.name:
                    Q(f"SELECT STATUS, VALIDATED FROM {self.dict}_CONSTRAINTS WHERE OWNER = {self._own(s)} AND CONSTRAINT_NAME = "
                      f"{self._n(c.name)}", "ENABLED / VALIDATED", "Constraint enabled")
        elif k == M.DROP_CONSTRAINT:
            n = d.get("constraint_name")
            if n:
                P(self.exists("CONSTRAINT", s, n), "1", f"{n} exists")
                Q(self.exists("CONSTRAINT", s, n), "0", f"{n} dropped")
                if self.d == "oracle":
                    P(f"SELECT DBMS_METADATA.GET_DDL('{'REF_CONSTRAINT' if _fkish(n) else 'CONSTRAINT'}', {self._n(n)}, "
                      f"{self._own(s)}) FROM DUAL", "save output", "Capture definition for rollback")
        elif k == M.CREATE_INDEX:
            P(self.exists("INDEX", s, op.name, tbl), "0", f"Index {op.name} must not exist")
            P(self.exists("TABLE", tschema, tbl), "1", f"Table {tbl} exists")
            if d.get("unique"):
                cols = ", ".join(c["name"] for c in d.get("columns", []))
                P(f"SELECT {cols}, COUNT(*) FROM {self.q(tschema, tbl)} GROUP BY {cols} HAVING COUNT(*) > 1", "0 rows", "No duplicates")
            if not d.get("_new_table"):
                P(self.row_count(tschema, tbl), "record value", "Table size - estimate build time")
                lk = self.locks(tschema, tbl)
                if lk:
                    P(lk, "no blocking sessions", "Active locks on the table (needs DBA privilege)")
            Q(self.exists("INDEX", s, op.name, tbl), "1", f"Index {op.name} created")
            if self.d == "oracle":
                Q(f"SELECT INDEX_NAME, STATUS, UNIQUENESS, TABLESPACE_NAME FROM {self.dict}_INDEXES WHERE OWNER = {self._own(s)} "
                  f"AND INDEX_NAME = {self._n(op.name)}", "STATUS = VALID", "Index usable")
        elif k == M.DROP_INDEX:
            P(self.exists("INDEX", s, op.name, tbl), "1", f"Index {op.name} exists")
            if self.d == "oracle":
                P(f"SELECT DBMS_METADATA.GET_DDL('INDEX', {self._n(op.name)}, {self._own(s)}) FROM DUAL", "save output",
                  "Capture definition for rollback")
                P(f"SELECT CONSTRAINT_NAME FROM {self.dict}_CONSTRAINTS WHERE OWNER = {self._own(s)} AND INDEX_NAME = "
                  f"{self._n(op.name)}", "0 rows", "Index is not backing a PK/UK constraint")
            Q(self.exists("INDEX", s, op.name, tbl), "0", "Index dropped")
        elif k == M.CREATE_SEQUENCE:
            P(self.exists("SEQUENCE", s, op.name), "0", "Sequence must not exist")
            Q(self.exists("SEQUENCE", s, op.name), "1", "Sequence created")
        elif k == M.DROP_SEQUENCE:
            if self.d == "oracle":
                P(f"SELECT LAST_NUMBER FROM {self.dict}_SEQUENCES WHERE SEQUENCE_OWNER = {self._own(s)} AND SEQUENCE_NAME = "
                  f"{self._n(op.name)}", "record value", "Current value (needed to recreate)")
            Q(self.exists("SEQUENCE", s, op.name), "0", "Sequence dropped")
        elif k in (M.CREATE_VIEW, M.CREATE_TRIGGER, M.CREATE_PROCEDURE, M.CREATE_FUNCTION, M.CREATE_PACKAGE,
                   M.CREATE_PACKAGE_BODY):
            otype = {"CREATE_VIEW": "VIEW", "CREATE_TRIGGER": "TRIGGER", "CREATE_PROCEDURE": "PROCEDURE",
                     "CREATE_FUNCTION": "FUNCTION", "CREATE_PACKAGE": "PACKAGE", "CREATE_PACKAGE_BODY": "PACKAGE BODY"}[k]
            if op.object_type.startswith("TYPE"):
                otype = op.object_type
            if op.object_type == "MATERIALIZED VIEW":
                otype = "MATERIALIZED VIEW"
            if op.or_replace:
                P(self.exists(otype, s, op.name, tbl), "0 = new, 1 = replace", "Is this a replace of an existing object?")
                if self.d == "oracle":
                    gtype = otype.replace(" ", "_")
                    P(f"SELECT DBMS_METADATA.GET_DDL('{gtype}', {self._n(op.name)}, {self._own(s)}) FROM DUAL",
                      "save output", "Capture current source for rollback (if it exists)")
            else:
                P(self.exists(otype, s, op.name, tbl), "0", f"{otype} must not exist")
            if k == M.CREATE_TRIGGER and op.table:
                P(self.exists("TABLE", tschema, op.table), "1", f"Trigger table {op.table} exists")
            Q(self.exists(otype, s, op.name, tbl), "1", f"{otype} {op.name} present")
            if self.d == "oracle":
                Q(f"SELECT OBJECT_NAME, OBJECT_TYPE, STATUS FROM {self.dict}_OBJECTS WHERE OWNER = {self._own(s)} AND "
                  f"OBJECT_NAME = {self._n(op.name)}", "STATUS = VALID", "Compiled without errors")
                e = self.errors(s, op.name)
                Q(e, "0 rows", "No compilation errors")
                if k == M.CREATE_TRIGGER:
                    Q(f"SELECT TRIGGER_NAME, STATUS FROM {self.dict}_TRIGGERS WHERE OWNER = {self._own(s)} AND TRIGGER_NAME = "
                      f"{self._n(op.name)}", "ENABLED", "Trigger enabled")
            if k == M.CREATE_VIEW:
                Q(f"SELECT COUNT(*) FROM {op.qualified} WHERE 1 = 0", "executes", "View is queryable")
        elif k in (M.DROP_VIEW, M.DROP_TRIGGER, M.DROP_ROUTINE):
            otype = {"DROP_VIEW": "VIEW", "DROP_TRIGGER": "TRIGGER"}.get(k, op.object_type)
            if self.d == "oracle":
                P(f"SELECT DBMS_METADATA.GET_DDL('{otype.replace(' ', '_')}', {self._n(op.name)}, {self._own(s)}) FROM DUAL",
                  "save output", "Capture source for rollback")
            dep = self.dependents(s, op.name)
            if dep:
                P(dep, "review", "Dependants")
            Q(self.exists(otype, s, op.name, tbl), "0", "Dropped")
        elif k in (M.INSERT, M.UPDATE, M.DELETE, M.MERGE):
            where = d.get("where")
            P(self.row_count(s, tbl, where), "record value (expected volume)", f"Rows affected by {k}")
            if k == M.INSERT and d.get("columns") and d.get("values") and len(d["columns"]) == len(d["values"]):
                cond = " AND ".join(f"{c} = {v}" for c, v in zip(d["columns"], d["values"])
                                    if v.strip().startswith("'") or v.strip().lstrip("-").replace(".", "").isdigit())
                if cond:
                    P(self.row_count(s, tbl, cond), "0", "Row not already present (idempotency)")
                    Q(self.row_count(s, tbl, cond), "1", "Row inserted")
            elif k == M.UPDATE and d.get("set"):
                Q(self.row_count(s, tbl, where), "same as pre-check", "Rows still matching predicate")
            elif k == M.DELETE:
                Q(self.row_count(s, tbl, where), "0", "Rows removed")
            Q(self.row_count(s, tbl), "pre-count +/- expected delta", "Total row count")
        elif k in (M.GRANT, M.REVOKE) and self.d == "oracle":
            Q(f"SELECT GRANTEE, PRIVILEGE FROM {self.dict}_TAB_PRIVS WHERE TABLE_SCHEMA = {self._own(s)} AND TABLE_NAME = "
              f"{self._n(op.name)} ORDER BY GRANTEE", "grantees listed" if k == M.GRANT else "revoked", "Privileges")
        return {"pre": pre, "post": post}

    def release_post_checks(self, schemas: List[str]) -> List[dict]:
        out = []
        for sc in schemas:
            inv = self.invalid_objects(sc)
            if inv:
                out.append({"sql": inv, "expect": "0 rows (or same as before deploy)", "purpose": f"Invalid objects in {sc or 'current schema'}"})
        if self.d == "oracle":
            out.append({"sql": "SELECT ID, AUTHOR, FILENAME, DATEEXECUTED, EXECTYPE FROM DATABASECHANGELOG ORDER BY ORDEREXECUTED DESC "
                               "FETCH FIRST 30 ROWS ONLY", "expect": "release changeSets EXECUTED", "purpose": "Liquibase history"})
        else:
            out.append({"sql": "SELECT ID, AUTHOR, FILENAME, DATEEXECUTED, EXECTYPE FROM DATABASECHANGELOG ORDER BY ORDEREXECUTED DESC",
                        "expect": "release changeSets EXECUTED", "purpose": "Liquibase history"})
        tr = self.p.get("tracker", {})
        if tr.get("enabled"):
            out.append({"sql": f"SELECT CHANGESET_ID, SCRIPT_NAME, STATUS, COUNT_BEFORE_CHANGE, COUNT_AFTER_CHANGE FROM {tr.get('table')} "
                               f"WHERE RELEASE_NUMBER = '{{release_label}}' ORDER BY CHANGESET_ID",
                        "expect": "all COMPLETED", "purpose": "Change tracker status"})
        return out

    def release_pre_checks(self, schemas: List[str]) -> List[dict]:
        out = []
        for sc in schemas:
            inv = self.invalid_objects(sc)
            if inv:
                out.append({"sql": inv, "expect": "baseline (record)", "purpose": f"Invalid objects BEFORE deploy in {sc}"})
        out.append({"sql": "SELECT * FROM DATABASECHANGELOGLOCK", "expect": "LOCKED = 0/false", "purpose": "No stale Liquibase lock"})
        return out


def _fkish(n):
    return (n or "").upper().startswith("FK")
