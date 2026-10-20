"""Liquibase changelog generators.

XmlChangelogGenerator   -> db.changelog-<release>.xml (native change types, explicit <rollback>,
                           optional preconditions, one logical change per changeSet)
FormattedSqlGenerator   -> house-style 'liquibase formatted sql' deploy scripts with
                           change-tracker pre/post changeSets, inline --rollback and a
                           consolidated rollback script (mirrors the vibehub 1.34 package)
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Dict, List, Optional, Tuple

from core import models as M
from analyzers.table_analyzer import _guess_ctype
from generators.naming import Namer
from generators.xml_util import attrs as A, cdata, el, indent
from templates.loader import Templates


def default_attr(v: Optional[str]) -> Dict[str, str]:
    if v is None:
        return {}
    s = v.strip()
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return {"defaultValueNumeric": s}
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return {"defaultValue": s[1:-1].replace("''", "'")}
    if s.upper() in ("TRUE", "FALSE"):
        return {"defaultValueBoolean": s.lower()}
    if s.upper() == "NULL":
        return {}
    return {"defaultValueComputed": s}


def value_attr(v: str) -> Dict[str, str]:
    s = v.strip()
    if re.fullmatch(r"-?\d+(\.\d+)?", s):
        return {"valueNumeric": s}
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return {"value": s[1:-1].replace("''", "'")}
    if s.upper() == "NULL":
        return {}
    return {"valueComputed": s}


def xml_type(c: M.Column) -> Tuple[str, bool]:
    t = (c.data_type or "").strip()
    u = t.upper()
    if u == "SERIAL":
        return "INT", True
    if u == "BIGSERIAL":
        return "BIGINT", True
    if u == "SMALLSERIAL":
        return "SMALLINT", True
    t = re.sub(r"\s+IDENTITY\s*\([^)]*\)", "", t, flags=re.I)
    t = re.sub(r"\s+AUTO_INCREMENT", "", t, flags=re.I)
    return t, c.auto_increment


class XmlChangeBuilder:
    def __init__(self, dialect: str, profile: dict, tpl: Templates):
        self.d = dialect
        self.p = profile
        self.tpl = tpl

    def sa(self, schema):
        return {"schemaName": schema} if schema and self.p.get("xml_schema_attr", True) else {}

    def _pre(self, conds: List[str]) -> str:
        if not conds or not self.p.get("preconditions", True):
            return ""
        return self.tpl.render("preconditions", on_fail=self.p.get("precondition_on_fail", "MARK_RAN"),
                               on_error=self.p.get("precondition_on_error", "HALT"),
                               conditions=indent("\n".join(conds), 12)) + "\n"

    def sql(self, body: str, plsql: bool = False, extra: Optional[dict] = None) -> str:
        a = dict(extra or {})
        if plsql:
            return self.tpl.render("plsql", attrs=A(a), body=body.rstrip())
        return self.tpl.render("sql", attrs=A(a), body=body.rstrip().rstrip(";"))

    # --------------------------------------------------------------------- per-op
    def changes(self, op: M.Operation, unit_ops: List[M.Operation], rb: M.Rollback) -> List[dict]:
        """Return list of changeSet specs: {changes, rollback, pre, attrs, comment}."""
        fn = getattr(self, "_x_" + op.kind.lower(), None)
        if fn:
            out = fn(op, unit_ops, rb)
            if out is not None:
                return out
        plsql = op.kind in M.PLSQL_KINDS
        return [self.spec(op, self.sql(op.sql, plsql, {"endDelimiter": "\\n/"} if plsql and self.d == "oracle" else None), rb)]

    def spec(self, op, change, rb: Optional[M.Rollback], pre=None, attrs=None, comment=None, rollback_xml=None):
        if rollback_xml is None:
            items = [x for x in (rb.xml if rb else []) if "-- MANUAL" not in x]
            rollback_xml = "\n".join(items)
            if rb and not rb.complete:
                note = " | ".join(dict.fromkeys(rb.notes)) or "manual rollback required"
                manual = [s[9:].strip() for s in rb.sql if s.startswith("-- MANUAL")]
                if manual:
                    note += " | e.g. " + " ; ".join(manual)
                rollback_xml = (rollback_xml + "\n" if rollback_xml else "") + \
                    f"<!-- TODO MANUAL ROLLBACK: {note.replace('--', '- -')} -->"
        return {"changes": change, "rollback": rollback_xml, "pre": self._pre(pre or []), "attrs": attrs or {},
                "comment": comment, "op": op, "rb": rb}

    # ---- tables
    def _x_create_table(self, op, unit_ops, rb):
        d = op.details
        cons = d.get("constraints", [])
        pk = next((c for c in cons if c.ctype == "PRIMARY KEY"), None)
        pk_cols = [x.upper() for x in (pk.columns if pk else [])]
        single_uk = {c.columns[0].upper(): c for c in cons if c.ctype == "UNIQUE" and len(c.columns) == 1}
        remarks = {}
        table_remark = d.get("remarks")
        for o in unit_ops:
            if o.kind == M.COMMENT and (o.table or "").upper() == op.name.upper():
                if o.details.get("target") == "COLUMN":
                    remarks[o.details["column"].upper()] = o.details["text"]
                else:
                    table_remark = o.details["text"]
        cols_xml = []
        for c in d.get("columns", []):
            typ, auto = xml_type(c)
            ca = {"name": c.name, "type": typ}
            ca.update(default_attr(c.default))
            if auto:
                ca["autoIncrement"] = "true"
            r = remarks.get(c.name.upper()) or c.remarks
            if r:
                ca["remarks"] = r
            con = {}
            if c.name.upper() in pk_cols:
                con.update({"primaryKey": "true", "primaryKeyName": pk.name})
                con["nullable"] = "false"
            if c.nullable is False:
                con["nullable"] = "false"
            uk = single_uk.get(c.name.upper())
            if uk:
                con.update({"unique": "true", "uniqueConstraintName": uk.name})
            if con:
                cols_xml.append(self.tpl.render("column_with_constraints", attrs=A(ca), constraint_attrs=A(con)))
            else:
                cols_xml.append(self.tpl.render("column", attrs=A(ca)))
        ta = {"tableName": op.name, **self.sa(op.schema), "tablespace": d.get("tablespace"), "remarks": table_remark}
        change = self.tpl.render("create_table", attrs=A(ta), columns=indent("\n".join(cols_xml), 4))
        opts = d.get("options", "") or ""
        opts = re.sub(r"\bTABLESPACE\s+\"?[\w$#]+\"?", "", opts, flags=re.I).strip()
        if table_remark:
            opts = re.sub(r"\bCOMMENT\s*=?\s*'(?:[^']|'')*'", "", opts, flags=re.I).strip()
        if opts:
            change += "\n" + self.tpl.render("modify_sql_append", dbms=self.d, value=" " + " ".join(opts.split()))
        specs = [self.spec(op, change, rb, pre=[f"<not><tableExists tableName=\"{op.name}\"{A(self.sa(op.schema))}/></not>"],
                           comment=f"Create table {op.qualified}")]
        # MySQL inline KEY/INDEX definitions -> createIndex changeSets
        for ix in d.get("inline_indexes", []):
            if not ix.get("name"):
                continue
            cols = "\n".join(self.tpl.render("index_column", attrs=A({"name": cn})) for cn in ix["columns"])
            ch = self.tpl.render("create_index", attrs=A({"indexName": ix["name"], "tableName": op.name, **self.sa(op.schema)}),
                                 columns=indent(cols, 4))
            rbx = self.tpl.render("drop_index", attrs=A({"indexName": ix["name"], "tableName": op.name, **self.sa(op.schema)}))
            specs.append(self.spec(op, ch, None, comment=f"Index {ix['name']} on {op.qualified} (inline KEY)", rollback_xml=rbx))
        # out-of-line constraints as separate changeSets
        for c in cons:
            if c.ctype == "UNIQUE" and len(c.columns) > 1:
                ch = self.tpl.render("add_unique", attrs=A({"tableName": op.name, **self.sa(op.schema),
                                                           "columnNames": ", ".join(c.columns), "constraintName": c.name,
                                                           "tablespace": d.get("tablespace")}))
                rbx = self.tpl.render("drop_unique", attrs=A({"tableName": op.name, **self.sa(op.schema), "constraintName": c.name}))
                specs.append(self.spec(op, ch, None, comment=f"Unique constraint {c.name} on {op.qualified}", rollback_xml=rbx))
            elif c.ctype == "FOREIGN KEY":
                specs.append(self._fk_spec(op, c, f"Foreign key {c.name} on {op.qualified}"))
            elif c.ctype == "CHECK":
                nm = c.name or f"CHK_{op.name[:20]}_{len(specs)}"
                tq = op.qualified
                ch = self.sql(f"ALTER TABLE {tq} ADD CONSTRAINT {nm} CHECK ({c.check_expr})")
                rbx = self.sql(f"ALTER TABLE {tq} DROP CONSTRAINT {nm}")
                specs.append(self.spec(op, ch, None, comment=f"Check constraint {nm} on {tq}", rollback_xml=rbx))
        return specs

    def _fk_spec(self, op, c, comment, validate=True):
        a = {"baseTableName": op.table or op.name, "baseColumnNames": ", ".join(c.columns), "constraintName": c.name,
             "referencedTableName": c.ref_table, "referencedColumnNames": ", ".join(c.ref_columns)}
        if op.schema and self.p.get("xml_schema_attr", True):
            a["baseTableSchemaName"] = op.schema
            a["referencedTableSchemaName"] = c.ref_schema or op.schema
        if c.on_delete:
            a["onDelete"] = c.on_delete.upper()
        if not validate:
            a["validate"] = "false"
        ch = self.tpl.render("add_foreign_key", attrs=A(a))
        rba = {"baseTableName": a["baseTableName"], "constraintName": c.name}
        if "baseTableSchemaName" in a:
            rba["baseTableSchemaName"] = a["baseTableSchemaName"]
        rbx = self.tpl.render("drop_foreign_key", attrs=A(rba))
        return self.spec(op, ch, None, pre=[f"<not><foreignKeyConstraintExists foreignKeyName=\"{c.name}\"/></not>"] if c.name else None,
                         comment=comment, rollback_xml=rbx)

    def _x_add_column(self, op, unit_ops, rb):
        cols = []
        for c in op.details.get("columns", []):
            typ, auto = xml_type(c)
            ca = {"name": c.name, "type": typ, **default_attr(c.default)}
            if auto:
                ca["autoIncrement"] = "true"
            con = {}
            if c.nullable is False:
                con["nullable"] = "false"
            if c.primary_key:
                con.update({"primaryKey": "true", "primaryKeyName": c.pk_name})
            if c.unique:
                con.update({"unique": "true", "uniqueConstraintName": c.unique_name})
            if c.references:
                r = c.references
                con.update({"foreignKeyName": r.get("name"), "referencedTableName": r.get("table"),
                            "referencedColumnNames": ", ".join(r.get("columns", []))})
                if r.get("schema"):
                    con["referencedTableSchemaName"] = r["schema"]
            cols.append(self.tpl.render("column_with_constraints" if con else "column", attrs=A(ca), constraint_attrs=A(con)))
        ch = self.tpl.render("add_column", attrs=A({"tableName": op.table, **self.sa(op.schema)}),
                             columns=indent("\n".join(cols), 4))
        first = op.details.get("columns", [None])[0]
        pre = [f"<not><columnExists tableName=\"{op.table}\" columnName=\"{first.name}\"{A(self.sa(op.schema))}/></not>"] if first else None
        return [self.spec(op, ch, rb, pre=pre, comment=f"Add column(s) to {op.qualified_table}")]

    def _x_drop_column(self, op, unit_ops, rb):
        d = op.details
        if d.get("set_unused") or (d.get("cascade") and self.d == "oracle"):
            return [self.spec(op, self.sql(op.sql), rb, comment=f"Drop column(s) {', '.join(d['columns'])} from {op.qualified_table}")]
        cols = "\n".join(self.tpl.render("column", attrs=A({"name": c})) for c in d.get("columns", []))
        ch = self.tpl.render("drop_column", attrs=A({"tableName": op.table, **self.sa(op.schema)}), columns=indent(cols, 4))
        pre = [f"<columnExists tableName=\"{op.table}\" columnName=\"{d['columns'][0]}\"{A(self.sa(op.schema))}/>"]
        return [self.spec(op, ch, rb, pre=pre, comment=f"Drop column(s) {', '.join(d['columns'])} from {op.qualified_table}")]

    def _x_modify_column(self, op, unit_ops, rb):
        d = op.details
        changes = []
        base = {"tableName": op.table, **self.sa(op.schema)}
        for c in d.get("columns", []):
            if d.get("rename"):
                changes.append(self.tpl.render("rename_column", attrs=A({**base, "oldColumnName": d["old_name"],
                                                                        "newColumnName": c.name,
                                                                        "columnDataType": c.data_type})))
            if c.data_type and self.d not in ("mysql", "mariadb"):
                changes.append(self.tpl.render("modify_data_type", attrs=A({**base, "columnName": c.name,
                                                                           "newDataType": c.data_type})))
            elif c.data_type:
                return None  # MySQL: keep full MODIFY statement (restates whole definition)
            if c.nullable is False:
                changes.append(self.tpl.render("add_not_null", attrs=A({**base, "columnName": c.name,
                                                                       "columnDataType": c.data_type or None})))
            elif c.nullable is True:
                changes.append(self.tpl.render("drop_not_null", attrs=A({**base, "columnName": c.name,
                                                                        "columnDataType": c.data_type or None})))
            if c.default is not None:
                changes.append(self.tpl.render("add_default", attrs=A({**base, "columnName": c.name,
                                                                      "columnDataType": c.data_type or None,
                                                                      **default_attr(c.default)})))
        if d.get("drop_default"):
            changes.append(self.tpl.render("drop_default", attrs=A({**base, "columnName": d.get("column")})))
        if not changes:
            return None
        return [self.spec(op, "\n".join(changes), rb, comment=f"Modify column(s) on {op.qualified_table}")]

    def _x_rename_column(self, op, unit_ops, rb):
        ch = self.tpl.render("rename_column", attrs=A({"tableName": op.table, **self.sa(op.schema),
                                                      "oldColumnName": op.details["column"],
                                                      "newColumnName": op.details["new_name"]}))
        return [self.spec(op, ch, rb, comment=f"Rename column on {op.qualified_table}")]

    def _x_rename_table(self, op, unit_ops, rb):
        ch = self.tpl.render("rename_table", attrs=A({**self.sa(op.schema), "oldTableName": op.table or op.name,
                                                     "newTableName": op.details["new_name"]}))
        return [self.spec(op, ch, rb, comment=f"Rename table {op.qualified_table}")]

    def _x_add_constraint(self, op, unit_ops, rb):
        c = op.details.get("constraint")
        if not isinstance(c, M.Constraint):
            return None
        base = {"tableName": op.table, **self.sa(op.schema)}
        if c.ctype == "FOREIGN KEY":
            return [self._fk_spec(op, c, f"Add FK {c.name} on {op.qualified_table}", op.details.get("validate", True))]
        if c.ctype == "PRIMARY KEY":
            ch = self.tpl.render("add_primary_key", attrs=A({**base, "columnNames": ", ".join(c.columns), "constraintName": c.name}))
            return [self.spec(op, ch, rb, pre=[f"<not><primaryKeyExists tableName=\"{op.table}\"{A(self.sa(op.schema))}/></not>"],
                              comment=f"Add PK {c.name} on {op.qualified_table}")]
        if c.ctype == "UNIQUE":
            ch = self.tpl.render("add_unique", attrs=A({**base, "columnNames": ", ".join(c.columns), "constraintName": c.name}))
            return [self.spec(op, ch, rb, comment=f"Add unique constraint {c.name} on {op.qualified_table}")]
        return [self.spec(op, self.sql(op.sql), rb, comment=f"Add {c.ctype} constraint {c.name} on {op.qualified_table}")]

    def _x_drop_constraint(self, op, unit_ops, rb):
        name = op.details.get("constraint_name")
        before = op.details.get("_before_ctype") or _guess_ctype(name or "", self.p) or op.details.get("ctype")
        base = {"tableName": op.table, **self.sa(op.schema), "constraintName": name}
        if op.details.get("cascade"):
            return None
        if before == "FOREIGN KEY":
            a = {"baseTableName": op.table, "constraintName": name}
            if op.schema and self.p.get("xml_schema_attr", True):
                a["baseTableSchemaName"] = op.schema
            ch = self.tpl.render("drop_foreign_key", attrs=A(a))
            return [self.spec(op, ch, rb, pre=[f"<foreignKeyConstraintExists foreignKeyName=\"{name}\"/>"],
                              comment=f"Drop FK {name} on {op.qualified_table}")]
        if before == "PRIMARY KEY":
            return [self.spec(op, self.tpl.render("drop_primary_key", attrs=A(base)), rb,
                              comment=f"Drop PK on {op.qualified_table}")]
        if before == "UNIQUE":
            return [self.spec(op, self.tpl.render("drop_unique", attrs=A(base)), rb,
                              comment=f"Drop unique constraint {name} on {op.qualified_table}")]
        return None

    # ---- indexes / sequences
    def _x_create_index(self, op, unit_ops, rb):
        d = op.details
        attrs = {}
        if d.get("concurrently"):
            attrs["runInTransaction"] = "false"
        raw = d.get("functional") or d.get("bitmap") or d.get("concurrently") or d.get("online") or d.get("where") \
            or d.get("include") or d.get("local") or d.get("method")
        pre = [f"<not><indexExists indexName=\"{op.name}\"{A(self.sa(op.schema))}/></not>"]
        comment = f"Create index {op.name} on {op.table}"
        if raw:
            return [self.spec(op, self.sql(op.sql), rb, pre=pre, attrs=attrs, comment=comment)]
        cols = "\n".join(self.tpl.render("index_column", attrs=A({"name": c["name"],
                                                                 "descending": "true" if c.get("descending") else None}))
                         for c in d.get("columns", []))
        ia = {"indexName": op.name, "tableName": op.table, **self.sa(d.get("table_schema") or op.schema),
              "tablespace": d.get("tablespace"), "unique": "true" if d.get("unique") else None,
              "clustered": "true" if d.get("clustered") else None}
        ch = self.tpl.render("create_index", attrs=A(ia), columns=indent(cols, 4))
        return [self.spec(op, ch, rb, pre=pre, attrs=attrs, comment=comment)]

    def _x_drop_index(self, op, unit_ops, rb):
        ch = self.tpl.render("drop_index", attrs=A({"indexName": op.name, "tableName": op.table, **self.sa(op.schema)}))
        return [self.spec(op, ch, rb, pre=[f"<indexExists indexName=\"{op.name}\"{A(self.sa(op.schema))}/>"],
                          comment=f"Drop index {op.name}")]

    def _x_create_sequence(self, op, unit_ops, rb):
        d = op.details
        a = {"sequenceName": op.name, **self.sa(op.schema), "startValue": d.get("start"), "incrementBy": d.get("increment"),
             "minValue": d.get("minvalue"), "maxValue": d.get("maxvalue"), "cacheSize": d.get("cache"),
             "cycle": "true" if d.get("cycle") else "false", "ordered": "true" if d.get("order") else None,
             "dataType": d.get("data_type")}
        ch = self.tpl.render("create_sequence", attrs=A(a))
        return [self.spec(op, ch, rb, pre=[f"<not><sequenceExists sequenceName=\"{op.name}\"{A(self.sa(op.schema))}/></not>"],
                          comment=f"Create sequence {op.qualified}")]

    def _x_drop_sequence(self, op, unit_ops, rb):
        ch = self.tpl.render("drop_sequence", attrs=A({"sequenceName": op.name, **self.sa(op.schema)}))
        return [self.spec(op, ch, rb, comment=f"Drop sequence {op.qualified}")]

    def _x_drop_table(self, op, unit_ops, rb):
        a = {"tableName": op.name, **self.sa(op.schema)}
        if op.details.get("cascade"):
            a["cascadeConstraints"] = "true"
        specs = []
        if rb and rb.pre_sql:
            specs.append(self.spec(op, "\n".join(self.sql(s) for s in rb.pre_sql), None,
                                   comment=f"Backup {op.qualified} before drop",
                                   rollback_xml=self.sql(f"DROP TABLE {op.schema + '.' if op.schema else ''}"
                                                         f"{_bkp_name(rb.pre_sql[0])}")))
        specs.append(self.spec(op, self.tpl.render("drop_table", attrs=A(a)), rb,
                               pre=[f"<tableExists tableName=\"{op.name}\"{A(self.sa(op.schema))}/>"],
                               comment=f"Drop table {op.qualified}"))
        return specs

    # ---- code objects
    def _x_create_view(self, op, unit_ops, rb):
        d = op.details
        simple = not (d.get("columns") or d.get("force") or d.get("editionable") or d.get("materialized")
                      or d.get("check_option") or d.get("read_only")) and self.d != "mssql"
        extra = []
        for o in unit_ops:
            if o.kind == M.COMMENT and (o.table or "").upper() == op.name.upper() and o is not op:
                pass
        if simple:
            ch = self.tpl.render("create_view", attrs=A({"viewName": op.name, **self.sa(op.schema),
                                                        "replaceIfExists": "true" if op.or_replace else None}),
                                 body=d.get("select", "").rstrip(";"))
        else:
            ch = self.sql(op.sql, plsql=False, extra={"splitStatements": "false", "stripComments": "false"})
        attrs = {"runOnChange": "true"} if self.p.get("run_on_change_for_replaceable") else {}
        pre = None if op.or_replace else [f"<not><viewExists viewName=\"{op.name}\"{A(self.sa(op.schema))}/></not>"]
        return [self.spec(op, ch, rb, pre=pre, attrs=attrs, comment=f"{'Create or replace' if op.or_replace else 'Create'} view {op.qualified}")]

    def _code(self, op, rb, what):
        attrs = {"runOnChange": "true"} if self.p.get("run_on_change_for_replaceable") else {}
        body = op.sql.rstrip()
        if self.d == "oracle":
            body = re.sub(r"\n\s*/\s*$", "", body)
        if op.kind in (M.CREATE_PROCEDURE, M.CREATE_FUNCTION, M.CREATE_PACKAGE, M.CREATE_PACKAGE_BODY):
            ch = self.tpl.render("create_procedure", attrs=A({"procedureName": op.name, **self.sa(op.schema),
                                                             "dbms": self.d if self.p.get("xml_dbms_attr") else None}),
                                 body=body)
        else:
            ch = self.tpl.render("plsql", attrs=A({"dbms": self.d if self.p.get("xml_dbms_attr") else None}), body=body)
        return [self.spec(op, ch, rb, attrs=attrs, comment=f"{'Create or replace' if op.or_replace else 'Create'} {what} {op.qualified}")]

    def _x_create_trigger(self, op, unit_ops, rb):
        return self._code(op, rb, "trigger")

    def _x_create_procedure(self, op, unit_ops, rb):
        return self._code(op, rb, "procedure")

    def _x_create_function(self, op, unit_ops, rb):
        return self._code(op, rb, "function")

    def _x_create_package(self, op, unit_ops, rb):
        return self._code(op, rb, op.object_type.lower())

    def _x_create_package_body(self, op, unit_ops, rb):
        return self._code(op, rb, op.object_type.lower())

    def _x_comment(self, op, unit_ops, rb):
        d = op.details
        if d.get("target") == "COLUMN":
            ch = self.tpl.render("set_column_remarks", attrs=A({"tableName": op.table, "columnName": d["column"],
                                                               **self.sa(op.schema), "remarks": d.get("text")}))
        elif d.get("target") == "TABLE":
            ch = self.tpl.render("set_table_remarks", attrs=A({"tableName": op.table, **self.sa(op.schema),
                                                              "remarks": d.get("text")}))
        else:
            ch = self.sql(op.sql)
        return [self.spec(op, ch, rb, comment=f"Comment on {op.qualified}")]

    def _x_insert(self, op, unit_ops, rb):
        d = op.details
        if d.get("from_select") or d.get("multi_row") or not d.get("columns") or len(d["columns"]) != len(d.get("values", [])):
            return [self.spec(op, self.sql(op.sql), rb, comment=f"Data: insert into {op.qualified_table}")]
        cols = "\n".join(self.tpl.render("column", attrs=A({"name": c, **value_attr(v)})) for c, v in zip(d["columns"], d["values"]))
        ch = self.tpl.render("insert", attrs=A({"tableName": op.table, **self.sa(op.schema)}), columns=indent(cols, 4))
        return [self.spec(op, ch, rb, comment=f"Data: insert into {op.qualified_table}")]

    def _dml_with_backup(self, op, rb, verb):
        specs = []
        if rb and rb.pre_sql:
            bk = _bkp_name(rb.pre_sql[0])
            specs.append(self.spec(op, "\n".join(self.sql(s) for s in rb.pre_sql), None,
                                   comment=f"Backup rows of {op.qualified_table} before {verb}",
                                   rollback_xml=self.sql(f"DROP TABLE {op.schema + '.' if op.schema else ''}{bk}")))
        specs.append(self.spec(op, self.sql(op.sql), rb, comment=f"Data: {verb} {op.qualified_table}"))
        return specs

    def _x_update(self, op, unit_ops, rb):
        return self._dml_with_backup(op, rb, "update")

    def _x_delete(self, op, unit_ops, rb):
        return self._dml_with_backup(op, rb, "delete")

    def _x_merge(self, op, unit_ops, rb):
        return self._dml_with_backup(op, rb, "merge")

    def _x_truncate_table(self, op, unit_ops, rb):
        return self._dml_with_backup(op, rb, "truncate")

    def _x_drop_column_backup(self):
        return None


def _bkp_name(sql: str) -> str:
    m = re.search(r"(?:TABLE|INTO)\s+(?:[\w$#]+\.)?([\w$#]+)", sql, re.I)
    return m.group(1) if m else "BKP"


class XmlChangelogGenerator:
    def __init__(self, dialect: str, profile: dict, tpl: Templates, namer: Namer):
        self.d, self.p, self.tpl, self.namer = dialect, profile, tpl, namer
        self.builder = XmlChangeBuilder(dialect, profile, tpl)

    def generate(self, units: List[M.ChangeUnit], rollbacks: Dict[int, M.Rollback], sources: List[str],
                 start_seq: int = 1) -> Tuple[str, List[dict]]:
        seq = start_seq
        blocks, meta = [], []
        author = self.p.get("author", "agent")
        if self.p.get("xml_changelog_dbms_precondition", True):
            blocks.append(self.tpl.render("changelog_preconditions", dbms=self.d))
        for name, value in (self.p.get("changelog_properties") or {}).items():
            blocks.append(self.tpl.render("property", name=name, value=value, extra=""))
        if self.p.get("tag_before_release", True):
            tid = self.namer.fmt(self.p.get("tag_changeset_id_pattern", "{release}-tag"))
            blocks.append(self.tpl.render("tag", id=tid, author=author, release=self.namer.release,
                                          tag=self.namer.fmt(self.p.get("tag_pattern", "{project}_{release}_pre"))))
        labels = self.namer.fmt(self.p.get("labels_pattern", "")) if self.p.get("labels_pattern") else None
        context = self.p.get("context") or None
        for u in units:
            for op in u.operations:
                if op.kind == M.COMMENT and u.operations[0].kind == M.CREATE_TABLE and op is not u.operations[0] \
                        and (op.table or "").upper() == u.operations[0].name.upper():
                    continue  # merged into createTable remarks
                rb = rollbacks.get(op.seq)
                for spec in self.builder.changes(op, u.operations, rb):
                    cid = self.namer.changeset_id(seq)
                    a = {"labels": labels, "context": context, **spec["attrs"]}
                    if self.p.get("xml_dbms_attr"):
                        a["dbms"] = self.d
                    comment = spec["comment"] or f"{op.kind} {op.qualified}"
                    src = f"{op.statement.source.split('/')[-1].split(chr(92))[-1]}:{op.statement.line_start}"
                    rb_xml = spec["rollback"] or "<!-- no rollback required -->"
                    blocks.append(self.tpl.render("changeset", id=cid, author=author, attrs=A(a),
                                                  comment=_esc(f"{comment} [source {src}]"),
                                                  preconditions=spec["pre"], changes=indent(spec["changes"], 8),
                                                  rollback=indent(rb_xml, 12)))
                    meta.append({"id": cid, "author": author, "op": op, "comment": comment,
                                 "rollback_complete": (spec["rb"].complete if spec["rb"] else True),
                                 "has_rollback": bool(spec["rollback"])})
                    seq += 1
        xml = self.tpl.render("changelog", title=f"Release {self.namer.release} - {self.p.get('project', '')}",
                              generated_at=_dt.datetime.now().strftime("%Y-%m-%d %H:%M"), sources=", ".join(sources),
                              dialect=self.d, xsd_version=self.p.get("xsd_version", "4.20"),
                              body="\n\n".join(blocks))
        return xml, meta


def _esc(s: str) -> str:
    from xml.sax.saxutils import escape
    return escape(s)


# =============================================================================== formatted SQL
class FormattedSqlGenerator:
    def __init__(self, dialect: str, profile: dict, tpl: Templates, namer: Namer, schema_model):
        self.d, self.p, self.tpl, self.namer, self.sm = dialect, profile, tpl, namer, schema_model
        self.tr = profile.get("tracker", {}) or {}

    # ------------------------------------------------------------- tracker helpers
    def _tracker_meta(self, u: M.ChangeUnit) -> dict:
        types = self.tr.get("unit_types", {})
        meta = dict(types.get(u.unit_type, {"object_type": u.unit_type.title(), "action": u.unit_type.title(),
                                             "count": "objects"}))
        ops = u.operations
        if u.unit_type == "TABLE" and any(o.kind == M.CREATE_INDEX for o in ops):
            meta["object_type"] = types.get("TABLE", {}).get("object_type_with_index", "Table/Index")
        if u.unit_type == "ROUTINE":
            meta["object_type"] = ops[0].object_type
            meta["action"] = f"Create or Replace {ops[0].object_type.title()}"
        if u.unit_type == "TRIGGER" and not any(o.or_replace for o in ops):
            meta["action"] = "Create Trigger"
        names = []
        for o in ops:
            if u.unit_type == "TABLE" and o.kind not in (M.CREATE_TABLE, M.CREATE_TABLE_AS):
                continue
            n = o.table if u.unit_type in ("ALTER", "DML") else o.name
            if u.unit_type == "INDEX":
                n = o.name
            if n and n not in names:
                names.append(n)
        if u.unit_type == "INDEX" and len(names) > 4:
            meta["object_name"] = self.tr.get("index_batch_label", "Supporting Indexes")
        else:
            meta["object_name"] = ", ".join(names)
        tables = sorted({(o.table or o.name).upper() for o in ops if o.table or o.name})
        meta["tables"] = tables
        return meta

    def _count_sql(self, key: str, schema: str, tables: List[str]) -> str:
        qs = self.tr.get("count_queries", {})
        pat = qs.get(key) or qs.get("objects") or "select count(*) from DBA_OBJECTS where OWNER = '{schema}'"
        if len(tables) == 1:
            pred = f"= '{tables[0]}'"
        else:
            pred = "IN (" + ",".join(f"'{t}'" for t in tables) + ")"
        return pat.format(schema=schema, table_pred=pred, table=tables[0] if tables else "", tables_in=pred)

    def _changeset_line(self, cid, attrs=""):
        return self.tpl.render("sql_changeset", author=self.p.get("author", "agent"), id=cid, attrs=attrs)

    # ------------------------------------------------------------- statement rendering
    def _stmt_text(self, ops: List[M.Operation], include_comments=True) -> List[Tuple[str, bool, str]]:
        """Unique statements of a unit in order: (sql, is_plsql, leading_comment)."""
        seen, out = set(), []
        for o in ops:
            sid = id(o.statement)
            if o.details.get("_synthetic"):
                out.append((o.sql, False, ""))
                continue
            if sid in seen:
                continue
            seen.add(sid)
            sql = o.statement.sql.strip()
            plsql = o.kind in M.PLSQL_KINDS
            if not plsql:
                sql = sql.rstrip().rstrip(";").rstrip()
            else:
                sql = re.sub(r"\n\s*/\s*$", "", sql).rstrip()
            out.append((sql, plsql, o.statement.leading_comment if include_comments else ""))
        return out

    def _banner(self, text: str) -> str:
        lines = "\n".join(f"-- {ln}" for ln in text.splitlines() if ln.strip())
        return self.tpl.render("banner", lines=lines)

    def _rollback_lines(self, stmts: List[str], plsql_cs: bool) -> List[str]:
        out = []
        for s in stmts:
            s = s.rstrip()
            if s.startswith("-- MANUAL"):
                out.append(f"-- ROLLBACK-MANUAL: {s[len('-- MANUAL:'):].strip()}")
                continue
            is_block = bool(re.match(r"^\s*(CREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?(TRIGGER|PROCEDURE|FUNCTION|PACKAGE|TYPE\s+BODY)|DECLARE|BEGIN)",
                                     s, re.I))
            if plsql_cs:
                body = s if is_block else s.rstrip(";")
                for ln in body.split("\n"):
                    out.append("--rollback " + ln)
                out.append("--rollback /")
            else:
                body = s if s.endswith(";") or is_block else s + ";"
                for ln in body.split("\n"):
                    out.append("--rollback " + ln)
        return out

    # ------------------------------------------------------------- main
    def generate(self, units: List[M.ChangeUnit], rollbacks: Dict[int, M.Rollback], start_seq: int = 1,
                 file_offset: int = 0) -> Tuple[Dict[str, str], List[dict]]:
        files: Dict[str, str] = {}
        meta = []
        seq = start_seq
        tracker_on = self.tr.get("enabled", False)
        tt = self.tr.get("table", "LIQUIBASE_APP.LIQUIBASE_DB_CHANGE_TRACKER")
        release_label = self.namer.fmt(self.tr.get("release_label", "{project} {release}"))
        plsql_attrs = self.p.get("plsql_changeset_attrs", " splitStatements:false")
        deploy_dir = self.namer.deploy_dir()
        for idx, u in enumerate(units):
            cid = self.namer.changeset_id(seq)
            fname = self.namer.file_name(u, idx + 1 + file_offset)
            u.changeset_id, u.file_name, u.seq = cid, fname, seq
            schema = (u.schema or self.p.get("default_schema") or "").upper()
            tm = self._tracker_meta(u)
            count_sql = self._count_sql(self.tr.get("unit_types", {}).get(u.unit_type, {}).get("count", "objects"),
                                        schema, tm["tables"])
            rbs = [rollbacks.get(o.seq) for o in _rollback_relevant(u.operations)]
            pre_sql = [s for r in rbs if r for s in r.pre_sql]
            rb_sql = [s for r in reversed([r for r in rbs if r]) for s in r.sql]
            complete = all(r.complete for r in rbs if r)
            notes = [n for r in rbs if r for n in r.notes]
            plsql = u.is_plsql
            out = [self.tpl.render("sql_file_header"), ""]
            if tracker_on:
                out.append(self._changeset_line(cid + "-pre"))
                out.append("")
                out.append(self.tpl.render("tracker_insert", tracker_table=tt, changeset_id=cid, schema=schema,
                                           script_name=fname, release_label=release_label, object_type=tm["object_type"],
                                           object_name=tm["object_name"], sql_location=self.tr.get("sql_location", "/opt/scripts/"),
                                           action=tm["action"], count_sql=count_sql, rollback_flag=0))
                out.append("")
                out.append("COMMIT;")
                if self.tr.get("rollback_lines", True):
                    out.append(self.tpl.render("tracker_insert_rollback", tracker_table=tt, changeset_id=cid))
                out.append("")
            if pre_sql:
                out.append(self._changeset_line(cid + "-bkp"))
                out.append(self._banner("Backup of data affected by this change (used by rollback)"))
                for s in pre_sql:
                    out.append(s.rstrip(";") + ";")
                for s in pre_sql:
                    out.append(f"--rollback DROP TABLE {u.schema + '.' if u.schema else ''}{_bkp_name(s)};")
                out.append("")
            cs_attrs = plsql_attrs if plsql else ""
            if any(o.details.get("concurrently") for o in u.operations):
                cs_attrs += " runInTransaction:false"
            out.append(self._changeset_line(cid, cs_attrs))
            out.append(f"--comment: {self._unit_comment(u)}")
            out.append("")
            for sql, is_pl, lead in self._stmt_text(u.operations):
                if lead and self.p.get("keep_source_comments", True):
                    out.append(self._banner(lead))
                if is_pl:
                    out.append(sql)
                else:
                    out.append(sql + ";")
                out.append("")
            if any(o.is_dml for o in u.operations) and not plsql:
                out.append("COMMIT;")
                out.append("")
            if self.p.get("inline_rollback", True):
                if notes:
                    out.append(self._banner("Rollback notes:\n" + "\n".join(dict.fromkeys(notes))))
                rl = self._rollback_lines(rb_sql, plsql)
                if not any(ln.startswith(("--rollback", "-- ROLLBACK-MANUAL")) for ln in rl):
                    rl.append("-- ROLLBACK-MANUAL: no automatic rollback could be generated - complete before release")
                out.extend(rl)
                out.append("")
            if tracker_on:
                out.append(self._changeset_line(cid + "-post"))
                out.append("")
                out.append(self.tpl.render("tracker_update", tracker_table=tt, changeset_id=cid, count_sql=count_sql))
                out.append("COMMIT;")
                if self.tr.get("rollback_lines", True):
                    out.append(self.tpl.render("tracker_update_rollback", tracker_table=tt, changeset_id=cid))
            files[f"{deploy_dir}/{fname}"] = "\n".join(out).rstrip() + "\n"
            meta.append({"id": cid, "file": fname, "unit": u, "rollback_complete": complete, "notes": notes,
                         "rollback_sql": rb_sql})
            seq += 1
        if self.p.get("rollback_script", True) and units:
            name, text = self._rollback_script(units, rollbacks, meta, tt, release_label)
            files[f"{self.namer.rollback_dir()}/{name}"] = text
        return files, meta

    def _unit_comment(self, u: M.ChangeUnit) -> str:
        kinds = []
        for o in u.operations:
            k = o.kind.replace("_", " ").title()
            if k not in kinds:
                kinds.append(k)
        return f"{', '.join(kinds)} - {', '.join(dict.fromkeys(o.name for o in u.operations))}"[:250]

    def _rollback_script(self, units, rollbacks, meta, tt, release_label):
        schema = (units[0].schema or self.p.get("default_schema") or "").upper()
        name = self.namer.rollback_file_name(schema)
        first = meta[0]["id"]
        rid = self.namer.rollback_id(first)
        needs_pl = any(re.match(r"^\s*CREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?(TRIGGER|PROCEDURE|FUNCTION|PACKAGE|TYPE)", s, re.I)
                       for m in meta for s in m["rollback_sql"])
        tracker_on = self.tr.get("enabled", False)
        out = [self.tpl.render("sql_file_header"), ""]
        cnt = self._count_sql("rollback", schema, [])
        if tracker_on:
            out.append(self._changeset_line(rid + "-pre"))
            out.append("")
            out.append(self.tpl.render("tracker_insert", tracker_table=tt, changeset_id=rid, schema=schema,
                                       script_name=name, release_label=release_label, object_type="Multiple",
                                       object_name=f"Release {self.namer.release} rollback",
                                       sql_location=self.tr.get("sql_location", "/opt/scripts/"),
                                       action="Rollback", count_sql=cnt, rollback_flag=1))
            out.append("COMMIT;")
            if self.tr.get("rollback_lines", True):
                out.append(self.tpl.render("tracker_insert_rollback", tracker_table=tt, changeset_id=rid))
            out.append("")
        out.append(self._changeset_line(rid, self.p.get("plsql_changeset_attrs", " splitStatements:false") if needs_pl else ""))
        out.append(f"--comment: Rollback of release {self.namer.release} (reverse order of deploy scripts)")
        out.append("")
        step = 1
        # objects created by this release: later alterations of them are superseded by their DROP
        created_new, first_seq = set(), {}
        for m in meta:
            for o in m["unit"].operations:
                k = (o.qualified or "").upper()
                if o.kind in (M.CREATE_TABLE, M.CREATE_TABLE_AS, M.CREATE_SEQUENCE) or (
                        o.kind in M.REPLACEABLE_KINDS and isinstance(rollbacks.get(o.seq), M.Rollback)
                        and any(x.upper().startswith("DROP ") for x in rollbacks[o.seq].sql)):
                    if k not in first_seq:
                        first_seq[k] = o.seq
                        created_new.add(k)
        for m in reversed(meta):
            ops = _rollback_relevant(m["unit"].operations)
            stmts, notes, skipped = [], [], []
            for o in reversed(ops):
                rb = rollbacks.get(o.seq)
                if not rb:
                    continue
                tkey = (f"{o.schema}.{o.table}" if o.schema else (o.table or "")).upper()
                okey = (o.qualified or "").upper()
                superseded = (okey in created_new and o.seq > first_seq[okey]) or \
                    (o.kind not in (M.CREATE_TABLE, M.CREATE_TABLE_AS) and tkey in created_new and o.seq > first_seq.get(tkey, 10 ** 9)
                     and o.kind not in M.REPLACEABLE_KINDS)
                if superseded:
                    skipped.append(o.name)
                    continue
                stmts.extend(rb.sql)
                notes.extend(rb.notes)
            hdr = f"{step}) Reverse {m['file']} ({m['id']})"
            if skipped:
                hdr += "\nSuperseded: object(s) " + ", ".join(dict.fromkeys(skipped)) + " are created in this release and dropped later in this script."
            hdr += "".join(f"\nNOTE: {n}" for n in dict.fromkeys(notes))
            out.append(self._banner(hdr))
            if not stmts and not skipped:
                out.append("-- ROLLBACK-MANUAL: nothing generated for this script")
            for s in stmts:
                if s.startswith("-- MANUAL"):
                    out.append(f"-- ROLLBACK-MANUAL: {s[len('-- MANUAL:'):].strip()}")
                    continue
                is_block = bool(re.match(r"^\s*(CREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?(TRIGGER|PROCEDURE|FUNCTION|PACKAGE|TYPE\s+BODY)|DECLARE|BEGIN)", s, re.I))
                if needs_pl:
                    out.append((s if is_block else s.rstrip(";")))
                    out.append("/")
                else:
                    out.append(s.rstrip(";") + ";")
            out.append("")
            step += 1
        out.append("-- Forward-only rollback script: to undo it, re-run the release deploy scripts.")
        out.append("--rollback " + ("SELECT 1 FROM DUAL" if self.d == "oracle" else "SELECT 1") + ";")
        out.append("")
        if tracker_on:
            out.append(self._changeset_line(rid + "-post"))
            out.append("")
            out.append(self.tpl.render("tracker_update", tracker_table=tt, changeset_id=rid, count_sql=cnt))
            out.append("COMMIT;")
            if self.tr.get("rollback_lines", True):
                out.append(self.tpl.render("tracker_update_rollback", tracker_table=tt, changeset_id=rid))
        return name, "\n".join(out).rstrip() + "\n"


def _rollback_relevant(ops: List[M.Operation]) -> List[M.Operation]:
    """Drop rollbacks made redundant by a DROP of the parent object in the same unit
    (comments/grants/indexes/constraints on a table created in the same script)."""
    created = {(o.qualified or "").upper() for o in ops if o.kind in (M.CREATE_TABLE, M.CREATE_TABLE_AS, M.CREATE_SEQUENCE,
                                                                       M.CREATE_VIEW)}
    out = []
    for o in ops:
        if o.kind in (M.COMMENT, M.GRANT, M.CREATE_INDEX, M.ADD_CONSTRAINT) and o.kind != M.CREATE_TABLE:
            parent = (f"{o.schema}.{o.table}" if o.schema else (o.table or "")).upper()
            if o.kind == M.GRANT:
                parent = (o.qualified or "").upper()
            if parent in created:
                continue
        out.append(o)
    return out
