"""LiquibaseAgent - orchestrates parse -> analyse -> generate -> validate. 100% offline."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from core import models as M
from core.schema import SchemaModel
from parsers.sql_parser import (detect_dialect, is_liquibase_formatted, is_liquibase_xml, normalize_dialect,
                                split_statements)
from parsers.ddl_parser import DDLParser
from parsers import liquibase_parser as LP
from analyzers.context import AnalysisContext
from analyzers import table_analyzer, index_analyzer, procedure_analyzer, dml_analyzer, dependency_analyzer
from generators.rollback_generator import RollbackGenerator
from generators.check_generator import CheckGenerator
from generators.grouping import group
from generators.naming import Namer
from generators.liquibase_generator import XmlChangelogGenerator, FormattedSqlGenerator
from validators import syntax_validator, naming_validator, rollback_validator, liquibase_validator, best_practice_validator
from templates.loader import Templates

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQL_EXT = (".sql", ".ddl", ".pls", ".pks", ".pkb", ".prc", ".fnc", ".trg", ".vw", ".tab", ".idx", ".seq", ".xml", ".txt")

TABLE_KINDS = {M.CREATE_TABLE, M.CREATE_TABLE_AS, M.DROP_TABLE, M.TRUNCATE_TABLE, M.ADD_COLUMN, M.MODIFY_COLUMN,
               M.DROP_COLUMN, M.RENAME_COLUMN, M.RENAME_TABLE, M.ADD_CONSTRAINT, M.DROP_CONSTRAINT, M.ALTER_TABLE_RAW}
INDEX_KINDS = {M.CREATE_INDEX, M.DROP_INDEX, M.CREATE_SEQUENCE, M.DROP_SEQUENCE, M.ALTER_SEQUENCE}
CODE_KINDS = {M.CREATE_VIEW, M.CREATE_TRIGGER, M.CREATE_PROCEDURE, M.CREATE_FUNCTION, M.CREATE_PACKAGE,
              M.CREATE_PACKAGE_BODY, M.PLSQL_BLOCK, M.DROP_VIEW, M.DROP_TRIGGER, M.DROP_ROUTINE}


@dataclass
class OpResult:
    op: M.Operation
    impact: str = ""
    findings: List[M.Finding] = field(default_factory=list)
    rollback: Optional[M.Rollback] = None
    checks: dict = field(default_factory=dict)
    apply: dict = field(default_factory=dict)


@dataclass
class AgentResult:
    dialect: str
    profile: dict
    release: str
    sources: List[str]
    ops: List[M.Operation]
    results: List[OpResult]
    findings: List[M.Finding]
    xml: Optional[str] = None
    xml_meta: List[dict] = field(default_factory=list)
    sql_files: Dict[str, str] = field(default_factory=dict)
    sql_meta: List[dict] = field(default_factory=list)
    units_xml: List[M.ChangeUnit] = field(default_factory=list)
    units_sql: List[M.ChangeUnit] = field(default_factory=list)
    release_checks: dict = field(default_factory=dict)
    input_changelogs: List[LP.ChangelogFile] = field(default_factory=list)
    namer: Optional[Namer] = None
    dialect_scores: dict = field(default_factory=dict)
    xml_file: str = ""


class LiquibaseAgent:
    def __init__(self, profile: dict, dialect: Optional[str] = None, release: Optional[str] = None,
                 author: Optional[str] = None, default_schema: Optional[str] = None):
        self.p = profile
        if author:
            self.p["author"] = author
        if default_schema:
            self.p["default_schema"] = default_schema
        self.release = release or profile.get("release", "1.0")
        self.dialect = normalize_dialect(dialect or profile.get("dialect") or "")
        self.tpl = Templates(os.path.join(HERE, "templates"))
        self.tracker_table = (profile.get("tracker", {}) or {}).get("table", "")
        self.baseline_sources: List[str] = []
        self.existing_changelogs: List[LP.ChangelogFile] = []
        self._baseline_texts: List[tuple] = []

    # ------------------------------------------------------------------ input helpers
    @staticmethod
    def expand(paths: List[str]) -> List[str]:
        out = []
        for p in paths:
            if os.path.isdir(p):
                for root, dirs, files in os.walk(p):
                    dirs.sort()
                    for fn in sorted(files):
                        if fn.lower().endswith(SQL_EXT):
                            out.append(os.path.join(root, fn))
            elif os.path.isfile(p):
                out.append(p)
            else:
                raise FileNotFoundError(p)
        return out

    @staticmethod
    def read(path: str) -> str:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()

    def add_baseline(self, paths: List[str]):
        """Existing DDL (DBMS_METADATA / pg_dump -s / mysqldump -d / SSMS scripts) or deployed changelogs."""
        for f in self.expand(paths):
            self._baseline_texts.append((f, self.read(f)))

    def add_existing_changelogs(self, paths: List[str]):
        for f in LP.collect_changelog_files(paths):
            self.existing_changelogs.append(LP.parse_changelog(f))

    # ------------------------------------------------------------------ main
    def run(self, inputs: List[str], formats=("xml", "sql"), start_seq: Optional[int] = None,
            inline_sql: Optional[str] = None) -> AgentResult:
        files = self.expand(inputs) if inputs else []
        texts = [(f, self.read(f)) for f in files]
        if inline_sql:
            texts.append(("<stdin>", inline_sql))
        if not texts:
            raise ValueError("No input SQL supplied.")
        joined = "\n".join(t for _, t in texts)
        scores = {}
        if not self.dialect:
            self.dialect, scores = detect_dialect(joined, default="oracle")
        d = self.dialect
        default_schema = self.p.get("default_schema") or None
        parser = DDLParser(d, default_schema=default_schema, tracker_table=self.tracker_table)

        # ---- baseline schema model
        sm = SchemaModel(default_schema)
        for path, text in self._baseline_texts:
            ops = self._text_to_ops(path, text, parser)
            sm.load_operations(ops, path, origin="baseline")
        for cf in self.existing_changelogs:
            ops = []
            for cs in cf.changesets:
                sqls = LP.xml_changes_to_sql(cs, d) if cf.fmt == "xml" else [cs.sql]
                for s in sqls:
                    for st in split_statements(s, d, cf.path):
                        ops.extend(parser.parse(st))
            sm.load_operations(ops, cf.path, origin="changelog")

        # ---- parse inputs
        input_changelogs = []
        ops: List[M.Operation] = []
        for path, text in texts:
            if is_liquibase_xml(text) or is_liquibase_formatted(text):
                input_changelogs.append(LP.parse_xml(path, text) if is_liquibase_xml(text) else LP.parse_formatted_sql(path, text))
            ops.extend(self._text_to_ops(path, text, parser))
        all_ops = ops
        ops = [o for o in ops if o.kind not in (M.TRACKER, M.TX_CONTROL)]
        ops = self._synthesize_grants(ops, parser)
        for i, op in enumerate(ops, 1):
            op.seq = i

        # ---- analyse
        ctx = AnalysisContext(d, self.p, sm, ops)
        rbgen = RollbackGenerator(d, sm, self.p)
        chk = CheckGenerator(d, self.p, sm)
        results: List[OpResult] = []
        findings: List[M.Finding] = []
        for op in ops:
            r = OpResult(op)
            r.findings += syntax_validator.validate_statement(op, d, self.p) if op.kind not in (M.TRACKER, M.TX_CONTROL) else []
            if op.kind in INDEX_KINDS:
                r.findings += index_analyzer.before_apply(op, ctx)
            if op.kind in CODE_KINDS:
                r.findings += procedure_analyzer.before_apply(op, ctx)
            if op.kind == M.CREATE_INDEX:
                op.details["_new_table"] = ctx.is_new_table(op.details.get("table_schema") or op.schema, op.table)
            if op.kind in (M.DROP_COLUMN, M.RENAME_COLUMN):
                cols = op.details.get("columns") or [op.details.get("column")]
                op.details["_dependents"] = sm.dependents_on_column(op.schema, op.table, [c for c in cols if c])
            res = sm.apply(op)
            r.apply = res
            r.findings += res["conflicts"]
            for c in r.findings:
                c.location = c.location or ctx.loc(op)
            if op.kind in (M.CREATE_TABLE, M.CREATE_TABLE_AS):
                ctx.new_tables.add(sm.key(op.schema, op.name))
            if op.kind == M.DROP_CONSTRAINT and res.get("before") is not None:
                op.details["_before_ctype"] = res["before"].ctype
            if op.kind in TABLE_KINDS:
                fs, imp = table_analyzer.analyze(op, res, ctx)
            elif op.kind in INDEX_KINDS:
                fs, imp = index_analyzer.analyze(op, res, ctx)
            elif op.kind in CODE_KINDS:
                fs, imp = procedure_analyzer.analyze(op, res, ctx)
            else:
                fs, imp = dml_analyzer.analyze(op, res, ctx)
            r.findings += fs
            r.impact = imp
            r.rollback = rbgen.generate(op, res)
            r.checks = chk.for_operation(op, res) if op.kind not in (M.TRACKER, M.TX_CONTROL, M.CLIENT_COMMAND) else {}
            ctx.results[op.seq] = res
            results.append(r)
            findings += r.findings
        findings += dependency_analyzer.analyze_release(ops, ctx)
        work_ops = [o for o in ops if o.kind not in (M.TRACKER, M.TX_CONTROL)]
        findings += naming_validator.validate(work_ops, self.p, d)
        findings += naming_validator.validate_author(self.p.get("author", ""), self.p)
        findings += best_practice_validator.validate(ops + [o for o in all_ops if o.kind in (M.TRACKER, M.TX_CONTROL)], self.p, d)

        # ---- generate
        namer = Namer(self.p, self.release)
        if start_seq is None:
            start_seq = self._next_seq(namer)
        rbs = {r.op.seq: r.rollback for r in results if r.rollback}
        res_obj = AgentResult(d, self.p, self.release, [p for p, _ in texts], ops, results, findings, namer=namer,
                              dialect_scores=scores, input_changelogs=input_changelogs)
        if "xml" in formats:
            units = group(ops, "statement")
            gen = XmlChangelogGenerator(d, self.p, self.tpl, namer)
            res_obj.xml, res_obj.xml_meta = gen.generate(units, rbs, [os.path.basename(p) for p, _ in texts], start_seq)
            res_obj.units_xml = units
            res_obj.xml_file = namer.xml_file_name()
        if "sql" in formats:
            units = group(ops, self.p.get("sql_group_by", "object"))
            for u in units:
                u.replaces_existing = any(ctx.results.get(o.seq, {}).get("existed") or
                                          (o.or_replace and o.kind == M.CREATE_TRIGGER and self._existed_before(o, ops))
                                          for o in u.operations)
            gen = FormattedSqlGenerator(d, self.p, self.tpl, namer, sm)
            res_obj.sql_files, res_obj.sql_meta = gen.generate(units, rbs, start_seq, self.p.get("file_number_offset", 0))
            res_obj.units_sql = units

        # ---- validate generated output + existing changelogs
        gen_sets = []
        if res_obj.xml:
            gen_sets.append([LP.parse_xml(res_obj.xml_file, res_obj.xml)])
            findings += rollback_validator.validate_generated(res_obj.xml_meta, "xml")
        if res_obj.sql_files:
            gen_sets.append([LP.parse_formatted_sql(n, t) for n, t in res_obj.sql_files.items()])
            findings += rollback_validator.validate_generated(res_obj.sql_meta, "formatted-sql")
        if not gen_sets and self.existing_changelogs:
            gen_sets.append([])
        for gen_files in gen_sets:
            lb_findings = liquibase_validator.validate(gen_files + self.existing_changelogs, self.p, self.tracker_table)
            for fnd in lb_findings:
                if any(fnd.location.startswith(g.path) for g in gen_files):
                    fnd.message = "[generated] " + fnd.message
            findings += [x for x in lb_findings if not (x.code == "LB_ID_GAP" and not self.existing_changelogs)]
        if input_changelogs:
            for x in liquibase_validator.validate(input_changelogs, self.p, self.tracker_table):
                x.message = "[input changelog] " + x.message
                findings.append(x)
            for x in rollback_validator.validate_existing(input_changelogs, self.tracker_table):
                x.message = "[input changelog] " + x.message
                findings.append(x)
        schemas = sorted({o.schema for o in work_ops if o.schema}) or [None]
        res_obj.release_checks = {"pre": chk.release_pre_checks(schemas), "post": chk.release_post_checks(schemas)}
        res_obj.findings = _dedupe(findings)
        return res_obj

    # ------------------------------------------------------------------ helpers
    def _existed_before(self, op, ops):
        return False

    def _text_to_ops(self, path, text, parser) -> List[M.Operation]:
        ops = []
        if is_liquibase_xml(text):
            cf = LP.parse_xml(path, text)
            for cs in cf.changesets:
                for s in LP.xml_changes_to_sql(cs, self.dialect):
                    for st in split_statements(s, self.dialect, path):
                        ops.extend(parser.parse(st))
            return ops
        for st in split_statements(text, self.dialect, path):
            ops.extend(parser.parse(st))
        return ops

    def _synthesize_grants(self, ops: List[M.Operation], parser: DDLParser) -> List[M.Operation]:
        g = self.p.get("grants", {}) or {}
        if not g.get("auto_generate"):
            return ops
        granted = {(o.schema or "").upper() + "." + (o.name or "").upper() for o in ops if o.kind == M.GRANT}
        kinds = {M.CREATE_TABLE: "table", M.CREATE_TABLE_AS: "table", M.CREATE_VIEW: "view",
                 M.CREATE_SEQUENCE: "sequence", M.CREATE_PROCEDURE: "routine", M.CREATE_FUNCTION: "routine",
                 M.CREATE_PACKAGE: "routine"}
        out = list(ops)
        inserts = []
        for idx, op in enumerate(ops):
            key = kinds.get(op.kind)
            if not key or not op.schema:
                continue
            q = op.schema.upper() + "." + op.name.upper()
            if q in granted:
                continue
            rules = list(g.get(key, []))
            if key == "table" and re.search(g.get("readonly_table_regex", "$^"), op.name, re.I):
                rules = [r for r in rules if r.get("privileges", "").upper() == "SELECT"]
            if not rules:
                continue
            pos = idx
            for j in range(idx + 1, len(ops)):
                o2 = ops[j]
                if (o2.table or o2.name or "").upper() == op.name.upper() and o2.kind in (M.CREATE_INDEX, M.COMMENT, M.ADD_CONSTRAINT):
                    pos = j
                elif o2.kind in (M.CREATE_INDEX, M.COMMENT):
                    continue
                else:
                    break
            for r in rules:
                grantee = r["grantee"].format(schema=op.schema.upper())
                sql = self.p.get("grant_sql_pattern", "GRANT {privileges} ON {schema}.{object} TO {grantee}").format(
                    privileges=r["privileges"], schema=op.schema, object=op.name, grantee=grantee)
                st = M.Statement(sql=sql, line_start=op.statement.line_start, line_end=op.statement.line_start,
                                 source=op.statement.source, leading_comment="")
                for gop in parser.parse(st):
                    gop.details["_synthetic"] = True
                    gop.sql = sql
                    inserts.append((pos, gop))
        for pos, gop in reversed(sorted(inserts, key=lambda x: x[0])):
            out.insert(pos + 1, gop)
        # keep original relative order of multiple grants on same position
        return _stable_grants(out)

    def _next_seq(self, namer: Namer) -> int:
        if not self.existing_changelogs:
            return int(self.p.get("start_seq", 1))
        probe = namer.changeset_id(987654321)
        prefix = probe.split("987654321")[0]
        mx = 0
        for cf in self.existing_changelogs:
            for cs in cf.changesets:
                cid = re.sub(r"-(pre|post|bkp)$", "", cs.id)
                if cid.startswith(prefix):
                    m = re.match(r"(\d+)", cid[len(prefix):])
                    if m:
                        mx = max(mx, int(m.group(1)))
        return mx + 1 if mx else int(self.p.get("start_seq", 1))


def _stable_grants(ops):
    return ops


def _dedupe(findings: List[M.Finding]) -> List[M.Finding]:
    seen, out = set(), []
    for f in findings:
        k = (f.code, f.message, f.location)
        if k in seen:
            continue
        seen.add(k)
        out.append(f)
    return sorted(out, key=lambda f: -M.SEVERITY_ORDER[f.severity])
