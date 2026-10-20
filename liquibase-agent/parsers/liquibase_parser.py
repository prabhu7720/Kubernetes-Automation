"""Parser for existing Liquibase changelogs (XML and formatted SQL).

Used to: detect duplicate changeSet ids, continue the id sequence of a release,
validate existing files and seed the schema model with already-deployed objects.
"""
from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional

CHANGESET_RE = re.compile(r"^\s*--\s*changeset\s+([^:\s]+):(\S+)(.*)$", re.IGNORECASE)
ATTR_RE = re.compile(r'(\w+):("([^"]*)"|\S+)')


@dataclass
class ChangeSetInfo:
    id: str
    author: str
    file: str
    line: int
    fmt: str                         # xml | sql
    attrs: Dict[str, str] = field(default_factory=dict)
    sql: str = ""
    rollback: str = ""
    has_rollback: bool = False
    rollback_empty: bool = False
    change_types: List[str] = field(default_factory=list)
    comment: str = ""
    preconditions: bool = False
    xml_element: Optional[object] = None

    @property
    def key(self) -> str:
        return f"{self.author}:{self.id}"


@dataclass
class ChangelogFile:
    path: str
    fmt: str
    changesets: List[ChangeSetInfo] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    header_ok: bool = True
    includes: List[str] = field(default_factory=list)


def _local(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def parse_formatted_sql(path: str, text: Optional[str] = None) -> ChangelogFile:
    text = text if text is not None else open(path, encoding="utf-8", errors="replace").read()
    lines = text.replace("\r\n", "\n").split("\n")
    cf = ChangelogFile(path, "sql")
    first = next((ln for ln in lines if ln.strip()), "")
    cf.header_ok = bool(re.match(r"^\s*--\s*liquibase\s+formatted\s+sql", first, re.I))
    if not cf.header_ok:
        cf.errors.append("First non-blank line must be '--liquibase formatted sql'.")
    cur: Optional[ChangeSetInfo] = None
    body, rb = [], []
    for no, ln in enumerate(lines, 1):
        m = CHANGESET_RE.match(ln)
        if m:
            if cur:
                cur.sql, cur.rollback = "\n".join(body).strip(), "\n".join(rb).strip()
                cf.changesets.append(cur)
            attrs = {a: (v2 if v2 else v) for a, v, v2 in ATTR_RE.findall(m.group(3))}
            cur = ChangeSetInfo(m.group(2), m.group(1), path, no, "sql", attrs)
            body, rb = [], []
            continue
        if cur is None:
            continue
        s = ln.strip()
        rm = re.match(r"^--\s*rollback\b\s?(.*)$", s, re.I)
        if rm:
            cur.has_rollback = True
            val = rm.group(1)
            if val.strip().lower() in ("empty", "not required", "none"):
                cur.rollback_empty = True
            rb.append(val)
            continue
        if re.match(r"^--\s*comment\s*:", s, re.I):
            cur.comment = s.split(":", 1)[1].strip()
            continue
        if re.match(r"^--\s*precondition", s, re.I):
            cur.preconditions = True
            continue
        body.append(ln)
    if cur:
        cur.sql, cur.rollback = "\n".join(body).strip(), "\n".join(rb).strip()
        cf.changesets.append(cur)
    return cf


def parse_xml(path: str, text: Optional[str] = None) -> ChangelogFile:
    cf = ChangelogFile(path, "xml")
    try:
        root = ET.fromstring(text) if text is not None else ET.parse(path).getroot()
    except ET.ParseError as exc:
        cf.errors.append(f"XML not well-formed: {exc}")
        cf.header_ok = False
        return cf
    if _local(root.tag) != "databaseChangeLog":
        cf.errors.append(f"Root element must be databaseChangeLog (found {_local(root.tag)}).")
        cf.header_ok = False
    for el in root:
        tag = _local(el.tag)
        if tag in ("include", "includeAll"):
            cf.includes.append(el.get("file") or el.get("path") or "")
        if tag != "changeSet":
            continue
        cs = ChangeSetInfo(el.get("id", ""), el.get("author", ""), path, 0, "xml",
                           {k: v for k, v in el.attrib.items() if k not in ("id", "author")}, xml_element=el)
        sqls = []
        for ch in el:
            ct = _local(ch.tag)
            if ct == "rollback":
                cs.has_rollback = True
                cs.rollback = (ch.text or "").strip() + "".join(_local(x.tag) + " " for x in ch)
                if not (ch.text or "").strip() and len(ch) == 0:
                    cs.rollback_empty = True
                continue
            if ct == "comment":
                cs.comment = (ch.text or "").strip()
                continue
            if ct == "preConditions":
                cs.preconditions = True
                continue
            if ct in ("validCheckSum", "modifySql", "tagDatabase"):
                continue
            cs.change_types.append(ct)
            if ct in ("sql", "createProcedure"):
                sqls.append((ch.text or "").strip())
        cs.sql = "\n".join(sqls)
        cf.changesets.append(cs)
    return cf


def parse_changelog(path: str) -> ChangelogFile:
    text = open(path, encoding="utf-8", errors="replace").read()
    if path.lower().endswith(".xml") or "<databaseChangeLog" in text[:3000]:
        return parse_xml(path, text)
    return parse_formatted_sql(path, text)


def collect_changelog_files(paths: List[str]) -> List[str]:
    out = []
    for p in paths:
        if os.path.isdir(p):
            for root, _, files in os.walk(p):
                for f in sorted(files):
                    if f.lower().endswith((".xml", ".sql")):
                        out.append(os.path.join(root, f))
        elif os.path.isfile(p):
            out.append(p)
    return out


def xml_changes_to_sql(cs: ChangeSetInfo, dialect: str) -> List[str]:
    """Translate common XML change types to SQL so they can seed the schema model."""
    el = cs.xml_element
    if el is None:
        return []
    out = []
    for ch in el:
        ct = _local(ch.tag)
        s = ch.get("schemaName")
        q = (lambda n: f"{s}.{n}" if s else n)
        if ct == "createTable":
            cols = []
            for c in ch:
                if _local(c.tag) != "column":
                    continue
                d = f"{c.get('name')} {c.get('type', 'VARCHAR(1)')}"
                for k in c:
                    if _local(k.tag) == "constraints":
                        if k.get("primaryKey") == "true":
                            d += " PRIMARY KEY"
                        if k.get("nullable") == "false":
                            d += " NOT NULL"
                cols.append(d)
            out.append(f"CREATE TABLE {q(ch.get('tableName'))} ({', '.join(cols)})")
        elif ct == "addColumn":
            for c in ch:
                if _local(c.tag) == "column":
                    out.append(f"ALTER TABLE {q(ch.get('tableName'))} ADD {c.get('name')} {c.get('type')}")
        elif ct == "dropColumn":
            out.append(f"ALTER TABLE {q(ch.get('tableName'))} DROP COLUMN {ch.get('columnName')}")
        elif ct == "createIndex":
            cols = ", ".join(c.get("name") for c in ch if _local(c.tag) == "column")
            out.append(f"CREATE INDEX {q(ch.get('indexName'))} ON {q(ch.get('tableName'))} ({cols})")
        elif ct == "createSequence":
            out.append(f"CREATE SEQUENCE {q(ch.get('sequenceName'))}")
        elif ct == "createView":
            out.append(f"CREATE OR REPLACE VIEW {q(ch.get('viewName'))} AS {(ch.text or '').strip()}")
        elif ct == "dropTable":
            out.append(f"DROP TABLE {q(ch.get('tableName'))}")
        elif ct == "dropIndex":
            out.append(f"DROP INDEX {q(ch.get('indexName'))}")
        elif ct in ("addForeignKeyConstraint",):
            out.append(f"ALTER TABLE {ch.get('baseTableSchemaName') + '.' if ch.get('baseTableSchemaName') else ''}"
                       f"{ch.get('baseTableName')} ADD CONSTRAINT {ch.get('constraintName')} FOREIGN KEY "
                       f"({ch.get('baseColumnNames')}) REFERENCES {ch.get('referencedTableName')} "
                       f"({ch.get('referencedColumnNames')})")
        elif ct in ("addPrimaryKey", "addUniqueConstraint"):
            kind = "PRIMARY KEY" if ct == "addPrimaryKey" else "UNIQUE"
            out.append(f"ALTER TABLE {q(ch.get('tableName'))} ADD CONSTRAINT "
                       f"{ch.get('constraintName')} {kind} ({ch.get('columnNames')})")
        elif ct in ("sql", "createProcedure"):
            out.append((ch.text or "").strip())
    return out
