"""Core data model shared by parsers, analyzers, generators and validators."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

SEVERITY_ORDER = {"INFO": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

# Operation kinds (one Operation == one logical change)
CREATE_TABLE = "CREATE_TABLE"
CREATE_TABLE_AS = "CREATE_TABLE_AS"
DROP_TABLE = "DROP_TABLE"
RENAME_TABLE = "RENAME_TABLE"
TRUNCATE_TABLE = "TRUNCATE_TABLE"
ADD_COLUMN = "ADD_COLUMN"
MODIFY_COLUMN = "MODIFY_COLUMN"
DROP_COLUMN = "DROP_COLUMN"
RENAME_COLUMN = "RENAME_COLUMN"
ADD_CONSTRAINT = "ADD_CONSTRAINT"
DROP_CONSTRAINT = "DROP_CONSTRAINT"
ALTER_TABLE_RAW = "ALTER_TABLE_RAW"
CREATE_INDEX = "CREATE_INDEX"
DROP_INDEX = "DROP_INDEX"
CREATE_VIEW = "CREATE_VIEW"
DROP_VIEW = "DROP_VIEW"
CREATE_SEQUENCE = "CREATE_SEQUENCE"
ALTER_SEQUENCE = "ALTER_SEQUENCE"
DROP_SEQUENCE = "DROP_SEQUENCE"
CREATE_TRIGGER = "CREATE_TRIGGER"
DROP_TRIGGER = "DROP_TRIGGER"
CREATE_PROCEDURE = "CREATE_PROCEDURE"
CREATE_FUNCTION = "CREATE_FUNCTION"
CREATE_PACKAGE = "CREATE_PACKAGE"
CREATE_PACKAGE_BODY = "CREATE_PACKAGE_BODY"
DROP_ROUTINE = "DROP_ROUTINE"
COMMENT = "COMMENT"
GRANT = "GRANT"
REVOKE = "REVOKE"
INSERT = "INSERT"
UPDATE = "UPDATE"
DELETE = "DELETE"
MERGE = "MERGE"
PLSQL_BLOCK = "PLSQL_BLOCK"
TX_CONTROL = "TX_CONTROL"          # COMMIT / ROLLBACK
CLIENT_COMMAND = "CLIENT_COMMAND"  # SQL*Plus / psql / sqlcmd directives
TRACKER = "TRACKER"                # house change-tracker bookkeeping statements
OTHER = "OTHER"

DDL_KINDS = {
    CREATE_TABLE, CREATE_TABLE_AS, DROP_TABLE, RENAME_TABLE, TRUNCATE_TABLE, ADD_COLUMN,
    MODIFY_COLUMN, DROP_COLUMN, RENAME_COLUMN, ADD_CONSTRAINT, DROP_CONSTRAINT, ALTER_TABLE_RAW,
    CREATE_INDEX, DROP_INDEX, CREATE_VIEW, DROP_VIEW, CREATE_SEQUENCE, ALTER_SEQUENCE,
    DROP_SEQUENCE, CREATE_TRIGGER, DROP_TRIGGER, CREATE_PROCEDURE, CREATE_FUNCTION,
    CREATE_PACKAGE, CREATE_PACKAGE_BODY, DROP_ROUTINE, COMMENT, GRANT, REVOKE,
}
DML_KINDS = {INSERT, UPDATE, DELETE, MERGE, PLSQL_BLOCK}
PLSQL_KINDS = {CREATE_TRIGGER, CREATE_PROCEDURE, CREATE_FUNCTION, CREATE_PACKAGE,
               CREATE_PACKAGE_BODY, PLSQL_BLOCK}
REPLACEABLE_KINDS = {CREATE_VIEW, CREATE_TRIGGER, CREATE_PROCEDURE, CREATE_FUNCTION,
                     CREATE_PACKAGE, CREATE_PACKAGE_BODY}


@dataclass
class Column:
    name: str
    data_type: str = ""
    nullable: Optional[bool] = None      # None = not specified
    default: Optional[str] = None
    primary_key: bool = False
    pk_name: Optional[str] = None
    unique: bool = False
    unique_name: Optional[str] = None
    references: Optional[Dict[str, Any]] = None  # {name, schema, table, columns, on_delete}
    check: Optional[str] = None
    check_name: Optional[str] = None
    auto_increment: bool = False
    remarks: Optional[str] = None
    raw: str = ""

    def definition_sql(self) -> str:
        if self.raw:
            return self.raw
        parts = [self.name, self.data_type]
        if self.default is not None:
            parts.append("DEFAULT " + self.default)
        if self.nullable is False:
            parts.append("NOT NULL")
        return " ".join(p for p in parts if p)


@dataclass
class Constraint:
    name: Optional[str]
    ctype: str                      # PRIMARY KEY | UNIQUE | FOREIGN KEY | CHECK | NOT NULL
    columns: List[str] = field(default_factory=list)
    ref_schema: Optional[str] = None
    ref_table: Optional[str] = None
    ref_columns: List[str] = field(default_factory=list)
    on_delete: Optional[str] = None
    check_expr: Optional[str] = None
    raw: str = ""

    def definition_sql(self) -> str:
        if self.raw:
            return self.raw
        head = f"CONSTRAINT {self.name} " if self.name else ""
        cols = ", ".join(self.columns)
        if self.ctype == "CHECK":
            return f"{head}CHECK ({self.check_expr})"
        if self.ctype == "FOREIGN KEY":
            ref = f"{self.ref_schema + '.' if self.ref_schema else ''}{self.ref_table}"
            s = f"{head}FOREIGN KEY ({cols}) REFERENCES {ref} ({', '.join(self.ref_columns)})"
            if self.on_delete:
                s += f" ON DELETE {self.on_delete}"
            return s
        return f"{head}{self.ctype} ({cols})"


@dataclass
class Statement:
    """A raw statement split from an input script."""
    sql: str
    line_start: int
    line_end: int
    source: str = "<input>"
    leading_comment: str = ""
    delimiter: str = ";"
    is_plsql: bool = False


@dataclass
class Operation:
    """One logical change derived from a statement."""
    kind: str
    schema: Optional[str]
    name: str                         # primary object name (table/index/view/...)
    sql: str                          # SQL fragment that performs exactly this change
    statement: Statement
    table: Optional[str] = None       # owning table (for index/trigger/column/constraint ops)
    object_type: str = ""             # TABLE / INDEX / VIEW / SEQUENCE / TRIGGER / PROCEDURE ...
    details: Dict[str, Any] = field(default_factory=dict)
    or_replace: bool = False
    seq: int = 0                      # position in input

    @property
    def qualified(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name

    @property
    def qualified_table(self) -> str:
        t = self.table or self.name
        return f"{self.schema}.{t}" if self.schema else t

    @property
    def is_ddl(self) -> bool:
        return self.kind in DDL_KINDS

    @property
    def is_dml(self) -> bool:
        return self.kind in DML_KINDS


@dataclass
class Finding:
    severity: str          # INFO | LOW | MEDIUM | HIGH | CRITICAL
    code: str
    message: str
    recommendation: str = ""
    category: str = "risk"  # risk | syntax | liquibase | naming | rollback | conflict | best_practice
    location: str = ""

    def as_dict(self):
        return self.__dict__.copy()


@dataclass
class Rollback:
    sql: List[str] = field(default_factory=list)
    xml: List[str] = field(default_factory=list)
    complete: bool = True
    notes: List[str] = field(default_factory=list)
    pre_sql: List[str] = field(default_factory=list)   # backup statements to run BEFORE the change


@dataclass
class ChangeUnit:
    """A group of operations emitted together (one changeSet / one deploy script)."""
    operations: List[Operation]
    unit_type: str          # TABLE | ALTER | INDEX | VIEW | TRIGGER | ROUTINE | SEQUENCE | DML | DROP | GRANT | COMMENT | OTHER
    label: str              # object label used for file naming
    schema: Optional[str]
    changeset_id: str = ""
    seq: int = 0
    file_name: str = ""
    comment: str = ""
    rollbacks: List[Rollback] = field(default_factory=list)
    replaces_existing: bool = False

    @property
    def is_plsql(self) -> bool:
        return any(op.kind in PLSQL_KINDS for op in self.operations)

    @property
    def is_dml(self) -> bool:
        return all(op.is_dml for op in self.operations)


def max_severity(findings: List[Finding]) -> str:
    if not findings:
        return "INFO"
    return max(findings, key=lambda f: SEVERITY_ORDER[f.severity]).severity
