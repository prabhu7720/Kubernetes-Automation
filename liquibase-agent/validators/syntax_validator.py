"""Rule-based SQL syntax validation (offline, no database connection)."""
from __future__ import annotations

import re
from typing import List

from core import models as M
from core.lexer import strip_comments

ORACLE_RESERVED = set("""ACCESS ADD ALL ALTER AND ANY AS ASC AUDIT BETWEEN BY CHAR CHECK CLUSTER COLUMN COMMENT COMPRESS
CONNECT CREATE CURRENT DATE DECIMAL DEFAULT DELETE DESC DISTINCT DROP ELSE EXCLUSIVE EXISTS FILE FLOAT FOR FROM GRANT
GROUP HAVING IDENTIFIED IMMEDIATE IN INCREMENT INDEX INITIAL INSERT INTEGER INTERSECT INTO IS LEVEL LIKE LOCK LONG
MAXEXTENTS MINUS MLSLABEL MODE MODIFY NOAUDIT NOCOMPRESS NOT NOWAIT NULL NUMBER OF OFFLINE ON ONLINE OPTION OR ORDER
PCTFREE PRIOR PUBLIC RAW RENAME RESOURCE REVOKE ROW ROWID ROWNUM ROWS SELECT SESSION SET SHARE SIZE SMALLINT START
SUCCESSFUL SYNONYM SYSDATE TABLE THEN TO TRIGGER UID UNION UNIQUE UPDATE USER VALIDATE VALUES VARCHAR VARCHAR2 VIEW
WHENEVER WHERE WITH""".split())
PG_RESERVED = set("""ALL ANALYSE ANALYZE AND ANY ARRAY AS ASC ASYMMETRIC BOTH CASE CAST CHECK COLLATE COLUMN CONSTRAINT
CREATE CURRENT_CATALOG CURRENT_DATE CURRENT_ROLE CURRENT_TIME CURRENT_TIMESTAMP CURRENT_USER DEFAULT DEFERRABLE DESC
DISTINCT DO ELSE END EXCEPT FALSE FETCH FOR FOREIGN FROM GRANT GROUP HAVING IN INITIALLY INTERSECT INTO LATERAL LEADING
LIMIT LOCALTIME LOCALTIMESTAMP NOT NULL OFFSET ON ONLY OR ORDER PLACING PRIMARY REFERENCES RETURNING SELECT SESSION_USER
SOME SYMMETRIC TABLE THEN TO TRAILING TRUE UNION UNIQUE USER USING VARIADIC WHEN WHERE WINDOW WITH""".split())
MYSQL_RESERVED = set("""ACCESSIBLE ADD ALL ALTER ANALYZE AND AS ASC BEFORE BETWEEN BIGINT BINARY BLOB BOTH BY CALL CASCADE
CASE CHANGE CHAR CHARACTER CHECK COLLATE COLUMN CONDITION CONSTRAINT CONTINUE CONVERT CREATE CROSS CURRENT_DATE
CURRENT_TIME CURRENT_TIMESTAMP CURRENT_USER CURSOR DATABASE DATABASES DEC DECIMAL DECLARE DEFAULT DELAYED DELETE DESC
DESCRIBE DISTINCT DIV DOUBLE DROP DUAL EACH ELSE ELSEIF ENCLOSED ESCAPED EXISTS EXIT EXPLAIN FALSE FETCH FLOAT FOR FORCE
FOREIGN FROM FULLTEXT GENERATED GET GRANT GROUP GROUPS HAVING IF IGNORE IN INDEX INNER INSERT INT INTEGER INTERVAL INTO IS
JOIN KEY KEYS KILL LEADING LEAVE LEFT LIKE LIMIT LINES LOAD LOCK LONG LOOP MATCH MOD MODIFIES NATURAL NOT NULL NUMERIC ON
OPTION OR ORDER OUT OUTER PARTITION PRECISION PRIMARY PROCEDURE PURGE RANGE RANK READ READS REAL REFERENCES REGEXP RELEASE
RENAME REPEAT REPLACE REQUIRE RESTRICT RETURN REVOKE RIGHT RLIKE ROW ROWS SCHEMA SELECT SET SHOW SIGNAL SMALLINT SPATIAL
SQL STARTING TABLE TERMINATED THEN TO TRAILING TRIGGER TRUE UNDO UNION UNIQUE UNLOCK UNSIGNED UPDATE USAGE USE USING VALUES
VARCHAR VARYING WHEN WHERE WHILE WINDOW WITH WRITE XOR ZEROFILL""".split())
MSSQL_RESERVED = set("""ADD ALL ALTER AND ANY AS ASC AUTHORIZATION BACKUP BEGIN BETWEEN BREAK BROWSE BULK BY CASCADE CASE
CHECK CHECKPOINT CLOSE CLUSTERED COALESCE COLLATE COLUMN COMMIT COMPUTE CONSTRAINT CONTAINS CONTINUE CONVERT CREATE CROSS
CURRENT CURSOR DATABASE DBCC DEALLOCATE DECLARE DEFAULT DELETE DENY DESC DISK DISTINCT DOUBLE DROP DUMP ELSE END ERRLVL
ESCAPE EXCEPT EXEC EXECUTE EXISTS EXIT EXTERNAL FETCH FILE FILLFACTOR FOR FOREIGN FREETEXT FROM FULL FUNCTION GOTO GRANT
GROUP HAVING HOLDLOCK IDENTITY IF IN INDEX INNER INSERT INTERSECT INTO IS JOIN KEY KILL LEFT LIKE LINENO LOAD MERGE
NATIONAL NOCHECK NONCLUSTERED NOT NULL NULLIF OF OFF OFFSETS ON OPEN OPTION OR ORDER OUTER OVER PERCENT PIVOT PLAN
PRECISION PRIMARY PRINT PROC PROCEDURE PUBLIC RAISERROR READ RECONFIGURE REFERENCES REPLICATION RESTORE RESTRICT RETURN
REVERT REVOKE RIGHT ROLLBACK ROWCOUNT RULE SAVE SCHEMA SELECT SET SETUSER SHUTDOWN SOME STATISTICS TABLE TABLESAMPLE THEN
TO TOP TRAN TRANSACTION TRIGGER TRUNCATE UNION UNIQUE UNPIVOT UPDATE USE USER VALUES VARYING VIEW WAITFOR WHEN WHERE
WHILE WITH""".split())
RESERVED = {"oracle": ORACLE_RESERVED, "postgresql": PG_RESERVED, "mysql": MYSQL_RESERVED, "mariadb": MYSQL_RESERVED,
            "mssql": MSSQL_RESERVED}
MAX_IDENT = {"oracle": 128, "postgresql": 63, "mysql": 64, "mariadb": 64, "mssql": 128}

# (regex on DDL text, dialects where it is INVALID, message)
TYPE_RULES = [
    (r"\bVARCHAR2\b|\bNVARCHAR2\b", {"postgresql", "mysql", "mariadb", "mssql"}, "VARCHAR2 is Oracle-only"),
    (r"\bNUMBER\s*\(", {"postgresql", "mysql", "mariadb", "mssql"}, "NUMBER(p,s) is Oracle-only (use NUMERIC/DECIMAL)"),
    (r"\bSERIAL\b|\bBIGSERIAL\b", {"oracle", "mysql", "mssql"}, "SERIAL types are PostgreSQL-only"),
    (r"\bAUTO_INCREMENT\b", {"oracle", "postgresql", "mssql"}, "AUTO_INCREMENT is MySQL/MariaDB-only"),
    (r"\bIDENTITY\s*\(\s*\d+\s*,\s*\d+\s*\)", {"oracle", "postgresql", "mysql", "mariadb"}, "IDENTITY(seed,inc) is SQL Server-only"),
    (r"\bNVARCHAR\s*\(\s*MAX\s*\)|\bDATETIME2\b|\bUNIQUEIDENTIFIER\b", {"oracle", "postgresql", "mysql", "mariadb"}, "SQL Server-only type"),
    (r"\bTIMESTAMPTZ\b|\bJSONB\b|\bBYTEA\b", {"oracle", "mysql", "mariadb", "mssql"}, "PostgreSQL-only type"),
    (r"\bTINYINT\b|\bMEDIUMINT\b|\bDATETIME\b(?!2)", {"oracle", "postgresql"}, "MySQL/SQL Server-only type"),
    (r"\bCLOB\b|\bNCLOB\b", {"postgresql", "mysql", "mariadb", "mssql"}, "CLOB is Oracle-only (TEXT / NVARCHAR(MAX))"),
    (r"\bGETDATE\s*\(", {"oracle", "postgresql", "mysql", "mariadb"}, "GETDATE() is SQL Server-only"),
    (r"\bSYSTIMESTAMP\b", {"postgresql", "mysql", "mariadb", "mssql"}, "SYSTIMESTAMP is Oracle-only"),
    (r"\bENGINE\s*=", {"oracle", "postgresql", "mssql"}, "ENGINE= is MySQL/MariaDB-only"),
    (r"\bNOLOGGING\b", {"mysql", "mariadb", "postgresql", "mssql"}, "NOLOGGING is an Oracle storage clause"),
]


def _blank_strings(s: str) -> str:
    s = re.sub(r"'(?:[^']|'')*'", "''", s)
    s = re.sub(r"\$([A-Za-z_]*)\$.*?\$\1\$", "''", s, flags=re.S)
    return s


def validate_statement(op: M.Operation, dialect: str, profile: dict) -> List[M.Finding]:
    f: List[M.Finding] = []
    st = op.statement
    loc = f"{st.source}:{st.line_start}"
    raw = strip_comments(st.sql, mysql_hash=dialect in ("mysql", "mariadb"))
    s = _blank_strings(raw)

    def add(sev, code, msg, rec=""):
        f.append(M.Finding(sev, code, msg, rec, "syntax", loc))

    if s.count("'") % 2:
        add("HIGH", "UNTERMINATED_STRING", "Unterminated string literal.")
    if s.count("(") != s.count(")"):
        add("HIGH", "UNBALANCED_PARENS", f"Unbalanced parentheses ({s.count('(')} open vs {s.count(')')} close).")
    if re.search(r",\s*\)", s):
        add("HIGH", "TRAILING_COMMA", "Trailing comma before ')'.")
    if re.search(r",\s*,", s):
        add("HIGH", "DOUBLE_COMMA", "Consecutive commas.")
    if s.count('"') % 2:
        add("HIGH", "UNTERMINATED_IDENT", "Unterminated quoted identifier.")
    if op.kind in M.PLSQL_KINDS and dialect in ("oracle", "mysql", "mariadb") and op.kind != M.CREATE_PACKAGE:
        u = s.upper()
        begins = len(re.findall(r"\bBEGIN\b", u)) + len(re.findall(r"\bCASE\b", u)) - len(re.findall(r"\bEND\s+CASE\b", u))
        ends = len(re.findall(r"\bEND\b(?!\s+(IF|LOOP|WHILE|REPEAT|CASE)\b)", u))
        if begins != ends and not re.search(r"\bCOMPOUND\s+TRIGGER\b", u):
            add("HIGH", "BLOCK_MISMATCH", f"BEGIN/CASE ({begins}) and END ({ends}) blocks do not balance.")
        if not re.search(r"\bEND\b\s*[\w\"]*\s*;?\s*$", u.strip()):
            add("MEDIUM", "BLOCK_NO_END", "PL/SQL block does not end with END;")
    if op.kind == M.CREATE_TABLE:
        cols = op.details.get("columns", [])
        if not cols:
            add("HIGH", "TABLE_NO_COLUMNS", "CREATE TABLE has no parsable column definitions.")
        for c in cols:
            if not c.data_type:
                add("HIGH", "COLUMN_NO_TYPE", f"Column {c.name} has no data type.")
    if op.kind in (M.CREATE_TABLE, M.ADD_COLUMN):
        reserved = RESERVED.get(dialect, set())
        for c in op.details.get("columns", []):
            quoted = c.raw.lstrip().startswith(('"', "`", "["))
            if c.name.upper() in reserved:
                if quoted:
                    add("LOW", "RESERVED_QUOTED", f"Column {c.name} is a reserved word - must be quoted in every query.",
                        "Rename the column.")
                else:
                    add("HIGH", "RESERVED_WORD", f"Column {c.name} is a reserved word in {dialect}.", "Rename the column.")
    if op.kind in M.DDL_KINDS:
        for pat, bad, msg in TYPE_RULES:
            if dialect in bad and re.search(pat, s, re.I):
                add("HIGH", "DIALECT_MISMATCH", f"{msg} - statement will fail on {dialect}.")
    names = [op.name] if op.kind.startswith("CREATE") or op.kind == M.ADD_CONSTRAINT else []
    for c in op.details.get("columns", []) if isinstance(op.details.get("columns"), list) else []:
        if isinstance(c, M.Column):
            names.append(c.name)
    lim = profile.get("naming", {}).get("max_identifier_length") or MAX_IDENT.get(dialect, 128)
    warn = profile.get("naming", {}).get("warn_identifier_length")
    for n in names:
        if n and len(n) > lim:
            add("HIGH", "IDENT_TOO_LONG", f"Identifier {n} is {len(n)} chars (limit {lim}).", "Abbreviate the name.")
        elif n and warn and len(n) > warn:
            add("LOW", "IDENT_LONG", f"Identifier {n} is {len(n)} chars (> {warn}) - fails on Oracle < 12.2 / "
                "COMPATIBLE < 12.2 databases.", f"Keep names <= {warn} chars for portability.")
    if op.kind == M.OTHER and op.details.get("parse_error"):
        add("MEDIUM", "PARSE_ERROR", f"Parser could not fully interpret statement: {op.details['parse_error']}")
    if re.search(r";\s*;", s):
        add("LOW", "DOUBLE_SEMICOLON", "Empty statement (;;).")
    if dialect == "oracle" and op.kind not in M.PLSQL_KINDS and re.search(r"\bGO\s*$", s, re.I | re.M):
        add("HIGH", "GO_IN_ORACLE", "'GO' batch separator is SQL Server syntax.")
    return f
