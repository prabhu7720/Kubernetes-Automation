"""Statement-level parser: turns a raw SQL statement into one or more Operations.

Rule based (no external libraries). Supports Oracle, PostgreSQL, MySQL, MariaDB and
SQL Server DDL/DML/PLSQL syntax that appears in day-to-day release scripts.
"""
from __future__ import annotations

import re
from typing import List, Optional, Tuple

from core import models as M
from core.lexer import (QIDENT, STRING, WORD, Token, match_paren, read_qualified, split_top,
                        strip_comments, text_of, tokenize)

COL_STOP = {"DEFAULT", "NOT", "NULL", "CONSTRAINT", "PRIMARY", "UNIQUE", "REFERENCES", "CHECK",
            "GENERATED", "AUTO_INCREMENT", "COLLATE", "COMMENT", "ENABLE", "DISABLE", "VISIBLE",
            "INVISIBLE", "ENCRYPT", "SPARSE", "ROWGUIDCOL", "FILESTREAM", "USING", "FIRST", "AFTER",
            "IDENTITY", "CHARSET", "SORT", "NOVALIDATE", "ON", "AS"}
TABLE_CONSTRAINT_START = {"CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK", "KEY", "INDEX",
                          "FULLTEXT", "SPATIAL", "PERIOD", "EXCLUDE"}
CREATE_MODIFIERS = {"OR", "REPLACE", "ALTER", "FORCE", "NOFORCE", "EDITIONABLE", "NONEDITIONABLE",
                    "GLOBAL", "TEMPORARY", "TEMP", "UNLOGGED", "UNIQUE", "BITMAP", "CLUSTERED",
                    "NONCLUSTERED", "PUBLIC", "FULLTEXT", "SPATIAL", "SECURE", "RECURSIVE", "EDITIONING",
                    "PRIVATE", "SHARED", "IMMUTABLE", "MULTIDIMENSIONAL", "BLOCKCHAIN"}
REF_RE = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE|MERGE\s+INTO|DELETE\s+FROM|TRUNCATE\s+TABLE)\s+"
                    r"((?:\"?[A-Za-z_][\w$#]*\"?\.)?\"?[A-Za-z_][\w$#]*\"?)", re.IGNORECASE)
NOT_TABLES = {"DUAL", "SELECT", "TABLE", "THE", "V_", "LATERAL", "UNNEST", "GENERATE_SERIES", "VALUES"}


def _u(t: Optional[Token]) -> str:
    return t.value.upper() if t is not None and t.type == WORD else (t.value if t is not None else "")


def referenced_objects(sql: str) -> List[str]:
    found = []
    clean = strip_comments(sql)
    clean = re.sub(r"'(?:[^']|'')*'", "''", clean)
    for m in REF_RE.finditer(clean):
        name = m.group(1).replace('"', "")
        base = name.split(".")[-1].upper()
        if base in NOT_TABLES or base.startswith(":") or base.startswith("V_") and "." not in name:
            continue
        if name.upper() not in [f.upper() for f in found]:
            found.append(name)
    return found


class DDLParser:
    def __init__(self, dialect: str, default_schema: Optional[str] = None,
                 tracker_table: Optional[str] = None):
        self.d = dialect
        self.default_schema = default_schema
        self.tracker_table = (tracker_table or "").upper()

    # ================================================================ entry
    def parse(self, stmt: M.Statement) -> List[M.Operation]:
        if stmt.delimiter == "EOL":
            return [self._op(M.CLIENT_COMMAND, None, stmt.sql.split()[0], stmt, object_type="CLIENT")]
        sql = strip_comments(stmt.sql, mysql_hash=self.d in ("mysql", "mariadb"))
        toks = tokenize(sql)
        while toks and toks[-1].is_sym(";", "/"):
            toks.pop()
        if not toks:
            return []
        self.sql, self.toks, self.stmt = sql, toks, stmt
        w0, w1 = _u(toks[0]), _u(toks[1]) if len(toks) > 1 else ""
        if self.tracker_table and self.tracker_table in sql.upper().replace('"', "") and w0 in (
                "INSERT", "UPDATE", "DELETE", "MERGE"):
            return [self._op(M.TRACKER, None, self.tracker_table, stmt, object_type="TRACKER")]
        if w0 in ("COMMIT", "ROLLBACK", "SAVEPOINT") or (w0 == "START" and w1 == "TRANSACTION") or \
                (w0 == "BEGIN" and (len(toks) == 1 or w1 in ("TRAN", "TRANSACTION", "WORK"))):
            return [self._op(M.TX_CONTROL, None, w0, stmt, object_type="TX")]
        if w0 in ("DECLARE", "BEGIN") or (w0 == "DO" and self.d == "postgresql"):
            return [self._op(M.PLSQL_BLOCK, None, "ANONYMOUS_BLOCK", stmt, object_type="BLOCK",
                             details={"references": referenced_objects(stmt.sql)})]
        try:
            if w0 == "CREATE":
                return self._create()
            if w0 == "ALTER" and w1 == "TABLE":
                return self._alter_table()
            if w0 == "ALTER" and w1 == "SEQUENCE":
                s, n, _, _ = read_qualified(toks, 2)
                return [self._op(M.ALTER_SEQUENCE, s, n, stmt, object_type="SEQUENCE")]
            if w0 == "DROP":
                return self._drop()
            if w0 == "COMMENT" and w1 == "ON":
                return self._comment()
            if w0 in ("GRANT", "REVOKE"):
                return self._grant(w0)
            if w0 in ("INSERT", "UPDATE", "DELETE", "MERGE", "UPSERT", "REPLACE"):
                return self._dml(w0)
            if w0 == "TRUNCATE":
                i = 2 if w1 == "TABLE" else 1
                s, n, _, _ = read_qualified(toks, i)
                return [self._op(M.TRUNCATE_TABLE, s, n, stmt, object_type="TABLE")]
            if w0 == "RENAME":
                s, n, i, _ = read_qualified(toks, 1)
                new = toks[i + 1].value if i + 1 < len(toks) else "?"
                return [self._op(M.RENAME_TABLE, s, n, stmt, table=n, object_type="TABLE",
                                 details={"new_name": new})]
            if w0 in ("EXEC", "EXECUTE") and "SP_RENAME" in sql.upper():
                return [self._op(M.ALTER_TABLE_RAW, None, "sp_rename", stmt, object_type="TABLE",
                                 details={"action": "RENAME"})]
        except Exception as exc:  # parsing must never crash the agent
            return [self._op(M.OTHER, None, w0, stmt, object_type="UNKNOWN",
                             details={"parse_error": str(exc)})]
        return [self._op(M.OTHER, None, w0, stmt, object_type="UNKNOWN")]

    # ================================================================ helpers
    def _op(self, kind, schema, name, stmt, sql=None, **kw) -> M.Operation:
        return M.Operation(kind=kind, schema=schema or self.default_schema, name=name or "?",
                           sql=(sql if sql is not None else stmt.sql).strip().rstrip(";").rstrip()
                           if kind not in M.PLSQL_KINDS else (sql or stmt.sql).strip(),
                           statement=stmt, **kw)

    def _txt(self, toks: List[Token]) -> str:
        return text_of(self.sql, toks)

    def _col_names(self, toks: List[Token]) -> List[str]:
        out = []
        for part in split_top(toks):
            part = [t for t in part if not t.is_word("ASC", "DESC")]
            if len(part) == 1 and part[0].type in (WORD, QIDENT):
                out.append(part[0].value)
            elif part:
                out.append(self._txt(part))
        return out

    # ================================================================ CREATE
    def _create(self) -> List[M.Operation]:
        toks, i = self.toks, 1
        flags = set()
        while i < len(toks):
            u = _u(toks[i])
            if u in CREATE_MODIFIERS:
                flags.add(u)
                i += 1
            elif u in ("DEFINER", "ALGORITHM") and i + 1 < len(toks) and toks[i + 1].is_sym("="):
                i += 3
                while i < len(toks) and (toks[i].is_sym("@") or (toks[i - 1].is_sym("@"))):
                    i += 1
            elif u == "SQL" and _u(toks[i + 1]) == "SECURITY":
                i += 3
            else:
                break
        obj = _u(toks[i])
        or_replace = ("REPLACE" in flags) or ("ALTER" in flags)
        if obj == "MATERIALIZED":
            i += 1
            obj = "MATERIALIZED VIEW"
        if obj == "TABLE":
            return self._create_table(i + 1, flags)
        if obj == "INDEX":
            return self._create_index(i + 1, flags)
        if obj == "SEQUENCE":
            return self._create_sequence(i + 1)
        if obj in ("VIEW", "MATERIALIZED VIEW"):
            return self._create_view(i + 1, flags, obj)
        if obj == "TRIGGER":
            return self._create_trigger(i + 1, or_replace)
        if obj in ("PROCEDURE", "PROC", "FUNCTION", "PACKAGE", "TYPE"):
            body = obj == "PACKAGE" and _u(toks[i + 1]) == "BODY"
            tbody = obj == "TYPE" and _u(toks[i + 1]) == "BODY"
            j = i + (2 if (body or tbody) else 1)
            s, n, _, _ = read_qualified(toks, j)
            kind = {"PROCEDURE": M.CREATE_PROCEDURE, "PROC": M.CREATE_PROCEDURE,
                    "FUNCTION": M.CREATE_FUNCTION, "PACKAGE": M.CREATE_PACKAGE,
                    "TYPE": M.CREATE_PACKAGE}[obj]
            if body or tbody:
                kind = M.CREATE_PACKAGE_BODY
            otype = {"PROC": "PROCEDURE"}.get(obj, obj) + (" BODY" if body or tbody else "")
            return [self._op(kind, s, n, self.stmt, object_type=otype, or_replace=or_replace,
                             details={"references": referenced_objects(self.stmt.sql),
                                      "language": self._language()})]
        if obj == "SYNONYM":
            s, n, _, _ = read_qualified(toks, i + 1)
            return [self._op(M.OTHER, s, n, self.stmt, object_type="SYNONYM", or_replace=or_replace)]
        s, n, _, _ = read_qualified(toks, i + 1)
        return [self._op(M.OTHER, s, n, self.stmt, object_type=obj)]

    def _language(self) -> str:
        m = re.search(r"\bLANGUAGE\s+(\w+)", self.sql, re.IGNORECASE)
        return m.group(1).lower() if m else ""

    # ---------------------------------------------------------------- table
    def _create_table(self, i: int, flags) -> List[M.Operation]:
        toks = self.toks
        if _u(toks[i]) == "IF":
            i += 3
        schema, name, i, _ = read_qualified(toks, i)
        details = {"temporary": bool(flags & {"TEMPORARY", "TEMP", "GLOBAL"}), "columns": [],
                   "constraints": [], "inline_indexes": []}
        if i < len(toks) and (toks[i].is_word("AS") or (toks[i].is_sym("(") and _u(toks[i + 1]) == "SELECT")):
            details["select"] = self._txt(toks[i + 1:])
            return [self._op(M.CREATE_TABLE_AS, schema, name, self.stmt, table=name,
                             object_type="TABLE", details=details)]
        if i >= len(toks) or not toks[i].is_sym("("):
            return [self._op(M.CREATE_TABLE, schema, name, self.stmt, table=name, object_type="TABLE",
                             details=details)]
        close = match_paren(toks, i)
        for part in split_top(toks[i + 1:close]):
            if not part:
                continue
            if _u(part[0]) in TABLE_CONSTRAINT_START and not (
                    _u(part[0]) in ("KEY", "INDEX") and len(part) > 1 and part[1].type in (WORD, QIDENT)
                    and _u(part[1]) not in ("(",) and self.d not in ("mysql", "mariadb")):
                c = self._table_constraint(part)
                if isinstance(c, M.Constraint):
                    details["constraints"].append(c)
                elif c:
                    details["inline_indexes"].append(c)
            else:
                col = self._column(part)
                details["columns"].append(col)
        # promote inline column constraints to table-level knowledge
        for col in details["columns"]:
            if col.primary_key:
                details["constraints"].append(M.Constraint(col.pk_name, "PRIMARY KEY", [col.name]))
            if col.unique:
                details["constraints"].append(M.Constraint(col.unique_name, "UNIQUE", [col.name]))
            if col.references:
                r = col.references
                details["constraints"].append(M.Constraint(r.get("name"), "FOREIGN KEY", [col.name],
                                                           r.get("schema"), r.get("table"),
                                                           r.get("columns", []), r.get("on_delete")))
            if col.check:
                details["constraints"].append(M.Constraint(col.check_name, "CHECK", [col.name],
                                                           check_expr=col.check))
        opts = toks[close + 1:]
        details["options"] = self._txt(opts)
        for k, t in enumerate(opts):
            if t.is_word("TABLESPACE") and k + 1 < len(opts):
                details["tablespace"] = opts[k + 1].value
            if t.is_word("NOLOGGING"):
                details["nologging"] = True
            if t.is_word("PARTITION"):
                details["partitioned"] = True
            if t.is_word("ENGINE") and k + 2 < len(opts):
                details["engine"] = opts[k + 2].value
            if t.is_word("COMMENT") and k + 1 < len(opts):
                nxt = opts[k + 2] if opts[k + 1].is_sym("=") and k + 2 < len(opts) else opts[k + 1]
                if nxt.type == STRING:
                    details["remarks"] = _unquote(nxt.value)
        return [self._op(M.CREATE_TABLE, schema, name, self.stmt, table=name, object_type="TABLE",
                         details=details)]

    def _column(self, part: List[Token]) -> M.Column:
        name = part[0].value
        k = 1
        while k < len(part):
            t = part[k]
            u = _u(t)
            if t.type == WORD and u in COL_STOP:
                if u == "CHARACTER" and _u(part[k + 1]) == "SET":
                    break
                if u == "ON" and k > 1:
                    break
                if u == "AS" and k > 1:
                    break
                if u in ("ON", "AS"):
                    k += 1
                    continue
                if u == "IDENTITY" and self.d != "mssql":
                    break
                break
            if t.is_sym("("):
                k = match_paren(part, k) + 1
                continue
            k += 1
        col = M.Column(name=name, data_type=self._txt(part[1:k]), raw=self._txt(part))
        if col.data_type.upper() in ("SERIAL", "BIGSERIAL", "SMALLSERIAL"):
            col.auto_increment = True
        self._column_attrs(col, part, k)
        return col

    def _column_attrs(self, col: M.Column, part: List[Token], k: int):
        pending = None
        while k < len(part):
            t, u = part[k], _u(part[k])
            nxt = _u(part[k + 1]) if k + 1 < len(part) else ""
            if u == "CONSTRAINT":
                pending = part[k + 1].value
                k += 2
                continue
            if u == "NOT" and nxt == "NULL":
                col.nullable = False
                k += 2
                pending = None
                continue
            if u == "NULL":
                col.nullable = True
                k += 1
                continue
            if u == "DEFAULT":
                j = k + 1
                if _u(part[j]) == "ON" and _u(part[j + 1]) == "NULL":
                    j += 2
                start = j
                while j < len(part):
                    if part[j].is_sym("("):
                        j = match_paren(part, j) + 1
                        continue
                    if part[j].type == WORD and _u(part[j]) in COL_STOP - {"ON"} and j > start:
                        break
                    j += 1
                col.default = self._txt(part[start:j])
                k = j
                continue
            if u == "PRIMARY" and nxt == "KEY":
                col.primary_key, col.pk_name = True, pending
                col.nullable = False if col.nullable is None else col.nullable
                k += 2
                pending = None
                continue
            if u == "UNIQUE":
                col.unique, col.unique_name = True, pending
                k += 1
                pending = None
                continue
            if u == "REFERENCES":
                s, n, j, _ = read_qualified(part, k + 1)
                cols = []
                if j < len(part) and part[j].is_sym("("):
                    e = match_paren(part, j)
                    cols = self._col_names(part[j + 1:e])
                    j = e + 1
                ref = {"name": pending, "schema": s, "table": n, "columns": cols}
                if j + 2 < len(part) and _u(part[j]) == "ON" and _u(part[j + 1]) == "DELETE":
                    ref["on_delete"] = " ".join(_u(x) for x in part[j + 2:j + 4]
                                                if _u(x) in ("CASCADE", "SET", "NULL", "RESTRICT", "NO", "ACTION", "DEFAULT"))
                col.references = ref
                k = j
                pending = None
                continue
            if u == "CHECK" and nxt == "(":
                e = match_paren(part, k + 1)
                col.check, col.check_name = self._txt(part[k + 2:e]), pending
                k = e + 1
                pending = None
                continue
            if u in ("AUTO_INCREMENT", "IDENTITY") or (u == "GENERATED" and "IDENTITY" in [
                    _u(x) for x in part[k:k + 6]]):
                col.auto_increment = True
            if u == "COMMENT" and k + 1 < len(part) and part[k + 1].type == STRING:
                col.remarks = _unquote(part[k + 1].value)
                k += 2
                continue
            k += 1

    def _table_constraint(self, part: List[Token]):
        name, k = None, 0
        if _u(part[0]) == "CONSTRAINT":
            name, k = part[1].value, 2
        u = _u(part[k])
        if u == "PRIMARY":
            p = self._next_paren(part, k)
            e = match_paren(part, p)
            return M.Constraint(name, "PRIMARY KEY", self._col_names(part[p + 1:e]), raw=self._txt(part))
        if u == "UNIQUE":
            p = self._next_paren(part, k)
            if name is None and p > k + 1 and part[p - 1].type in (WORD, QIDENT) and not part[p - 1].is_word("KEY", "INDEX"):
                name = part[p - 1].value
            e = match_paren(part, p)
            return M.Constraint(name, "UNIQUE", self._col_names(part[p + 1:e]), raw=self._txt(part))
        if u == "FOREIGN":
            p = self._next_paren(part, k)
            e = match_paren(part, p)
            cols = self._col_names(part[p + 1:e])
            j = e + 1
            while j < len(part) and not part[j].is_word("REFERENCES"):
                j += 1
            s, n, j, _ = read_qualified(part, j + 1)
            rcols = []
            if j < len(part) and part[j].is_sym("("):
                e2 = match_paren(part, j)
                rcols = self._col_names(part[j + 1:e2])
                j = e2 + 1
            ondel = None
            ws = [_u(x) for x in part[j:]]
            if "DELETE" in ws:
                di = ws.index("DELETE")
                ondel = " ".join(w for w in ws[di + 1:di + 3] if w in ("CASCADE", "SET", "NULL", "RESTRICT", "NO", "ACTION", "DEFAULT"))
            return M.Constraint(name, "FOREIGN KEY", cols, s, n, rcols, ondel, raw=self._txt(part))
        if u == "CHECK":
            p = self._next_paren(part, k)
            e = match_paren(part, p)
            return M.Constraint(name, "CHECK", [], check_expr=self._txt(part[p + 1:e]), raw=self._txt(part))
        if u in ("KEY", "INDEX", "FULLTEXT", "SPATIAL"):
            p = self._next_paren(part, k)
            iname = part[p - 1].value if p - 1 > k and part[p - 1].type in (WORD, QIDENT) else None
            e = match_paren(part, p)
            return {"name": iname, "columns": self._col_names(part[p + 1:e])}
        return None

    @staticmethod
    def _next_paren(part, k):
        for j in range(k, len(part)):
            if part[j].is_sym("("):
                return j
        return len(part) - 1

    # ---------------------------------------------------------------- index
    def _create_index(self, i: int, flags) -> List[M.Operation]:
        toks = self.toks
        details = {"unique": "UNIQUE" in flags, "bitmap": "BITMAP" in flags,
                   "clustered": "CLUSTERED" in flags, "concurrently": False}
        while _u(toks[i]) in ("CONCURRENTLY", "IF", "NOT", "EXISTS", "ONLINE"):
            if _u(toks[i]) == "CONCURRENTLY":
                details["concurrently"] = True
            i += 1
        s, n, i, _ = read_qualified(toks, i)
        while i < len(toks) and not toks[i].is_word("ON"):
            i += 1
        ts, tn, i, _ = read_qualified(toks, i + 1)
        if i < len(toks) and toks[i].is_word("USING"):
            details["method"] = toks[i + 1].value
            i += 2
        cols, exprs = [], []
        if i < len(toks) and toks[i].is_sym("("):
            e = match_paren(toks, i)
            for part in split_top(toks[i + 1:e]):
                desc = any(t.is_word("DESC") for t in part)
                core = [t for t in part if not t.is_word("ASC", "DESC")]
                if len(core) == 1 and core[0].type in (WORD, QIDENT):
                    cols.append({"name": core[0].value, "descending": desc})
                else:
                    exprs.append(self._txt(core))
                    cols.append({"name": self._txt(core), "descending": desc, "expression": True})
            i = e + 1
        rest = toks[i:]
        for k, t in enumerate(rest):
            if t.is_word("TABLESPACE") and k + 1 < len(rest):
                details["tablespace"] = rest[k + 1].value
            if t.is_word("ONLINE"):
                details["online"] = True
            if t.is_word("LOCAL"):
                details["local"] = True
            if t.is_word("WHERE"):
                details["where"] = self._txt(rest[k + 1:])
            if t.is_word("INCLUDE"):
                details["include"] = True
        if any(_u(t) == "ONLINE" and k < 4 for k, t in enumerate(toks)):
            details["online"] = True
        if re.search(r"ONLINE\s*=\s*ON", self.sql, re.I) or re.search(r"LOCK\s*=\s*NONE", self.sql, re.I):
            details["online"] = True
        details["columns"] = cols
        details["functional"] = bool(exprs)
        details["table_schema"] = ts
        return [self._op(M.CREATE_INDEX, s or ts, n, self.stmt, table=tn, object_type="INDEX",
                         details=details)]

    # ---------------------------------------------------------------- sequence
    def _create_sequence(self, i: int) -> List[M.Operation]:
        toks = self.toks
        if _u(toks[i]) == "IF":
            i += 3
        s, n, i, _ = read_qualified(toks, i)
        ws = [_u(t) for t in toks[i:]]
        d = {}

        def num_after(*keys):
            for idx, w in enumerate(ws):
                if w in keys:
                    for nx in range(idx + 1, min(idx + 4, len(ws))):
                        if re.fullmatch(r"-?\d+", ws[nx]) or (ws[nx] == "-" and nx + 1 < len(ws)):
                            if ws[nx] == "-":
                                return "-" + ws[nx + 1]
                            return ws[nx]
            return None
        d["start"] = num_after("START")
        d["increment"] = num_after("INCREMENT")
        d["minvalue"] = num_after("MINVALUE")
        d["maxvalue"] = num_after("MAXVALUE")
        d["cache"] = "0" if "NOCACHE" in ws else num_after("CACHE")
        d["cycle"] = "CYCLE" in ws and "NOCYCLE" not in ws
        d["order"] = "ORDER" in ws and "NOORDER" not in ws
        if "AS" in ws:
            d["data_type"] = ws[ws.index("AS") + 1]
        return [self._op(M.CREATE_SEQUENCE, s, n, self.stmt, object_type="SEQUENCE", details=d)]

    # ---------------------------------------------------------------- view
    def _create_view(self, i: int, flags, obj) -> List[M.Operation]:
        toks = self.toks
        if _u(toks[i]) == "IF":
            i += 3
        s, n, i, _ = read_qualified(toks, i)
        cols = []
        if i < len(toks) and toks[i].is_sym("("):
            e = match_paren(toks, i)
            cols = self._col_names(toks[i + 1:e])
            i = e + 1
        while i < len(toks) and not toks[i].is_word("AS"):
            i += 1
        select = self._txt(toks[i + 1:])
        # keep comments inside the select from the original text
        orig_select = self.stmt.sql[toks[i + 1].start:].strip().rstrip(";").rstrip() if i + 1 < len(toks) else select
        d = {"columns": cols, "select": orig_select, "force": "FORCE" in flags,
             "editionable": "EDITIONABLE" in flags, "materialized": obj == "MATERIALIZED VIEW",
             "references": referenced_objects(select),
             "check_option": bool(re.search(r"WITH\s+(CASCADED\s+|LOCAL\s+)?CHECK\s+OPTION", select, re.I)),
             "read_only": bool(re.search(r"WITH\s+READ\s+ONLY", select, re.I))}
        return [self._op(M.CREATE_VIEW, s, n, self.stmt, object_type="MATERIALIZED VIEW" if d["materialized"] else "VIEW",
                         or_replace=bool(flags & {"REPLACE", "ALTER"}), details=d)]

    # ---------------------------------------------------------------- trigger
    def _create_trigger(self, i: int, or_replace: bool) -> List[M.Operation]:
        toks = self.toks
        if _u(toks[i]) == "IF":
            i += 3
        s, n, i, _ = read_qualified(toks, i)
        ws = [_u(t) for t in toks[i:i + 40]]
        timing = next((w for w in ("BEFORE", "AFTER", "INSTEAD", "FOR") if w in ws), "")
        if timing == "INSTEAD":
            timing = "INSTEAD OF"
        events = []
        if timing:
            ti = ws.index(timing.split()[0])
            for w in ws[ti + (2 if timing == "INSTEAD OF" else 1):]:
                if w in ("ON", "AS", "BEGIN", "FOR", "REFERENCING", "WHEN", "DECLARE", "EXECUTE", "NOT", "WITH"):
                    break
                if w in ("INSERT", "UPDATE", "DELETE", "TRUNCATE") and w not in events:
                    events.append(w)
        tschema, tname = None, None
        for k in range(i, min(i + 60, len(toks))):
            if toks[k].is_word("ON"):
                tschema, tname, _, _ = read_qualified(toks, k + 1)
                if tname and tname.upper() not in ("DATABASE", "SCHEMA"):
                    break
        row_level = bool(re.search(r"FOR\s+EACH\s+ROW", self.sql, re.I))
        body = self.stmt.sql
        d = {"timing": timing, "events": events, "row_level": row_level,
             "table_schema": tschema, "references": referenced_objects(body),
             "compound": bool(re.search(r"\bCOMPOUND\s+TRIGGER\b", self.sql, re.I)),
             "columns_used": sorted(set(c.upper() for c in re.findall(r"[:]?(?:NEW|OLD)\.\"?(\w+)", body, re.I)))}
        return [self._op(M.CREATE_TRIGGER, s or tschema, n, self.stmt, table=tname, object_type="TRIGGER",
                         or_replace=or_replace, details=d)]

    # ================================================================ ALTER TABLE
    ACTIONS = {"ADD", "DROP", "MODIFY", "ALTER", "RENAME", "CHANGE", "SET", "ENABLE", "DISABLE", "MOVE",
               "SHRINK", "TRUNCATE", "SPLIT", "MERGE", "EXCHANGE", "OWNER", "ATTACH", "DETACH", "VALIDATE",
               "NOCHECK", "WITH", "ENGINE", "AUTO_INCREMENT", "CONVERT", "CHARACTER", "DEFAULT"}

    def _alter_table(self) -> List[M.Operation]:
        toks = self.toks
        i = 2
        while _u(toks[i]) in ("IF", "EXISTS", "ONLY", "ONLINE", "IGNORE"):
            i += 1
        schema, table, i, _ = read_qualified(toks, i)
        head_txt = self.sql[toks[0].start:toks[i - 1].end].strip()
        # Oracle: ADD(..) MODIFY(..) DROP(..) are single actions. Others: split on top-level commas.
        segments = []
        for seg in split_top(toks[i:]):
            if not seg:
                continue
            if segments and _u(seg[0]) not in self.ACTIONS:
                segments.append(("INHERIT", seg))
            else:
                segments.append(("ACTION", seg))
        actions = []
        for tag, seg in segments:
            if tag == "INHERIT":
                if actions and actions[-1]["kind"] == M.ADD_COLUMN:
                    actions[-1]["columns"].append(self._column(seg))
                    actions[-1]["text_parts"].append(self._txt(seg))
                elif actions:
                    actions[-1]["text_parts"].append(self._txt(seg))
                continue
            actions.append(self._alter_action(seg))
        # merge consecutive identical-kind actions into one logical op
        ops: List[M.Operation] = []
        merged: List[dict] = []
        for a in actions:
            if merged and merged[-1]["kind"] == a["kind"] and a["kind"] in (M.ADD_COLUMN, M.DROP_COLUMN):
                merged[-1]["columns"] += a.get("columns", [])
                merged[-1]["text_parts"] += a["text_parts"]
                merged[-1]["cascade"] = merged[-1].get("cascade") or a.get("cascade")
            else:
                merged.append(a)
        multi = len(merged) > 1
        for a in merged:
            text = ", ".join(a["text_parts"]) if self.d != "oracle" else " ".join(a["text_parts"])
            sql = f"{head_txt}\n{text}" if multi else self.stmt.sql.strip().rstrip(";")
            kind = a.pop("kind")
            name = a.get("constraint_name") or table
            ops.append(self._op(kind, schema, name if kind in (M.ADD_CONSTRAINT, M.DROP_CONSTRAINT) else table,
                                self.stmt, sql=sql, table=table, object_type="TABLE", details=a))
        return ops

    def _alter_action(self, seg: List[Token]) -> dict:
        txt = self._txt(seg)
        u0 = _u(seg[0]) if seg else ""
        u1 = _u(seg[1]) if len(seg) > 1 else ""
        base = {"text_parts": [txt], "action_text": txt}
        if u0 == "ADD":
            k = 1
            if u1 == "COLUMN":
                k = 2
            if _u(seg[k]) == "IF":
                k += 3
            if _u(seg[k]) in ("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK"):
                c = self._table_constraint(seg[k:])
                return {**base, "kind": M.ADD_CONSTRAINT, "constraint": c,
                        "constraint_name": c.name if isinstance(c, M.Constraint) else None,
                        "validate": not bool(re.search(r"\bNOVALIDATE\b|\bNOT\s+VALID\b|WITH\s+NOCHECK", txt, re.I))}
            if _u(seg[k]) in ("INDEX", "KEY", "FULLTEXT", "SPATIAL"):
                c = self._table_constraint(seg[k:])
                return {**base, "kind": M.ALTER_TABLE_RAW, "action": "ADD INDEX", "index": c}
            if seg[k].is_sym("("):
                e = match_paren(seg, k)
                inner = split_top(seg[k + 1:e])
                if inner and _u(inner[0][0]) in ("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK"):
                    c = self._table_constraint(inner[0])
                    return {**base, "kind": M.ADD_CONSTRAINT, "constraint": c,
                            "constraint_name": c.name if isinstance(c, M.Constraint) else None, "validate": True}
                return {**base, "kind": M.ADD_COLUMN, "columns": [self._column(p) for p in inner if p]}
            return {**base, "kind": M.ADD_COLUMN, "columns": [self._column(seg[k:])]}
        if u0 == "DROP":
            cascade = bool(re.search(r"\bCASCADE\b", txt, re.I))
            if u1 in ("COLUMN",):
                k = 2
                if _u(seg[k]) == "IF":
                    k += 2
                return {**base, "kind": M.DROP_COLUMN, "columns": [seg[k].value], "cascade": cascade}
            if seg[1].is_sym("("):
                e = match_paren(seg, 1)
                return {**base, "kind": M.DROP_COLUMN, "columns": self._col_names(seg[2:e]), "cascade": cascade}
            if u1 == "CONSTRAINT":
                k = 2
                if _u(seg[k]) == "IF":
                    k += 2
                return {**base, "kind": M.DROP_CONSTRAINT, "constraint_name": seg[k].value, "cascade": cascade,
                        "keep_index": "KEEP" in txt.upper()}
            if u1 == "PRIMARY":
                return {**base, "kind": M.DROP_CONSTRAINT, "constraint_name": None, "ctype": "PRIMARY KEY",
                        "cascade": cascade}
            if u1 == "FOREIGN" and len(seg) > 3:
                return {**base, "kind": M.DROP_CONSTRAINT, "constraint_name": seg[3].value, "ctype": "FOREIGN KEY"}
            if u1 in ("INDEX", "KEY"):
                return {**base, "kind": M.ALTER_TABLE_RAW, "action": "DROP INDEX", "index_name": seg[2].value}
            if u1 == "UNUSED":
                return {**base, "kind": M.ALTER_TABLE_RAW, "action": "DROP UNUSED COLUMNS"}
            if u1 == "DEFAULT":
                return {**base, "kind": M.MODIFY_COLUMN, "column": None, "drop_default": True}
            # MySQL / SQL Server: DROP col
            return {**base, "kind": M.DROP_COLUMN, "columns": [seg[1].value], "cascade": cascade}
        if u0 == "MODIFY" or u0 == "CHANGE":
            k = 1
            if u1 == "COLUMN":
                k = 2
            if u0 == "MODIFY" and u1 == "CONSTRAINT":
                return {**base, "kind": M.ALTER_TABLE_RAW, "action": "MODIFY CONSTRAINT"}
            if u0 == "CHANGE":
                old = seg[k].value
                col = self._column(seg[k + 1:])
                return {**base, "kind": M.MODIFY_COLUMN, "column": col.name, "old_name": old,
                        "columns": [col], "rename": old.upper() != col.name.upper()}
            if seg[k].is_sym("("):
                e = match_paren(seg, k)
                cols = [self._column(p) for p in split_top(seg[k + 1:e]) if p]
                return {**base, "kind": M.MODIFY_COLUMN, "column": cols[0].name if cols else None, "columns": cols}
            col = self._column(seg[k:])
            return {**base, "kind": M.MODIFY_COLUMN, "column": col.name, "columns": [col]}
        if u0 == "ALTER":
            k = 2 if u1 == "COLUMN" else 1
            cname = seg[k].value
            rest = [_u(t) for t in seg[k + 1:]]
            col = M.Column(name=cname)
            info = {**base, "kind": M.MODIFY_COLUMN, "column": cname, "columns": [col]}
            if rest[:2] == ["SET", "NOT"]:
                col.nullable = False
            elif rest[:2] == ["DROP", "NOT"]:
                col.nullable = True
            elif rest[:2] == ["SET", "DEFAULT"]:
                col.default = self._txt(seg[k + 3:])
            elif rest[:2] == ["DROP", "DEFAULT"]:
                info["drop_default"] = True
            elif rest[:1] == ["TYPE"] or rest[:3] == ["SET", "DATA", "TYPE"]:
                j = k + 2 if rest[:1] == ["TYPE"] else k + 4
                end = next((x for x in range(j, len(seg)) if seg[x].is_word("USING", "COLLATE")), len(seg))
                col.data_type = self._txt(seg[j:end])
                if end < len(seg) and seg[end].is_word("USING"):
                    info["using"] = self._txt(seg[end + 1:])
            else:  # SQL Server: ALTER COLUMN c type [NULL|NOT NULL]
                full = self._column(seg[k:])
                info["columns"] = [full]
            return info
        if u0 == "RENAME":
            if u1 == "COLUMN" or (len(seg) > 3 and _u(seg[2]) == "TO" and u1 not in ("TO", "AS", "CONSTRAINT", "INDEX")):
                k = 2 if u1 == "COLUMN" else 1
                return {**base, "kind": M.RENAME_COLUMN, "column": seg[k].value, "new_name": seg[k + 2].value}
            if u1 in ("TO", "AS"):
                return {**base, "kind": M.RENAME_TABLE, "new_name": seg[2].value}
            if u1 == "CONSTRAINT":
                return {**base, "kind": M.ALTER_TABLE_RAW, "action": "RENAME CONSTRAINT",
                        "old": seg[2].value, "new_name": seg[4].value if len(seg) > 4 else None}
        if u0 == "SET" and u1 == "UNUSED":
            if len(seg) > 2 and seg[2].is_sym("("):
                e = match_paren(seg, 2)
                cols = self._col_names(seg[3:e])
            else:
                cols = [seg[3].value] if len(seg) > 3 else []
            return {**base, "kind": M.DROP_COLUMN, "columns": cols, "set_unused": True,
                    "cascade": "CASCADE" in txt.upper()}
        return {**base, "kind": M.ALTER_TABLE_RAW, "action": " ".join(_u(t) for t in seg[:2])}

    # ================================================================ DROP
    def _drop(self) -> List[M.Operation]:
        toks = self.toks
        obj = _u(toks[1])
        i = 2
        if obj in ("PACKAGE", "TYPE") and _u(toks[2]) == "BODY":
            obj += " BODY"
            i = 3
        if obj == "MATERIALIZED":
            obj, i = "MATERIALIZED VIEW", 3
        if obj == "PUBLIC":
            obj, i = "PUBLIC SYNONYM", 3
        if _u(toks[i]) == "IF":
            i += 2
        s, n, j, _ = read_qualified(toks, i)
        ws = [_u(t) for t in toks[j:]]
        details = {"cascade": "CASCADE" in ws, "purge": "PURGE" in ws, "if_exists": "IF" in [_u(t) for t in toks[:4]]}
        table = None
        if "ON" in ws:
            k = j + ws.index("ON")
            _, table, _, _ = read_qualified(toks, k + 1)
        kind = {"TABLE": M.DROP_TABLE, "INDEX": M.DROP_INDEX, "VIEW": M.DROP_VIEW, "MATERIALIZED VIEW": M.DROP_VIEW,
                "SEQUENCE": M.DROP_SEQUENCE, "TRIGGER": M.DROP_TRIGGER}.get(obj)
        if obj in ("PROCEDURE", "PROC", "FUNCTION", "PACKAGE", "PACKAGE BODY", "TYPE", "TYPE BODY"):
            kind = M.DROP_ROUTINE
        if not kind:
            return [self._op(M.OTHER, s, n, self.stmt, object_type=obj)]
        return [self._op(kind, s, n, self.stmt, table=table if kind in (M.DROP_INDEX, M.DROP_TRIGGER) else
                         (n if kind == M.DROP_TABLE else None),
                         object_type={"PROC": "PROCEDURE"}.get(obj, obj), details=details)]

    # ================================================================ COMMENT / GRANT
    def _comment(self) -> List[M.Operation]:
        toks = self.toks
        target = _u(toks[2])
        parts, i = [], 3
        while i < len(toks) and toks[i].type in (WORD, QIDENT):
            parts.append(toks[i].value)
            if i + 1 < len(toks) and toks[i + 1].is_sym("."):
                i += 2
                continue
            i += 1
            break
        text = ""
        for t in toks[i:]:
            if t.type == STRING:
                text = _unquote(t.value)
        if target == "COLUMN":
            col = parts[-1]
            table = parts[-2] if len(parts) >= 2 else None
            schema = parts[-3] if len(parts) >= 3 else None
            return [self._op(M.COMMENT, schema, table, self.stmt, table=table, object_type="COLUMN",
                             details={"target": "COLUMN", "column": col, "text": text})]
        schema = parts[-2] if len(parts) >= 2 else None
        return [self._op(M.COMMENT, schema, parts[-1] if parts else "?", self.stmt, table=parts[-1] if parts else None,
                         object_type=target, details={"target": target, "text": text})]

    def _grant(self, w0) -> List[M.Operation]:
        toks = self.toks
        ws = [_u(t) for t in toks]
        on = ws.index("ON") if "ON" in ws else -1
        privs = self._txt(toks[1:on]) if on > 0 else self._txt(toks[1:])
        s = n = None
        grantees = []
        if on > 0:
            k = on + 1
            if _u(toks[k]) in ("TABLE", "SEQUENCE", "FUNCTION", "PROCEDURE", "SCHEMA", "OBJECT") and toks[k + 1].type in (WORD, QIDENT):
                if not toks[k + 1].is_word("TO", "FROM"):
                    k += 1
            s, n, k, _ = read_qualified(toks, k)
            if k < len(toks) and toks[k].is_sym(":"):
                k += 2  # mssql OBJECT::name
            kw = "TO" if w0 == "GRANT" else "FROM"
            if kw in ws[k:]:
                g = k + ws[k:].index(kw)
                grantees = [p[0].value for p in split_top(toks[g + 1:]) if p and not p[0].is_word("WITH")]
        return [self._op(M.GRANT if w0 == "GRANT" else M.REVOKE, s, n or "SYSTEM", self.stmt,
                         object_type="GRANT", table=n,
                         details={"privileges": privs, "grantees": grantees,
                                  "with_grant_option": "GRANT OPTION" in " ".join(ws) and w0 == "GRANT"})]

    # ================================================================ DML
    def _dml(self, w0) -> List[M.Operation]:
        toks = self.toks
        ws = [_u(t) for t in toks]
        kind = {"INSERT": M.INSERT, "UPDATE": M.UPDATE, "DELETE": M.DELETE, "MERGE": M.MERGE,
                "UPSERT": M.INSERT, "REPLACE": M.INSERT}[w0]
        i = 1
        if w0 in ("INSERT", "REPLACE", "UPSERT") and "INTO" in ws[:4]:
            i = ws.index("INTO") + 1
        elif w0 == "DELETE" and len(ws) > 1 and ws[1] == "FROM":
            i = 2
        elif w0 == "MERGE":
            i = ws.index("INTO") + 1 if "INTO" in ws else 1
        if w0 == "UPDATE" and ws[i] in ("TOP",):
            i += 4
        s, n, j, _ = read_qualified(toks, i)
        details = {"has_where": "WHERE" in ws, "references": referenced_objects(self.stmt.sql)}
        if kind == M.INSERT:
            cols, vals = [], []
            if j < len(toks) and toks[j].is_sym("("):
                e = match_paren(toks, j)
                cols = self._col_names(toks[j + 1:e])
                j = e + 1
            if j < len(toks) and toks[j].is_word("VALUES") and j + 1 < len(toks) and toks[j + 1].is_sym("("):
                e = match_paren(toks, j + 1)
                vals = [self._txt(p) for p in split_top(toks[j + 2:e])]
                details["multi_row"] = e + 1 < len(toks) and toks[e + 1].is_sym(",")
            details.update({"columns": cols, "values": vals, "from_select": "SELECT" in ws})
        if kind in (M.UPDATE, M.DELETE) and "WHERE" in ws:
            details["where"] = self._txt(toks[ws.index("WHERE") + 1:])
        if kind == M.UPDATE and "SET" in ws:
            si = ws.index("SET")
            wi = ws.index("WHERE") if "WHERE" in ws else len(ws)
            details["set"] = self._txt(toks[si + 1:wi])
            details["set_columns"] = [p[0].value for p in split_top(toks[si + 1:wi]) if p]
        return [self._op(kind, s, n, self.stmt, table=n, object_type="DATA", details=details)]


def _unquote(s: str) -> str:
    if len(s) >= 2 and s[0] in "nNeE" and s[1] == "'":
        s = s[1:]
    if len(s) >= 2 and s[0] == "'" and s[-1] == "'":
        return s[1:-1].replace("''", "'")
    return s
