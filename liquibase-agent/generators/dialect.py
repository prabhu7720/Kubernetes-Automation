"""Dialect specific SQL builders used by rollback / check generators."""
from __future__ import annotations

from typing import List, Optional

from core import models as M


def q(schema: Optional[str], name: str) -> str:
    return f"{schema}.{name}" if schema else name


def sql_str(s: Optional[str]) -> str:
    return "'" + (s or "").replace("'", "''") + "'"


class Dialect:
    def __init__(self, name: str, oracle_cascade: bool = True):
        self.name = name
        self.oracle_cascade = oracle_cascade

    # ------------------------------------------------------------- tables
    def drop_table(self, schema, table) -> str:
        if self.name == "oracle":
            return f"DROP TABLE {q(schema, table)}{' CASCADE CONSTRAINTS' if self.oracle_cascade else ''}"
        if self.name == "postgresql":
            return f"DROP TABLE {q(schema, table)}"
        return f"DROP TABLE {q(schema, table)}"

    def add_columns(self, schema, table, cols: List[M.Column]) -> str:
        defs = [self.coldef(c) for c in cols]
        t = q(schema, table)
        if self.name == "oracle":
            return f"ALTER TABLE {t} ADD ({', '.join(defs)})"
        if self.name == "mssql":
            return f"ALTER TABLE {t} ADD {', '.join(defs)}"
        return f"ALTER TABLE {t} " + ", ".join(f"ADD COLUMN {d}" for d in defs)

    def drop_columns(self, schema, table, cols: List[str]) -> str:
        t = q(schema, table)
        if self.name == "oracle":
            return f"ALTER TABLE {t} DROP ({', '.join(cols)})" if len(cols) > 1 else f"ALTER TABLE {t} DROP COLUMN {cols[0]}"
        if self.name == "mssql":
            return f"ALTER TABLE {t} DROP COLUMN {', '.join(cols)}"
        return f"ALTER TABLE {t} " + ", ".join(f"DROP COLUMN {c}" for c in cols)

    def coldef(self, c: M.Column) -> str:
        parts = [c.name, c.data_type or ""]
        if c.default is not None:
            parts.append(f"DEFAULT {c.default}")
        if c.nullable is False:
            parts.append("NOT NULL")
        return " ".join(p for p in parts if p)

    def modify_column(self, schema, table, old: M.Column, new: M.Column) -> List[str]:
        """Statements that turn column `new` back into `old` (only attributes that changed)."""
        t = q(schema, table)
        out = []
        type_changed = bool(new.data_type) and old.data_type and old.data_type.upper() != new.data_type.upper()
        null_changed = new.nullable is not None and old.nullable is not None and (bool(old.nullable) != bool(new.nullable))
        null_inverse_only = new.nullable is not None and old.nullable is None
        target_nullable = old.nullable if old.nullable is not None else (not new.nullable if null_inverse_only else None)
        def_changed = new.default is not None and (old.default or "") != (new.default or "")
        if self.name == "oracle":
            parts = [old.name]
            if type_changed:
                parts.append(old.data_type)
            if def_changed:
                parts.append(f"DEFAULT {old.default if old.default is not None else 'NULL'}")
            if null_changed or null_inverse_only:
                parts.append("NULL" if target_nullable else "NOT NULL")
            if len(parts) > 1:
                out.append(f"ALTER TABLE {t} MODIFY ({' '.join(parts)})")
        elif self.name == "postgresql":
            if type_changed:
                out.append(f"ALTER TABLE {t} ALTER COLUMN {old.name} TYPE {old.data_type}")
            if def_changed:
                out.append(f"ALTER TABLE {t} ALTER COLUMN {old.name} " +
                           (f"SET DEFAULT {old.default}" if old.default is not None else "DROP DEFAULT"))
            if null_changed or null_inverse_only:
                out.append(f"ALTER TABLE {t} ALTER COLUMN {old.name} {'DROP' if target_nullable else 'SET'} NOT NULL")
        elif self.name in ("mysql", "mariadb"):
            if old.data_type:
                out.append(f"ALTER TABLE {t} MODIFY COLUMN {self.coldef(old)}" +
                           ("" if old.nullable is False else " NULL"))
        elif self.name == "mssql":
            if old.data_type:
                out.append(f"ALTER TABLE {t} ALTER COLUMN {old.name} {old.data_type} "
                           f"{'NULL' if (target_nullable if target_nullable is not None else True) else 'NOT NULL'}")
        return out

    # ------------------------------------------------------------- constraints / indexes
    def add_constraint(self, schema, table, c: M.Constraint) -> str:
        body = c.raw if c.raw and c.raw.upper().lstrip().startswith(("CONSTRAINT", "PRIMARY", "UNIQUE", "FOREIGN", "CHECK")) \
            else c.definition_sql()
        if not body.upper().startswith("CONSTRAINT") and c.name:
            body = f"CONSTRAINT {c.name} {body}"
        return f"ALTER TABLE {q(schema, table)} ADD {body}"

    def drop_constraint(self, schema, table, name: Optional[str], ctype: str = "") -> str:
        t = q(schema, table)
        if self.name in ("mysql", "mariadb"):
            if ctype == "FOREIGN KEY":
                return f"ALTER TABLE {t} DROP FOREIGN KEY {name}"
            if ctype == "PRIMARY KEY":
                return f"ALTER TABLE {t} DROP PRIMARY KEY"
            if ctype == "UNIQUE":
                return f"ALTER TABLE {t} DROP INDEX {name}"
            if ctype == "CHECK":
                return f"ALTER TABLE {t} DROP CHECK {name}"
        if not name and ctype == "PRIMARY KEY" and self.name == "oracle":
            return f"ALTER TABLE {t} DROP PRIMARY KEY"
        return f"ALTER TABLE {t} DROP CONSTRAINT {name}"

    def drop_index(self, schema, index, table_schema, table) -> str:
        if self.name in ("mysql", "mariadb", "mssql"):
            return f"DROP INDEX {index} ON {q(table_schema or schema, table)}"
        return f"DROP INDEX {q(schema, index)}"

    # ------------------------------------------------------------- code objects
    def drop_object(self, otype: str, schema, name, table=None) -> str:
        otype = otype.upper()
        if otype == "TRIGGER" and self.name == "postgresql":
            return f"DROP TRIGGER {name} ON {q(schema, table)}"
        if otype == "MATERIALIZED VIEW":
            return f"DROP MATERIALIZED VIEW {q(schema, name)}"
        if otype == "TYPE BODY":
            return f"DROP TYPE BODY {q(schema, name)}"
        return f"DROP {otype} {q(schema, name)}"

    def comment(self, target: str, schema, table, column, text) -> Optional[str]:
        if self.name in ("oracle", "postgresql"):
            if target == "COLUMN":
                return f"COMMENT ON COLUMN {q(schema, table)}.{column} IS {sql_str(text)}"
            return f"COMMENT ON {target if target in ('TABLE', 'VIEW', 'MATERIALIZED VIEW') else 'TABLE'} {q(schema, table)} IS {sql_str(text)}"
        if self.name in ("mysql", "mariadb") and target != "COLUMN":
            return f"ALTER TABLE {q(schema, table)} COMMENT = {sql_str(text)}"
        return None

    def rename_column(self, schema, table, old, new) -> str:
        if self.name == "mssql":
            return f"EXEC sp_rename '{q(schema, table)}.{old}', '{new}', 'COLUMN'"
        return f"ALTER TABLE {q(schema, table)} RENAME COLUMN {old} TO {new}"

    def rename_table(self, schema, old, new) -> str:
        if self.name == "oracle":
            return f"ALTER TABLE {q(schema, old)} RENAME TO {new}"
        if self.name == "mssql":
            return f"EXEC sp_rename '{q(schema, old)}', '{new}'"
        return f"ALTER TABLE {q(schema, old)} RENAME TO {new}"

    def ctas_backup(self, schema, table, bkp, where: Optional[str]) -> str:
        w = f" WHERE {where}" if where else ""
        if self.name == "mssql":
            return f"SELECT * INTO {q(schema, bkp)} FROM {q(schema, table)}{w}"
        return f"CREATE TABLE {q(schema, bkp)} AS SELECT * FROM {q(schema, table)}{w}"
