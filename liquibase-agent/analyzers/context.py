"""Shared analysis context."""
from __future__ import annotations

from typing import Dict, List, Optional

from core import models as M
from core.schema import SchemaModel


class AnalysisContext:
    def __init__(self, dialect: str, profile: dict, schema: SchemaModel, ops: List[M.Operation]):
        self.dialect = dialect
        self.profile = profile
        self.schema = schema
        self.ops = ops
        self.new_tables: set = set()
        self.results: Dict[int, dict] = {}    # op.seq -> apply result

    def is_new_table(self, schema: Optional[str], table: Optional[str]) -> bool:
        return self.schema.key(schema, table) in self.new_tables

    @staticmethod
    def loc(op: M.Operation) -> str:
        st = op.statement
        return f"{st.source}:{st.line_start}"

    def finding(self, op: M.Operation, sev: str, code: str, msg: str, rec: str = "", cat: str = "risk") -> M.Finding:
        return M.Finding(sev, code, msg, rec, cat, self.loc(op))
