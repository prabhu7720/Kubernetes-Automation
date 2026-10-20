"""Rollback generation.

For every operation produce:
  * rollback SQL (used in formatted-SQL --rollback lines and the consolidated rollback script)
  * Liquibase XML rollback change elements
  * completeness flag + notes when a rollback cannot be exact (data loss, unknown BEFORE image)
The BEFORE image comes from the SchemaModel (baseline DDL + earlier statements of the release).
"""
from __future__ import annotations

import re
from typing import List, Optional

from core import models as M
from analyzers.table_analyzer import _guess_ctype
from generators.dialect import Dialect, q
from generators.xml_util import attrs, cdata, el


class RollbackGenerator:
    def __init__(self, dialect: str, schema, profile: dict):
        self.d = Dialect(dialect, profile.get("oracle_drop_cascade", True))
        self.dialect = dialect
        self.schema = schema
        self.profile = profile

    def generate(self, op: M.Operation, res: dict) -> M.Rollback:
        fn = getattr(self, "_rb_" + op.kind.lower(), None)
        if fn is None:
            if op.kind in (M.TX_CONTROL, M.CLIENT_COMMAND, M.TRACKER):
                return M.Rollback(complete=True)
            return M.Rollback(complete=False, notes=[f"No automatic rollback for {op.kind}; write it manually."])
        rb = fn(op, res or {})
        if not rb.xml and rb.sql:
            rb.xml = [self._xml_sql(s) for s in rb.sql]
        return rb

    # ------------------------------------------------------------ helpers
    def _xml_sql(self, s: str, plsql: bool = False) -> str:
        a = {"splitStatements": "false", "stripComments": "false"} if plsql else {}
        if plsql and self.dialect == "oracle":
            a["endDelimiter"] = "\\n/"
        return el("sql", a, cdata(s))

    def _schema_attr(self, op):
        return {"schemaName": op.schema} if op.schema and self.profile.get("xml_schema_attr", True) else {}

    # ------------------------------------------------------------ tables
    def _rb_create_table(self, op, res):
        sql = self.d.drop_table(op.schema, op.name)
        a = {"tableName": op.name, **self._schema_attr(op)}
        if self.dialect in ("oracle", "postgresql"):
            a["cascadeConstraints"] = "true"
        rb = M.Rollback([sql], [el("dropTable", a)])
        if res.get("existed"):
            rb.notes.append("Table already existed before this change - rollback would DROP a pre-existing table. Review!")
            rb.complete = False
        return rb

    _rb_create_table_as = _rb_create_table

    def _rb_drop_table(self, op, res):
        t = res.get("before")
        if not t or not t.columns:
            return M.Rollback(complete=False, notes=[
                f"Cannot recreate {op.qualified}: definition unknown (supply --baseline). Data must be restored from backup "
                "(expdp / FLASHBACK TABLE ... TO BEFORE DROP)."],
                pre_sql=[self.d.ctas_backup(op.schema, op.name, self._bkp(op), None)])
        cols = ",\n    ".join(self.d.coldef(c) for c in t.columns.values())
        cons = [c.definition_sql() if not c.raw else c.raw for c in t.constraints.values()]
        body = ",\n    ".join([cols] + cons) if cons else cols
        ts = f"\nTABLESPACE {t.tablespace}" if t.tablespace and self.dialect == "oracle" else ""
        sql = [f"CREATE TABLE {q(op.schema, op.name)} (\n    {body}\n){ts}"]
        bkp = self._bkp(op)
        sql.append(f"INSERT INTO {q(op.schema, op.name)} SELECT * FROM {q(op.schema, bkp)}")
        for ik, ix in res.get("implicit", {}).get("indexes", {}).items():
            if ix.get("sql"):
                sql.append(ix["sql"])
        for tk, tr in res.get("implicit", {}).get("triggers", {}).items():
            if tr.get("sql"):
                sql.append(tr["sql"])
        return M.Rollback(sql, complete=True, pre_sql=[self.d.ctas_backup(op.schema, op.name, bkp, None)],
                          notes=[f"Data restored from backup table {bkp} created before the drop; grants must be re-applied."])

    def _rb_truncate_table(self, op, res):
        bkp = self._bkp(op)
        return M.Rollback([f"INSERT INTO {q(op.schema, op.name)} SELECT * FROM {q(op.schema, bkp)}"],
                          pre_sql=[self.d.ctas_backup(op.schema, op.name, bkp, None)],
                          notes=[f"Restores rows from backup {bkp} (created by the -bkp changeSet)."])

    def _rb_add_column(self, op, res):
        cols = [c.name for c in op.details.get("columns", [])]
        x = el("dropColumn", {"tableName": op.table, **self._schema_attr(op)},
               "\n".join(el("column", {"name": c}) for c in cols))
        return M.Rollback([self.d.drop_columns(op.schema, op.table, cols)], [x])

    def _rb_drop_column(self, op, res):
        before = res.get("before") or {}
        impl = res.get("implicit") or {}
        cols = op.details.get("columns", [])
        known = [before[c.upper()] for c in cols if c.upper() in before]
        rb = M.Rollback()
        add_sql, restore_sql, after_sql, not_null = [], [], [], []
        if len(known) == len(cols) and known:
            restored = []
            for c in known:
                c2 = M.Column(c.name, c.data_type, c.nullable, c.default)
                if c2.nullable is False and c2.default is None:
                    not_null.append(c.name)
                    c2.nullable = None
                restored.append(c2)
            add_sql.append(self.d.add_columns(op.schema, op.table, restored))
            for cn, con in (impl.get("constraints") or {}).items():
                if con.ctype != "NOT NULL":
                    after_sql.append(self.d.add_constraint(op.schema, op.table, con))
            for ik, ix in (impl.get("indexes") or {}).items():
                if ix.get("sql"):
                    after_sql.append(ix["sql"].rstrip(";"))
            for col, txt in (impl.get("comments") or {}).items():
                s = self.d.comment("COLUMN", op.schema, op.table, col, txt)
                if s:
                    after_sql.append(s)
        else:
            rb.complete = False
            rb.notes.append(f"Column definition(s) for {', '.join(cols)} unknown - supply --baseline to generate the ADD.")
            add_sql.append(f"-- MANUAL: ALTER TABLE {q(op.schema, op.table)} ADD (<{', '.join(cols)} definitions>)")
        if op.details.get("set_unused"):
            rb.complete = False
            rb.notes.append("SET UNUSED is irreversible in Oracle: rollback re-adds empty columns only.")
        data_restored = False
        if self.profile.get("dml_backup", True):
            bkp = self._bkp(op)
            pk = self._pk_cols(op.schema, op.table)
            if pk:
                sel = ", ".join(pk + cols)
                rb.pre_sql.append(f"CREATE TABLE {q(op.schema, bkp)} AS SELECT {sel} FROM {q(op.schema, op.table)}"
                                  if self.dialect != "mssql" else
                                  f"SELECT {sel} INTO {q(op.schema, bkp)} FROM {q(op.schema, op.table)}")
                if rb.complete:
                    on = " AND ".join(f"t.{c} = b.{c}" for c in pk)
                    if self.dialect in ("oracle", "mssql"):
                        sets = ", ".join(f"t.{c} = b.{c}" for c in cols)
                        restore_sql.append(f"MERGE INTO {q(op.schema, op.table)} t USING {q(op.schema, bkp)} b ON ({on}) "
                                           f"WHEN MATCHED THEN UPDATE SET {sets}")
                    elif self.dialect == "postgresql":
                        sets = ", ".join(f"{c} = b.{c}" for c in cols)
                        restore_sql.append(f"UPDATE {q(op.schema, op.table)} AS t SET {sets} FROM {q(op.schema, bkp)} AS b WHERE {on}")
                    else:
                        sets = ", ".join(f"t.{c} = b.{c}" for c in cols)
                        restore_sql.append(f"UPDATE {q(op.schema, op.table)} t JOIN {q(op.schema, bkp)} b ON {on} SET {sets}")
                    data_restored = True
                    rb.notes.append(f"Column data is restored from {bkp} (created by the -bkp changeSet).")
            else:
                rb.notes.append("Column DATA is not restored (primary key unknown - supply --baseline).")
                rb.complete = False
        for c in not_null:
            if data_restored:
                after_sql.extend(self.d.modify_column(op.schema, op.table, M.Column(c, "", False), M.Column(c, "", True)))
                rb.notes.append(f"{c} is re-added nullable, back-filled from backup, then set NOT NULL "
                                "(fails if rows were inserted after the deploy - fix them first).")
            else:
                rb.notes.append(f"{c} was NOT NULL without default - re-added as NULLABLE; restore data, then set NOT NULL.")
        rb.sql = add_sql + restore_sql + after_sql
        return rb

    def _rb_modify_column(self, op, res):
        before = res.get("before") or {}
        rb = M.Rollback()
        for c in op.details.get("columns", []):
            key = (op.details.get("old_name") or c.name).upper()
            old = before.get(key)
            if op.details.get("rename"):
                rb.sql.append(self.d.rename_column(op.schema, op.table, c.name, op.details["old_name"]))
            if old is None:
                old = M.Column(c.name, "", None, None)
                if c.data_type:
                    rb.complete = False
                    rb.notes.append(f"Previous data type of {c.name} unknown - supply --baseline.")
            stmts = self.d.modify_column(op.schema, op.table, old, c)
            if not stmts and not op.details.get("rename"):
                rb.complete = False
                rb.notes.append(f"Could not derive inverse for {c.name}; write manually.")
            rb.sql.extend(stmts)
            if c.nullable is True:
                rb.notes.append(f"Re-applying NOT NULL on {c.name} fails if NULL rows were written after deploy: "
                                f"UPDATE/DELETE them first.")
        return rb

    def _rb_rename_column(self, op, res):
        return M.Rollback([self.d.rename_column(op.schema, op.table, op.details["new_name"], op.details["column"])],
                          [el("renameColumn", {"tableName": op.table, **self._schema_attr(op),
                                               "oldColumnName": op.details["new_name"], "newColumnName": op.details["column"]})])

    def _rb_rename_table(self, op, res):
        return M.Rollback([self.d.rename_table(op.schema, op.details["new_name"], op.table or op.name)],
                          [el("renameTable", {**self._schema_attr(op), "oldTableName": op.details["new_name"],
                                              "newTableName": op.table or op.name})])

    def _rb_add_constraint(self, op, res):
        c = op.details.get("constraint")
        if not isinstance(c, M.Constraint):
            return M.Rollback(complete=False, notes=["Constraint not parsed - write rollback manually."])
        sql = self.d.drop_constraint(op.schema, op.table, c.name, c.ctype)
        sa = self._schema_attr(op)
        if c.ctype == "FOREIGN KEY":
            x = el("dropForeignKeyConstraint", {"baseTableName": op.table, "constraintName": c.name,
                                                **({"baseTableSchemaName": op.schema} if sa else {})})
        elif c.ctype == "PRIMARY KEY":
            x = el("dropPrimaryKey", {"tableName": op.table, "constraintName": c.name, **sa})
        elif c.ctype == "UNIQUE":
            x = el("dropUniqueConstraint", {"tableName": op.table, "constraintName": c.name, **sa})
        else:
            x = self._xml_sql(sql)
        rb = M.Rollback([sql], [x])
        if not c.name:
            rb.complete = False
            rb.notes.append("Unnamed constraint: name is system generated - rollback must look it up.")
        return rb

    def _rb_drop_constraint(self, op, res):
        con = res.get("before")
        if not con:
            name = op.details.get("constraint_name")
            return M.Rollback([f"-- MANUAL: ALTER TABLE {q(op.schema, op.table)} ADD CONSTRAINT {name} <definition>"],
                              complete=False, notes=[f"Definition of {name} unknown - supply --baseline."])
        rb = M.Rollback([self.d.add_constraint(op.schema, op.table, con)])
        if con.ctype == "FOREIGN KEY":
            rb.notes.append(f"Re-adding FK {con.name} fails if orphan rows were created meanwhile - delete/repair them first.")
        return rb

    # ------------------------------------------------------------ indexes / sequences
    def _rb_create_index(self, op, res):
        ts = op.details.get("table_schema") or op.schema
        sql = self.d.drop_index(op.schema, op.name, ts, op.table)
        return M.Rollback([sql], [el("dropIndex", {"indexName": op.name, "tableName": op.table,
                                                   **({"schemaName": op.schema} if self._schema_attr(op) else {})})])

    def _rb_drop_index(self, op, res):
        b = res.get("before")
        if b and b.get("sql"):
            return M.Rollback([b["sql"].rstrip(";")])
        if b and b.get("columns"):
            t = b["table_key"]
            return M.Rollback([f"CREATE {'UNIQUE ' if b.get('unique') else ''}INDEX {op.qualified} ON {t} ({', '.join(b['columns'])})"
                               + (f" TABLESPACE {b['tablespace']}" if b.get("tablespace") else "")])
        return M.Rollback([f"-- MANUAL: CREATE INDEX {op.qualified} ON <table> (<columns>)"], complete=False,
                          notes=["Index definition unknown - supply --baseline."])

    def _rb_create_sequence(self, op, res):
        return M.Rollback([self.d.drop_object("SEQUENCE", op.schema, op.name)],
                          [el("dropSequence", {"sequenceName": op.name, **self._schema_attr(op)})])

    def _rb_drop_sequence(self, op, res):
        b = res.get("before")
        if b and b.get("sql"):
            return M.Rollback([b["sql"]], notes=["Recreated sequence restarts at its original START WITH; reset it above "
                                                 "MAX(id) before use."])
        return M.Rollback([f"-- MANUAL: CREATE SEQUENCE {op.qualified} START WITH <max_id + 1>"], complete=False,
                          notes=["Sequence definition unknown."])

    def _rb_alter_sequence(self, op, res):
        return M.Rollback(complete=False, notes=["ALTER SEQUENCE: restore previous INCREMENT/CACHE manually."])

    # ------------------------------------------------------------ replaceable code objects
    def _replaceable(self, op, res, otype):
        before = res.get("before")
        plsql = op.kind in M.PLSQL_KINDS or self.dialect == "mssql"
        if res.get("existed") and before and before.get("sql"):
            prev = before["sql"]
            rb = M.Rollback([prev], [self._xml_sql(prev, plsql)],
                            notes=[f"Restores the previous definition of {op.qualified} captured from baseline/earlier step."])
            if op.kind == M.CREATE_VIEW and before.get("comment"):
                s = self.d.comment("TABLE", op.schema, op.name, None, before["comment"])
                if s:
                    rb.sql.append(s)
            return rb
        if res.get("existed"):
            return M.Rollback([f"-- MANUAL: restore previous source of {op.qualified}"], complete=False,
                              notes=[f"{op.qualified} existed but previous source unknown."])
        sql = self.d.drop_object(otype, op.schema, op.name, op.table)
        on_new_table = op.kind == M.CREATE_TRIGGER and op.table and \
            self.schema.tables.get(self.schema.key(op.details.get("table_schema") or op.schema, op.table)) is not None and \
            self.schema.tables[self.schema.key(op.details.get("table_schema") or op.schema, op.table)].origin == "new"
        if op.or_replace and not self.schema.has_baseline and not on_new_table and \
                not self.profile.get("assume_new_when_unknown", False):
            src = "DBMS_METADATA pre-check output" if self.dialect == "oracle" else "definition captured by the pre-check"
            return M.Rollback([f"-- MANUAL: restore the previous definition of {op.qualified} ({src}) "
                               f"or {sql} if the object is new"], complete=False,
                              notes=[f"CREATE OR REPLACE {op.qualified} without --baseline: the agent cannot know whether a "
                                     "previous version exists, so it will not generate a DROP that could delete a live object."])
        if op.kind == M.CREATE_VIEW:
            x = el("dropView", {"viewName": op.name, **self._schema_attr(op)}) if not op.details.get("materialized") \
                else self._xml_sql(sql)
        elif op.kind == M.CREATE_PROCEDURE:
            x = el("dropProcedure", {"procedureName": op.name, **self._schema_attr(op)})
        else:
            x = self._xml_sql(sql)
        rb = M.Rollback([sql], [x])
        if op.or_replace and not self.schema.has_baseline and not on_new_table:
            rb.notes.append(f"Assumes {op.qualified} is new. If it already exists in the target, supply --baseline so the "
                            "previous version is restored instead of dropped.")
        return rb

    def _rb_create_view(self, op, res):
        return self._replaceable(op, res, "MATERIALIZED VIEW" if op.details.get("materialized") else "VIEW")

    def _rb_create_trigger(self, op, res):
        return self._replaceable(op, res, "TRIGGER")

    def _rb_create_procedure(self, op, res):
        return self._replaceable(op, res, "PROCEDURE")

    def _rb_create_function(self, op, res):
        return self._replaceable(op, res, "FUNCTION")

    def _rb_create_package(self, op, res):
        return self._replaceable(op, res, "TYPE" if op.object_type == "TYPE" else "PACKAGE")

    def _rb_create_package_body(self, op, res):
        return self._replaceable(op, res, "TYPE BODY" if op.object_type.startswith("TYPE") else "PACKAGE BODY")

    def _drop_code(self, op, res):
        b = res.get("before")
        if b and b.get("sql"):
            return M.Rollback([b["sql"]], [self._xml_sql(b["sql"], op.object_type != "VIEW")])
        return M.Rollback([f"-- MANUAL: recreate {op.object_type} {op.qualified}"], complete=False,
                          notes=[f"Source of {op.qualified} unknown - supply --baseline."])

    _rb_drop_view = _drop_code
    _rb_drop_trigger = _drop_code
    _rb_drop_routine = _drop_code

    # ------------------------------------------------------------ comments / grants
    def _rb_comment(self, op, res):
        tgt = op.details.get("target")
        prev = res.get("before")
        s = self.d.comment(tgt, op.schema, op.table, op.details.get("column"), prev or "")
        if not s:
            return M.Rollback(complete=False, notes=["Comment rollback not supported for this dialect."])
        rb = M.Rollback([s])
        if prev is None:
            rb.notes.append("No previous comment known - rollback blanks the comment.")
        return rb

    def _rb_grant(self, op, res):
        d = op.details
        g = ", ".join(d.get("grantees", []))
        return M.Rollback([f"REVOKE {d.get('privileges')} ON {op.qualified} FROM {g}"])

    def _rb_revoke(self, op, res):
        d = op.details
        return M.Rollback([f"GRANT {d.get('privileges')} ON {op.qualified} TO {', '.join(d.get('grantees', []))}"])

    # ------------------------------------------------------------ DML
    def _rb_insert(self, op, res):
        d = op.details
        cols, vals = d.get("columns", []), d.get("values", [])
        if d.get("from_select") or d.get("multi_row") or not cols or len(cols) != len(vals):
            return M.Rollback([f"-- MANUAL: DELETE FROM {q(op.schema, op.table)} WHERE <rows inserted by this changeSet>"],
                              complete=False, notes=["INSERT ... SELECT / multi-row insert: identify inserted rows "
                                                     "(e.g. by a batch/created_by marker) for the rollback DELETE."])
        pk = [c.upper() for c in self._pk_cols(op.schema, op.table)]
        pairs = list(zip(cols, vals))
        use = [(c, v) for c, v in pairs if c.upper() in pk] if pk and all(p in [c.upper() for c in cols] for p in pk) else \
            [(c, v) for c, v in pairs if re.fullmatch(r"'(?:[^']|'')*'|-?\d+(\.\d+)?", v.strip())]
        if not use:
            return M.Rollback(complete=False, notes=["No literal key values to build the rollback DELETE."])
        where = " AND ".join(f"{c} = {v}" for c, v in use)
        rb = M.Rollback([f"DELETE FROM {q(op.schema, op.table)} WHERE {where}"])
        if not pk:
            rb.notes.append("Rollback DELETE matches on literal column values (no PK known) - verify uniqueness.")
        return rb

    def _rb_update(self, op, res):
        return self._backup_restore(op, "UPDATE")

    def _rb_delete(self, op, res):
        return self._backup_restore(op, "DELETE")

    def _rb_merge(self, op, res):
        return M.Rollback([f"-- MANUAL: reverse MERGE on {op.qualified_table}"], complete=False,
                          notes=["MERGE rollback requires a pre-image backup; restore from the -bkp table."],
                          pre_sql=[self.d.ctas_backup(op.schema, op.table, self._bkp(op), None)])

    def _backup_restore(self, op, kind):
        d = op.details
        bkp = self._bkp(op)
        where = d.get("where")
        pre = [self.d.ctas_backup(op.schema, op.table, bkp, where)] if self.profile.get("dml_backup", True) else []
        t, b = q(op.schema, op.table), q(op.schema, bkp)
        if kind == "DELETE":
            return M.Rollback([f"INSERT INTO {t} SELECT * FROM {b}"], pre_sql=pre,
                              notes=[f"Deleted rows restored from {bkp}."] if pre else [],
                              complete=bool(pre))
        pk = self._pk_cols(op.schema, op.table)
        cols = d.get("set_columns", [])
        if pre and pk and cols and self.dialect in ("oracle", "postgresql", "mssql"):
            on = " AND ".join(f"t.{c} = b.{c}" for c in pk)
            if self.dialect == "postgresql":
                sets = ", ".join(f"{c} = b.{c}" for c in cols)
                sql = f"UPDATE {t} AS t SET {sets} FROM {b} AS b WHERE {on}"
            else:
                sets = ", ".join(f"t.{c} = b.{c}" for c in cols)
                sql = f"MERGE INTO {t} t USING {b} b ON ({on}) WHEN MATCHED THEN UPDATE SET {sets}"
            return M.Rollback([sql], pre_sql=pre, notes=[f"Pre-update values restored from {bkp} by primary key."])
        return M.Rollback([f"-- MANUAL: restore {', '.join(cols)} on {t} from {b}"], pre_sql=pre, complete=False,
                          notes=["UPDATE rollback needs the PK of the table (supply --baseline) to restore from the backup."])

    def _rb_plsql_block(self, op, res):
        return M.Rollback([f"-- MANUAL: compensating block for anonymous PL/SQL at {op.statement.source}:{op.statement.line_start}"],
                          complete=False, notes=["Anonymous blocks need a hand-written compensating block."])

    def _rb_alter_table_raw(self, op, res):
        return M.Rollback([f"-- MANUAL: reverse '{op.details.get('action_text', '')[:80]}'"], complete=False,
                          notes=["Raw ALTER TABLE action - write rollback manually."])

    def _rb_other(self, op, res):
        return M.Rollback([f"-- MANUAL: reverse statement at {op.statement.source}:{op.statement.line_start}"],
                          complete=False, notes=["Unrecognised statement - write rollback manually."])

    # ------------------------------------------------------------ misc
    def _pk_cols(self, schema, table) -> List[str]:
        t = self.schema.table(schema, table)
        if not t:
            return []
        for c in t.constraints.values():
            if c.ctype == "PRIMARY KEY":
                return list(c.columns)
        return []

    def _bkp(self, op) -> str:
        suffix = self.profile.get("backup_suffix", "_BKP")
        maxlen = self.profile.get("naming", {}).get("max_identifier_length") or 30
        base = (op.table or op.name).upper()
        tag = f"{suffix}{op.seq}"
        return (base[: maxlen - len(tag)] + tag)
