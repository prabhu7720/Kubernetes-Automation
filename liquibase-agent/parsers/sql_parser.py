"""Script-level SQL parsing: dialect detection and statement splitting.

Handles, without any third-party dependency:
  * Oracle  : PL/SQL blocks (BEGIN/END depth tracking), '/' terminators, q'' quotes,
              SQL*Plus directives (SET, PROMPT, SPOOL, WHENEVER, EXIT, @file)
  * Postgres: $$ / $tag$ dollar quoting, psql backslash commands
  * MySQL / MariaDB: DELIMITER directive, backtick identifiers, # comments
  * SQL Server: GO batch separator, [bracket] identifiers, CREATE PROC/TRIGGER batches
  * Liquibase formatted SQL: --changeset / --rollback / --comment lines are treated as
    statement boundaries so existing changelog files can be re-analysed.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from core.models import Statement

DIALECTS = ("oracle", "postgresql", "mysql", "mariadb", "mssql")
DIALECT_ALIASES = {
    "oracle": "oracle", "ora": "oracle",
    "postgres": "postgresql", "postgresql": "postgresql", "pg": "postgresql",
    "mysql": "mysql", "mariadb": "mariadb", "maria": "mariadb",
    "mssql": "mssql", "sqlserver": "mssql", "sql_server": "mssql", "tsql": "mssql",
}

_SIGNALS: Dict[str, List[Tuple[str, int]]] = {
    "oracle": [(r"\bVARCHAR2\b", 3), (r"\bNUMBER\s*(\(|\b)", 2), (r"\bSYSTIMESTAMP\b|\bSYSDATE\b", 2),
               (r"\bTABLESPACE\b", 1), (r"\bNOLOGGING\b|\bNOCACHE\b|\bNOCYCLE\b", 2),
               (r":NEW\.|:OLD\.", 3), (r"^\s*/\s*$", 2), (r"\bNVL\s*\(", 2), (r"\bDUAL\b", 2),
               (r"\bCLOB\b|\bNCLOB\b|\bRAW\s*\(", 2), (r"\bCASCADE\s+CONSTRAINTS\b", 2),
               (r"\bDBA_|\bALL_TAB|\bUSER_TAB", 2), (r"\bEDITIONABLE\b", 3), (r"\bSYS_GUID\b", 3),
               (r"\bPLS_INTEGER\b|\bVARCHAR2\b", 2)],
    "postgresql": [(r"\bSERIAL\b|\bBIGSERIAL\b", 3), (r"\$\$|\$[A-Za-z_]+\$", 3),
                   (r"\bLANGUAGE\s+plpgsql\b", 4), (r"::\s*[A-Za-z]", 2), (r"\bTIMESTAMPTZ\b|\bJSONB\b", 3),
                   (r"\bILIKE\b", 2), (r"\bCONCURRENTLY\b", 3), (r"\bEXECUTE\s+(FUNCTION|PROCEDURE)\b", 3),
                   (r"\bBYTEA\b|\bUUID\b|\bTEXT\[\]", 2), (r"\bRETURNS\s+TRIGGER\b", 4)],
    "mysql": [(r"\bAUTO_INCREMENT\b", 4), (r"\bENGINE\s*=", 4), (r"`", 2), (r"^\s*DELIMITER\b", 4),
              (r"\bUNSIGNED\b", 3), (r"\bTINYINT\b|\bMEDIUMTEXT\b|\bLONGTEXT\b", 2),
              (r"\bCHARSET\b|\bCOLLATE\s*=", 2), (r"\bIFNULL\s*\(", 2)],
    "mssql": [(r"\bNVARCHAR\s*\(\s*MAX\s*\)", 4), (r"\bIDENTITY\s*\(", 3), (r"^\s*GO\s*$", 4),
              (r"\[[A-Za-z_][A-Za-z0-9_ ]*\]", 2), (r"\bdbo\.", 3), (r"\bGETDATE\s*\(", 3),
              (r"\bDATETIME2\b|\bUNIQUEIDENTIFIER\b", 3), (r"\bNONCLUSTERED\b|\bCLUSTERED\b", 3),
              (r"\bsp_rename\b|\bEXEC\b", 2), (r"\bCREATE\s+OR\s+ALTER\b", 3), (r"\bTOP\s*\(", 2)],
}


def normalize_dialect(d: str) -> str:
    if not d:
        return ""
    key = d.strip().lower()
    if key not in DIALECT_ALIASES:
        raise ValueError(f"Unsupported dialect '{d}'. Use one of: {', '.join(DIALECTS)}")
    return DIALECT_ALIASES[key]


def detect_dialect(text: str, default: str = "oracle") -> Tuple[str, Dict[str, int]]:
    scores = {}
    for d, sigs in _SIGNALS.items():
        s = 0
        for pat, w in sigs:
            s += w * min(len(re.findall(pat, text, re.IGNORECASE | re.MULTILINE)), 5)
        scores[d] = s
    if re.search(r"mariadb", text, re.IGNORECASE):
        scores["mariadb"] = scores["mysql"] + 1
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return default, scores
    return best, scores


_LB_META = re.compile(r"^\s*--\s*(liquibase\s+formatted|changeset\b|rollback\b|comment\s*:|"
                      r"preconditions?\b|precondition-|validCheckSum\b|ignoreLines\b|property\b)",
                      re.IGNORECASE)
_SQLPLUS = re.compile(r"^\s*(SET\s+(DEFINE|ECHO|SERVEROUTPUT|FEEDBACK|TIMING|LINESIZE|PAGESIZE|VERIFY|"
                      r"HEADING|TERMOUT|SQLBLANKLINES|TRIMSPOOL|SCAN|LONG|TAB|AUTOCOMMIT)\b|PROMPT\b|"
                      r"SPOOL\b|WHENEVER\b|EXIT\b|QUIT\b|CONNECT\b|CONN\b|@@?|SHOW\s+ERR|DEFINE\b|"
                      r"UNDEFINE\b|ALTER\s+SESSION\s+SET\s+CURRENT_SCHEMA)", re.IGNORECASE)
_PLSQL_HEAD_ORA = re.compile(
    r"^\s*(CREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?(TRIGGER|PROCEDURE|FUNCTION|PACKAGE|TYPE\s+BODY|"
    r"LIBRARY)\b|DECLARE\b|BEGIN\b)", re.IGNORECASE)
_PLSQL_HEAD_MYSQL = re.compile(
    r"^\s*CREATE\s+(OR\s+REPLACE\s+)?(DEFINER\s*=\s*\S+\s+)?(TRIGGER|PROCEDURE|FUNCTION|EVENT)\b", re.IGNORECASE)
_PLSQL_HEAD_MSSQL = re.compile(
    r"^\s*(CREATE|ALTER|CREATE\s+OR\s+ALTER)\s+(PROC|PROCEDURE|TRIGGER|FUNCTION|VIEW)\b", re.IGNORECASE)
_PKG_HEAD = re.compile(r"^\s*CREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?(PACKAGE|TYPE\s+BODY)\b", re.IGNORECASE)


class _Splitter:
    def __init__(self, text: str, dialect: str, source: str):
        self.t = text.replace("\r\n", "\n").replace("\r", "\n")
        self.d = dialect
        self.source = source
        self.out: List[Statement] = []
        self.delim = ";"

    # ----------------------------------------------------------------- helpers
    def _line_no(self, pos: int) -> int:
        return self.t.count("\n", 0, pos) + 1

    def _emit(self, start: int, end: int, delimiter: str = ";", plsql: bool = False):
        chunk = self.t[start:end]
        lead, body_off = _split_leading_comment(chunk)
        sql = chunk[body_off:].rstrip()
        if not sql.strip():
            return
        s = start + body_off
        self.out.append(Statement(sql=sql.strip(), line_start=self._line_no(s),
                                  line_end=self._line_no(start + len(chunk.rstrip())),
                                  source=self.source, leading_comment=lead.strip(),
                                  delimiter=delimiter, is_plsql=plsql))

    def _head(self, start: int, i: int) -> str:
        return _strip_leading_comments(self.t[start:i + 200])

    # ----------------------------------------------------------------- main
    def run(self) -> List[Statement]:
        t, n = self.t, len(self.t)
        i = 0
        start = 0
        plsql = None      # None=unknown, False=plain, True=block
        pkg = False
        depth = 0
        seen_block = False
        at_line_start = True

        def reset(pos):
            nonlocal start, plsql, depth, seen_block, pkg
            start, plsql, depth, seen_block, pkg = pos, None, 0, False, False

        while i < n:
            c = t[i]
            if at_line_start:
                eol = t.find("\n", i)
                eol = n if eol < 0 else eol
                line = t[i:eol]
                stripped = line.strip()
                buf_empty = not _strip_leading_comments(t[start:i]).strip()
                if _LB_META.match(line):
                    self._emit(start, i, plsql=bool(plsql))
                    reset(eol + 1)
                    i = eol + 1
                    continue
                if self.d == "oracle" and stripped == "/":
                    self._emit(start, i, "/", plsql=bool(plsql))
                    reset(eol + 1)
                    i = eol + 1
                    continue
                if self.d == "mssql" and re.fullmatch(r"GO(\s+\d+)?", stripped, re.IGNORECASE):
                    self._emit(start, i, "GO", plsql=bool(plsql))
                    reset(eol + 1)
                    i = eol + 1
                    continue
                if self.d in ("mysql", "mariadb") and re.match(r"DELIMITER\s+\S+", stripped, re.IGNORECASE):
                    self._emit(start, i, self.delim, plsql=bool(plsql))
                    self.delim = stripped.split()[1]
                    reset(eol + 1)
                    i = eol + 1
                    continue
                if buf_empty and ((self.d == "oracle" and _SQLPLUS.match(line)) or
                                  (self.d == "postgresql" and stripped.startswith("\\"))):
                    self._emit(i, eol, "EOL")
                    reset(eol + 1)
                    i = eol + 1
                    continue
                at_line_start = False

            if c == "\n":
                at_line_start = True
                i += 1
                continue
            # comments
            if t.startswith("--", i) or (c == "#" and self.d in ("mysql", "mariadb")):
                j = t.find("\n", i)
                i = n if j < 0 else j
                continue
            if t.startswith("/*", i):
                j = t.find("*/", i + 2)
                i = n if j < 0 else j + 2
                continue
            # strings / quoted identifiers
            if c in "qQ" and t[i + 1:i + 2] == "'" and self.d == "oracle":
                op = t[i + 2:i + 3]
                cl = {"[": "]", "(": ")", "{": "}", "<": ">"}.get(op, op)
                j = t.find(cl + "'", i + 3)
                i = n if j < 0 else j + 2
                continue
            if c == "'":
                j = i + 1
                while j < n:
                    if t[j] == "\\" and self.d in ("mysql", "mariadb"):
                        j += 2
                        continue
                    if t[j] == "'" and t[j + 1:j + 2] == "'":
                        j += 2
                        continue
                    if t[j] == "'":
                        break
                    j += 1
                i = j + 1
                continue
            if c == '"' or (c == "`" and self.d in ("mysql", "mariadb")):
                j = t.find(c, i + 1)
                i = n if j < 0 else j + 1
                continue
            if c == "$" and self.d == "postgresql":
                m = re.match(r"\$([A-Za-z_]*)\$", t[i:])
                if m:
                    tag = m.group(0)
                    j = t.find(tag, i + len(tag))
                    i = n if j < 0 else j + len(tag)
                    continue
            # custom delimiter (MySQL DELIMITER $$) has priority over everything else
            if self.delim != ";" and t.startswith(self.delim, i):
                self._emit(start, i, self.delim, plsql=True)
                reset(i + len(self.delim))
                i += len(self.delim)
                continue
            # classify statement on first significant char
            if plsql is None and not c.isspace():
                head = self._head(start, i)
                if self.d == "oracle":
                    plsql = bool(_PLSQL_HEAD_ORA.match(head))
                    pkg = bool(_PKG_HEAD.match(head)) and not re.match(
                        r"^\s*CREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?TYPE\s+(?!BODY)", head, re.I)
                elif self.d in ("mysql", "mariadb"):
                    plsql = bool(_PLSQL_HEAD_MYSQL.match(head))
                elif self.d == "mssql":
                    plsql = bool(_PLSQL_HEAD_MSSQL.match(head))
                else:
                    plsql = False
            # words (block depth)
            if c.isalpha() or c == "_":
                m = re.match(r"[A-Za-z_][A-Za-z0-9_#]*" if self.d in ("mysql", "mariadb") else r"[A-Za-z_][A-Za-z0-9_$#]*", t[i:])
                w = m.group(0).upper()
                if plsql and self.d in ("oracle", "mysql", "mariadb"):
                    if w in ("BEGIN", "CASE") or (w == "COMPOUND" and self.d == "oracle"):
                        depth += 1
                        seen_block = True
                    elif w in ("AS", "IS") and pkg and depth == 0 and not seen_block:
                        depth += 1
                        seen_block = True
                    elif w == "END":
                        nxt = re.match(r"\s+([A-Za-z_]+)", t[i + 3:])
                        nw = nxt.group(1).upper() if nxt else ""
                        if nw in ("IF", "LOOP", "WHILE", "REPEAT", "FOR"):
                            i += 3 + nxt.end()
                            continue
                        depth = max(0, depth - 1)
                        if nw == "CASE":
                            i += 3 + nxt.end()
                            continue
                i += len(w)
                continue
            # custom delimiter (MySQL DELIMITER $$)
            if self.delim != ";" and t.startswith(self.delim, i):
                self._emit(start, i, self.delim, plsql=True)
                reset(i + len(self.delim))
                i += len(self.delim)
                continue
            if c == ";" and self.delim != ";":
                i += 1
                continue
            if c == ";":
                if plsql:
                    if self.d == "mssql":
                        i += 1
                        continue
                    if self.d == "oracle" and (not seen_block or depth > 0):
                        i += 1
                        continue
                    if self.d in ("mysql", "mariadb") and seen_block and depth > 0:
                        i += 1
                        continue
                    self._emit(start, i + 1, ";", plsql=True)
                else:
                    self._emit(start, i, ";")
                reset(i + 1)
                i += 1
                continue
            i += 1
        self._emit(start, n, "EOF", plsql=bool(plsql))
        return self.out


def _split_leading_comment(chunk: str) -> Tuple[str, int]:
    """Return (leading comment text, offset of first SQL char)."""
    i, n = 0, len(chunk)
    comments = []
    while i < n:
        if chunk[i].isspace():
            i += 1
            continue
        if chunk.startswith("--", i):
            j = chunk.find("\n", i)
            j = n if j < 0 else j
            comments.append(chunk[i + 2:j].strip(" -=*"))
            i = j
            continue
        if chunk.startswith("/*", i):
            j = chunk.find("*/", i + 2)
            j = n if j < 0 else j + 2
            body = chunk[i + 2:j - 2]
            for ln in body.splitlines():
                ln = ln.strip(" */=-")
                if ln:
                    comments.append(ln)
            i = j
            continue
        break
    return "\n".join(c for c in comments if c), i


def _strip_leading_comments(s: str) -> str:
    _, off = _split_leading_comment(s)
    return s[off:]


def split_statements(text: str, dialect: str, source: str = "<input>") -> List[Statement]:
    return _Splitter(text, dialect, source).run()


def is_liquibase_formatted(text: str) -> bool:
    return bool(re.search(r"^\s*--\s*liquibase\s+formatted\s+sql", text, re.IGNORECASE | re.MULTILINE))


def is_liquibase_xml(text: str) -> bool:
    return "<databaseChangeLog" in text[:5000]
