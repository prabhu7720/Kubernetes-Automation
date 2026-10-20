"""In-memory schema model.

Built offline from (a) existing DDL / DBMS_METADATA exports, (b) existing Liquibase
changelogs and (c) the operations being analysed. Each new operation is *applied*
in order, which gives us:
  * object-conflict detection (create existing, alter missing, duplicate names)
  * the BEFORE image of every object, used to build exact rollbacks
    (dropped column definitions, previous view/trigger/procedure source, ...)
"""
from __future__ import annotations

import copy
import re
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core import models as M


@dataclass
class TableDef:
    schema: Optional[str]
    name: str
    columns: "OrderedDict[str, M.Column]" = field(default_factory=OrderedDict)
    constraints: Dict[str, M.Constraint] = field(default_factory=dict)
    comments: Dict[str, str] = field(default_factory=dict)   # '' -> table comment, COL -> column comment
    options: str = ""
    tablespace: Optional[str] = None
    origin: str = "baseline"   # baseline | changelog | new


class SchemaModel:
    def __init__(self, default_schema: Optional[str] = None):
        self.default_schema = (default_schema or "").upper() or None
        self.tables: Dict[str, TableDef] = {}
        self.indexes: Dict[str, dict] = {}
        self.views: Dict[str, dict] = {}
        self.triggers: Dict[str, dict] = {}
        self.routines: Dict[str, dict] = {}
        self.sequences: Dict[str, dict] = {}
        self.constraint_owner: Dict[str, str] = {}   # constraint key -> table key
        self.grants: List[dict] = []
        self.loaded_sources: List[str] = []

    # ------------------------------------------------------------ keys
    def key(self, schema: Optional[str], name: Optional[str]) -> str:
        s = (schema or self.default_schema or "").upper()
        return f"{s}.{(name or '').upper()}" if s else (name or "").upper()

    @property
    def has_baseline(self) -> bool:
        return bool(self.loaded_sources)

    def table(self, schema, name) -> Optional[TableDef]:
        return self.tables.get(self.key(schema, name))

    def object_exists(self, otype: str, schema, name) -> bool:
        k = self.key(schema, name)
        store = {"TABLE": self.tables, "INDEX": self.indexes, "VIEW": self.views, "TRIGGER": self.triggers,
                 "SEQUENCE": self.sequences}.get(otype, self.routines)
        return k in store

    def covering_index(self, schema, table, cols: List[str]) -> Optional[str]:
        """Index / PK / UK whose leading columns equal `cols` (order-insensitive prefix)."""
        want = [c.upper() for c in cols]
        tkey = self.key(schema, table)
        for ik, ix in self.indexes.items():
            if ix["table_key"] == tkey:
                lead = [c.upper() for c in ix["columns"][:len(want)]]
                if sorted(lead) == sorted(want):
                    return ik.split(".")[-1]
        t = self.tables.get(tkey)
        if t:
            for cn, c in t.constraints.items():
                if c.ctype in ("PRIMARY KEY", "UNIQUE"):
                    lead = [x.upper() for x in c.columns[:len(want)]]
                    if sorted(lead) == sorted(want):
                        return c.name or cn
        return None

    def dependents_on_column(self, schema, table, columns: List[str]) -> List[dict]:
        """Views / triggers / routines whose source references table AND column token."""
        out = []
        tname = (table or "").upper()
        cols = [c.upper() for c in columns]
        for store, otype in ((self.views, "VIEW"), (self.triggers, "TRIGGER"), (self.routines, "ROUTINE")):
            for k, obj in store.items():
                src = (obj.get("sql") or "").upper()
                if not re.search(r"\b" + re.escape(tname) + r"\b", src):
                    continue
                hit = [c for c in cols if re.search(r"(?<![\w$#])" + re.escape(c) + r"(?![\w$#])", src)]
                if hit:
                    out.append({"type": otype, "name": k, "columns": hit})
        return out

    def dependents_on_table(self, schema, table) -> List[dict]:
        out = []
        tname = (table or "").upper()
        for store, otype in ((self.views, "VIEW"), (self.triggers, "TRIGGER"), (self.routines, "ROUTINE")):
            for k, obj in store.items():
                if obj.get("table_key") == self.key(schema, table) or re.search(
                        r"\b" + re.escape(tname) + r"\b", (obj.get("sql") or "").upper()):
                    out.append({"type": otype, "name": k})
        for k, t in self.tables.items():
            for c in t.constraints.values():
                if c.ctype == "FOREIGN KEY" and (c.ref_table or "").upper() == tname and k != self.key(schema, table):
                    out.append({"type": "FOREIGN KEY", "name": f"{k}.{c.name}"})
        return out

    def find_constraint(self, schema, name) -> Optional[tuple]:
        if not name:
            return None
        ck = self.key(schema, name)
        tk = self.constraint_owner.get(ck)
        if tk and tk in self.tables:
            c = self.tables[tk].constraints.get(name.upper())
            if c:
                return tk, c
        return None

    # ------------------------------------------------------------ apply
    def apply(self, op: M.Operation, origin: str = "new") -> dict:
        """Apply an operation. Returns {'before': ..., 'conflicts': [Finding], 'existed': bool}."""
        res = {"before": None, "conflicts": [], "existed": False, "implicit": {}}
        fn = getattr(self, "_apply_" + op.kind.lower(), None)
        if fn:
            fn(op, res, origin)
        return res

    def _conf(self, res, sev, code, msg, rec=""):
        res["conflicts"].append(M.Finding(sev, code, msg, rec, "conflict"))

    def _apply_create_table(self, op, res, origin):
        k = self.key(op.schema, op.name)
        if k in self.tables:
            res["existed"] = True
            self._conf(res, "HIGH", "OBJ_EXISTS", f"Table {k} already exists ({self.tables[k].origin}).",
                       "Use a precondition (tableExists -> MARK_RAN) or remove the duplicate CREATE.")
        t = TableDef(op.schema, op.name, origin=origin, options=op.details.get("options", ""),
                     tablespace=op.details.get("tablespace"))
        for c in op.details.get("columns", []):
            t.columns[c.name.upper()] = copy.deepcopy(c)
            if c.remarks:
                t.comments[c.name.upper()] = c.remarks
        if op.details.get("remarks"):
            t.comments[""] = op.details["remarks"]
        self.tables[k] = t
        for c in op.details.get("constraints", []):
            self._add_constraint(op.schema, t, c, res)
        for ix in op.details.get("inline_indexes", []):
            if ix.get("name"):
                self.indexes[self.key(op.schema, ix["name"])] = {"table_key": k, "columns": ix["columns"],
                                                                 "unique": False, "sql": ""}

    _apply_create_table_as = _apply_create_table

    def _add_constraint(self, schema, t: TableDef, c, res):
        if not isinstance(c, M.Constraint):
            return
        name = (c.name or f"SYS_{c.ctype.split()[0]}_{len(t.constraints) + 1}").upper()
        ck = self.key(schema, name)
        if c.name and ck in self.constraint_owner and self.constraint_owner[ck] != self.key(t.schema, t.name):
            self._conf(res, "HIGH", "CONSTRAINT_NAME_EXISTS",
                       f"Constraint name {name} is already used on {self.constraint_owner[ck]}.",
                       "Constraint names must be unique per schema (Oracle/PostgreSQL).")
        elif c.name and name in t.constraints:
            self._conf(res, "HIGH", "CONSTRAINT_EXISTS", f"Constraint {name} already exists on {t.name}.")
        t.constraints[name] = c
        self.constraint_owner[ck] = self.key(t.schema, t.name)
        if c.ctype in ("PRIMARY KEY", "UNIQUE"):
            for col in c.columns:
                cc = t.columns.get(col.upper())
                if cc and c.ctype == "PRIMARY KEY":
                    cc.nullable = False

    def _table_or_note(self, op, res) -> Optional[TableDef]:
        t = self.tables.get(self.key(op.schema, op.table or op.name))
        if t is None and self.has_baseline:
            self._conf(res, "MEDIUM", "OBJ_NOT_FOUND",
                       f"Table {self.key(op.schema, op.table or op.name)} not found in the supplied baseline.",
                       "Verify the table exists in the target environment (see pre-check SQL).")
        return t

    def _apply_drop_table(self, op, res, origin):
        k = self.key(op.schema, op.name)
        t = self.tables.pop(k, None)
        if t is None:
            self._table_or_note(op, res)
        res["before"] = t
        res["implicit"]["indexes"] = {ik: ix for ik, ix in self.indexes.items() if ix["table_key"] == k}
        res["implicit"]["triggers"] = {tk: tr for tk, tr in self.triggers.items() if tr.get("table_key") == k}
        for ik in list(res["implicit"]["indexes"]):
            self.indexes.pop(ik, None)
        for tk in list(res["implicit"]["triggers"]):
            self.triggers.pop(tk, None)

    def _apply_add_column(self, op, res, origin):
        t = self._table_or_note(op, res)
        if not t:
            return
        for c in op.details.get("columns", []):
            if c.name.upper() in t.columns:
                self._conf(res, "HIGH", "COLUMN_EXISTS", f"Column {t.name}.{c.name} already exists.",
                           "Use a columnExists precondition or remove the duplicate ADD.")
            t.columns[c.name.upper()] = copy.deepcopy(c)

    def _apply_modify_column(self, op, res, origin):
        t = self._table_or_note(op, res)
        if not t:
            return
        before = {}
        for c in op.details.get("columns", []):
            old_name = (op.details.get("old_name") or c.name).upper()
            cur = t.columns.get(old_name)
            if cur is None:
                if t.columns:
                    self._conf(res, "HIGH", "COLUMN_NOT_FOUND", f"Column {t.name}.{old_name} not found.")
                continue
            before[old_name] = copy.deepcopy(cur)
            if c.data_type:
                cur.data_type = c.data_type
            if c.nullable is not None:
                cur.nullable = c.nullable
            if c.default is not None:
                cur.default = c.default
            if op.details.get("drop_default"):
                cur.default = None
            if old_name != c.name.upper():
                cur.name = c.name
                t.columns[c.name.upper()] = t.columns.pop(old_name)
        res["before"] = before

    def _apply_drop_column(self, op, res, origin):
        t = self._table_or_note(op, res)
        if not t:
            return
        before, dropped_cons, dropped_idx, comments = OrderedDict(), {}, {}, {}
        cols = [c.upper() for c in op.details.get("columns", [])]
        for c in cols:
            if c not in t.columns:
                if t.columns:
                    self._conf(res, "HIGH", "COLUMN_NOT_FOUND", f"Column {t.name}.{c} not found - DROP will fail.")
                continue
            before[c] = t.columns.pop(c)
            if c in t.comments:
                comments[c] = t.comments.pop(c)
        for cn, con in list(t.constraints.items()):
            cc = [x.upper() for x in con.columns]
            refs_col = any(c in cc for c in cols) or (con.ctype == "CHECK" and any(
                re.search(r"\b" + c + r"\b", (con.check_expr or "").upper()) for c in cols))
            if refs_col:
                dropped_cons[cn] = t.constraints.pop(cn)
        tkey = self.key(t.schema, t.name)
        for ik, ix in list(self.indexes.items()):
            if ix["table_key"] == tkey and any(c.upper() in cols for c in ix["columns"]):
                dropped_idx[ik] = self.indexes.pop(ik)
        res["before"] = before
        res["implicit"] = {"constraints": dropped_cons, "indexes": dropped_idx, "comments": comments}

    def _apply_rename_column(self, op, res, origin):
        t = self._table_or_note(op, res)
        if t:
            old, new = op.details["column"].upper(), op.details["new_name"]
            if old in t.columns:
                col = t.columns.pop(old)
                col.name = new
                t.columns[new.upper()] = col

    def _apply_rename_table(self, op, res, origin):
        k = self.key(op.schema, op.table or op.name)
        if k in self.tables:
            t = self.tables.pop(k)
            t.name = op.details["new_name"]
            self.tables[self.key(op.schema, t.name)] = t

    def _apply_add_constraint(self, op, res, origin):
        t = self._table_or_note(op, res)
        c = op.details.get("constraint")
        if t and isinstance(c, M.Constraint):
            self._add_constraint(op.schema, t, c, res)

    def _apply_drop_constraint(self, op, res, origin):
        t = self._table_or_note(op, res)
        name = (op.details.get("constraint_name") or "").upper()
        if not t:
            return
        if not name and op.details.get("ctype") == "PRIMARY KEY":
            name = next((n for n, c in t.constraints.items() if c.ctype == "PRIMARY KEY"), "")
        con = t.constraints.pop(name, None)
        if con is None and t.columns:
            self._conf(res, "MEDIUM", "CONSTRAINT_NOT_FOUND", f"Constraint {name} not found on {t.name}.")
        if con:
            self.constraint_owner.pop(self.key(op.schema, name), None)
        res["before"] = con

    def _apply_create_index(self, op, res, origin):
        k = self.key(op.schema, op.name)
        if k in self.indexes:
            res["existed"] = True
            self._conf(res, "HIGH", "OBJ_EXISTS", f"Index {k} already exists.",
                       "Use an indexExists precondition or rename the index.")
        tkey = self.key(op.details.get("table_schema") or op.schema, op.table)
        cols = [c["name"] for c in op.details.get("columns", [])]
        self.indexes[k] = {"table_key": tkey, "columns": cols, "unique": op.details.get("unique"),
                           "sql": op.sql, "tablespace": op.details.get("tablespace")}

    def _apply_drop_index(self, op, res, origin):
        k = self.key(op.schema, op.name)
        res["before"] = self.indexes.pop(k, None)
        if res["before"] is None and self.has_baseline:
            self._conf(res, "MEDIUM", "OBJ_NOT_FOUND", f"Index {k} not found in the supplied baseline.")

    def _replaceable(self, store, op, res, extra=None):
        k = self.key(op.schema, op.name)
        if k in store:
            res["existed"] = True
            res["before"] = copy.deepcopy(store[k])
            if not op.or_replace:
                self._conf(res, "HIGH", "OBJ_EXISTS", f"{op.object_type} {k} already exists and statement is not "
                           f"CREATE OR REPLACE.", "Use CREATE OR REPLACE (or a precondition).")
        entry = {"sql": op.sql, "type": op.object_type, "origin": "new"}
        entry.update(extra or {})
        store[k] = entry

    def _apply_create_view(self, op, res, origin):
        self._replaceable(self.views, op, res, {"columns": op.details.get("columns", [])})

    def _apply_create_trigger(self, op, res, origin):
        self._replaceable(self.triggers, op, res, {"table_key": self.key(op.schema, op.table)})

    def _apply_create_procedure(self, op, res, origin):
        self._replaceable(self.routines, op, res)

    _apply_create_function = _apply_create_procedure
    _apply_create_package = _apply_create_procedure
    _apply_create_package_body = _apply_create_procedure

    def _drop_from(self, store, op, res):
        k = self.key(op.schema, op.name)
        res["before"] = store.pop(k, None)
        if res["before"] is None and self.has_baseline:
            self._conf(res, "MEDIUM", "OBJ_NOT_FOUND", f"{op.object_type} {k} not found in the supplied baseline.")

    def _apply_drop_view(self, op, res, origin):
        self._drop_from(self.views, op, res)

    def _apply_drop_trigger(self, op, res, origin):
        self._drop_from(self.triggers, op, res)

    def _apply_drop_routine(self, op, res, origin):
        self._drop_from(self.routines, op, res)

    def _apply_create_sequence(self, op, res, origin):
        k = self.key(op.schema, op.name)
        if k in self.sequences:
            res["existed"] = True
            self._conf(res, "HIGH", "OBJ_EXISTS", f"Sequence {k} already exists.",
                       "Use a sequenceExists precondition.")
        self.sequences[k] = {"sql": op.sql, **op.details}

    def _apply_drop_sequence(self, op, res, origin):
        self._drop_from(self.sequences, op, res)

    def _apply_comment(self, op, res, origin):
        t = self.tables.get(self.key(op.schema, op.table))
        target = op.details.get("target")
        col = (op.details.get("column") or "").upper() if target == "COLUMN" else ""
        if t:
            res["before"] = t.comments.get(col)
            t.comments[col] = op.details.get("text", "")
        else:
            v = self.views.get(self.key(op.schema, op.table))
            if v is not None:
                res["before"] = v.get("comment")
                v["comment"] = op.details.get("text")

    def _apply_grant(self, op, res, origin):
        self.grants.append({"object": self.key(op.schema, op.name), **op.details})

    # ------------------------------------------------------------ loading
    def load_operations(self, ops: List[M.Operation], source: str, origin: str = "baseline"):
        for op in ops:
            self.apply(op, origin=origin)
        self.loaded_sources.append(source)
