"""Liquibase changelog validation (XML + formatted SQL), fully offline.

Checks: well-formedness, header, id/author presence, duplicate changeSets, id pattern and
sequence, author format, PL/SQL delimiter safety, DDL/DML mixing, change types,
one-change-per-changeSet.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import List

from core import models as M
from core.lexer import strip_comments
from parsers.liquibase_parser import ChangelogFile

KNOWN_XML_CHANGES = set("""addAutoIncrement addColumn addDefaultValue addForeignKeyConstraint addLookupTable
addNotNullConstraint addPrimaryKey addUniqueConstraint alterSequence createIndex createProcedure createSequence
createTable createView customChange delete dropAllForeignKeyConstraints dropColumn dropDefaultValue
dropForeignKeyConstraint dropIndex dropNotNullConstraint dropPrimaryKey dropProcedure dropSequence dropTable
dropUniqueConstraint dropView empty executeCommand insert loadData loadUpdateData mergeColumns modifyDataType output
renameColumn renameSequence renameTable renameView setColumnRemarks setTableRemarks sql sqlFile stop tagDatabase update
createFunction dropFunction createPackage createPackageBody createTrigger dropTrigger addCheckConstraint
dropCheckConstraint enableCheckConstraint disableCheckConstraint enableTrigger disableTrigger createSynonym dropSynonym""".split())
PRO_ONLY = {"createFunction", "dropFunction", "createPackage", "createPackageBody", "createTrigger", "dropTrigger",
            "addCheckConstraint", "dropCheckConstraint", "enableCheckConstraint", "disableCheckConstraint",
            "enableTrigger", "disableTrigger", "createSynonym", "dropSynonym"}
DML_CHANGES = {"insert", "update", "delete", "loadData", "loadUpdateData"}
PLSQL_HEAD = re.compile(r"^\s*(CREATE\s+(OR\s+REPLACE\s+)?((NON)?EDITIONABLE\s+)?(TRIGGER|PROCEDURE|FUNCTION|PACKAGE|TYPE\s+BODY)"
                        r"|DECLARE\b|BEGIN\b)", re.I | re.M)
DDL_RE = re.compile(r"^\s*(CREATE|ALTER|DROP|TRUNCATE|RENAME|COMMENT\s+ON|GRANT|REVOKE)\b", re.I | re.M)
DML_RE = re.compile(r"^\s*(INSERT|UPDATE|DELETE|MERGE)\b", re.I | re.M)


def validate(files: List[ChangelogFile], profile: dict, tracker_table: str = "") -> List[M.Finding]:
    f: List[M.Finding] = []
    seen = defaultdict(list)
    nm = profile.get("naming", {})
    id_re = re.compile(nm["changeset_id_regex"]) if nm.get("changeset_id_regex") else None
    author_re = re.compile(nm["author_regex"]) if nm.get("author_regex") else None
    tt = (tracker_table or "").upper()
    for cf in files:
        for e in cf.errors:
            f.append(M.Finding("HIGH", "LB_FILE", e, "", "liquibase", cf.path))
        for cs in cf.changesets:
            loc = f"{cf.path}:{cs.line}" if cs.line else f"{cf.path}#{cs.id}"
            add = lambda sev, code, msg, rec="": f.append(M.Finding(sev, code, msg, rec, "liquibase", loc))
            if not cs.id:
                add("HIGH", "LB_NO_ID", "changeSet without id.")
            if not cs.author:
                add("HIGH", "LB_NO_AUTHOR", "changeSet without author.")
            seen[(cs.author, cs.id)].append(cf.path)
            base_id = re.sub(r"-(pre|post|bkp)$", "", cs.id)
            if base_id.startswith(profile.get("rollback_id_prefix", "RB.")):
                base_id = base_id[len(profile.get("rollback_id_prefix", "RB.")):]
            if id_re and not id_re.match(base_id) and cs.id and not cs.id.endswith("-tag"):
                add("LOW", "LB_ID_PATTERN", f"changeSet id '{cs.id}' does not match the id convention {id_re.pattern}.")
            if author_re and cs.author and not author_re.match(cs.author):
                add("MEDIUM", "AUTHOR_FORMAT", f"Author '{cs.author}' does not match {author_re.pattern}.")
            if cf.fmt == "sql":
                _check_sql_changeset(cs, add, tt, profile)
            else:
                _check_xml_changeset(cs, add)
    for (author, cid), paths in seen.items():
        if len(paths) > 1:
            same = len(set(paths)) < len(paths)
            f.append(M.Finding("HIGH" if same else "MEDIUM", "LB_DUPLICATE",
                               f"Duplicate changeSet {author}:{cid} in {', '.join(sorted(set(paths)))}" +
                               (" (same file - Liquibase will refuse to run)" if same else
                                " (different files - identity includes path, but this is almost always a copy/paste error)"),
                               "Give every changeSet a unique id.", "liquibase"))
    f.extend(_check_sequence(files, profile))
    return f


def _check_sql_changeset(cs, add, tt, profile):
    body = cs.sql
    clean = strip_comments(body)
    attrs = {k.lower(): v for k, v in cs.attrs.items()}
    split_off = attrs.get("splitstatements", "true").lower() == "false"
    end_delim = attrs.get("enddelimiter")
    if PLSQL_HEAD.search(clean):
        if not split_off and not end_delim:
            add("HIGH", "LB_PLSQL_SPLIT", f"changeSet {cs.id} contains PL/SQL but neither splitStatements:false nor "
                "endDelimiter is set - Liquibase will split the block on ';' and create an INVALID object.",
                'Add splitStatements:false (or endDelimiter:"/") to the --changeset line.')
        if end_delim and end_delim.strip('"') == "/":
            stripped = re.sub(r"'(?:[^']|'')*'", "''", clean)
            if re.search(r"[^\s/*]\s*/\s*[^\s/*]", stripped.replace("\n/\n", "\n")):
                add("MEDIUM", "LB_DELIM_IN_BODY", f"changeSet {cs.id} uses endDelimiter:\"/\" and the body contains a '/' "
                    "(division?) that Liquibase will treat as a statement terminator.",
                    'Use endDelimiter:"\\n/" or splitStatements:false.')
    ddl = bool(DDL_RE.search(clean))
    dml_stmts = [m for m in DML_RE.finditer(clean)]
    dml_non_tracker = [m for m in dml_stmts if not tt or tt not in clean[m.start():m.start() + 300].upper()]
    if PLSQL_HEAD.search(clean):
        dml_non_tracker = []
    if ddl and dml_non_tracker and not cs.id.startswith(profile.get("rollback_id_prefix", "RB.")):
        add("MEDIUM", "LB_DDL_DML_MIX", f"changeSet {cs.id} mixes DDL and DML. Oracle DDL auto-commits, so a failure "
            "leaves the changeSet half-applied and not re-runnable.", "Split DML into its own changeSet.")
    if ddl and tt and tt in clean.upper():
        add("LOW", "LB_TRACKER_IN_DDL", f"changeSet {cs.id} mixes tracker bookkeeping with DDL; if the DDL fails the "
            "tracker row stays PENDING and the changeSet is not re-runnable.", "Use separate -pre / -post changeSets.")
    n_ddl = len(DDL_RE.findall(clean)) if not PLSQL_HEAD.search(clean) else 1
    if n_ddl > 1 and not profile.get("allow_grouped_ddl", False):
        add("LOW", "LB_MULTI_CHANGE", f"changeSet {cs.id} contains {n_ddl} DDL statements - Liquibase best practice is one "
            "logical change per changeSet.", "Split into separate changeSets (or set allow_grouped_ddl in the profile).")
    if not body.strip():
        add("MEDIUM", "LB_EMPTY", f"changeSet {cs.id} has no SQL.")


def _check_xml_changeset(cs, add):
    for ct in cs.change_types:
        if ct not in KNOWN_XML_CHANGES:
            add("HIGH", "LB_UNKNOWN_CHANGE", f"Unknown change type <{ct}> in {cs.id}.")
        elif ct in PRO_ONLY:
            add("LOW", "LB_PRO_CHANGE", f"<{ct}> requires Liquibase Pro.", "Use <sql> for Liquibase OSS.")
    real = [c for c in cs.change_types if c not in ("tagDatabase", "output", "empty")]
    if len(real) > 1:
        add("LOW", "LB_MULTI_CHANGE", f"changeSet {cs.id} contains {len(real)} changes ({', '.join(real)}).",
            "One logical change per changeSet.")
    plsql = bool(PLSQL_HEAD.search(strip_comments(cs.sql or "")))
    has_dml = any(c in DML_CHANGES for c in real) or (not plsql and bool(DML_RE.search(strip_comments(cs.sql or ""))))
    has_ddl = any(c not in DML_CHANGES and c != "sql" for c in real) or bool(DDL_RE.search(strip_comments(cs.sql or "")))
    if has_dml and has_ddl:
        add("MEDIUM", "LB_DDL_DML_MIX", f"changeSet {cs.id} mixes DDL and DML.", "Separate DDL and DML changeSets.")
    el = cs.xml_element
    if el is not None:
        for ch in el:
            tag = ch.tag.split("}")[-1]
            if tag == "createTable" and not any(c.tag.split("}")[-1] == "column" for c in ch):
                add("HIGH", "LB_TABLE_NO_COLUMNS", f"<createTable> in {cs.id} has no columns.")
            if tag in ("createTable", "addColumn"):
                for c in ch:
                    if c.tag.split("}")[-1] == "column" and not c.get("type"):
                        add("HIGH", "LB_COLUMN_NO_TYPE", f"Column {c.get('name')} in {cs.id} has no type.")
            if tag == "sql" and PLSQL_HEAD.search(ch.text or "") and ch.get("splitStatements", "true") != "false" \
                    and not ch.get("endDelimiter"):
                add("HIGH", "LB_PLSQL_SPLIT", f"<sql> in {cs.id} contains PL/SQL without splitStatements=\"false\".")


def _check_sequence(files: List[ChangelogFile], profile: dict) -> List[M.Finding]:
    """Ids ending in a number must be sequential within a prefix (e.g. SOL_SERVICES.1.34.1.0.N)."""
    f = []
    groups = defaultdict(list)
    rbp = profile.get("rollback_id_prefix", "RB.")
    for cf in files:
        for cs in cf.changesets:
            cid = re.sub(r"-(pre|post|bkp)$", "", cs.id)
            if cid.startswith(rbp) or cid.endswith("-tag"):
                continue
            m = re.match(r"^(.*?)(\d+)$", cid)
            if m:
                groups[m.group(1)].append((int(m.group(2)), cs, cf.path))
    for prefix, items in groups.items():
        nums = []
        for n, cs, p in items:
            if not nums or nums[-1] != n:
                nums.append(n)
        if nums != sorted(nums):
            f.append(M.Finding("MEDIUM", "LB_ID_ORDER", f"changeSet ids with prefix '{prefix}' are out of order: {nums[:15]}",
                               "Keep ids increasing in execution order.", "liquibase"))
        s = sorted(set(nums))
        gaps = [x for x in range(s[0], s[-1] + 1) if x not in s] if s else []
        if gaps:
            f.append(M.Finding("LOW", "LB_ID_GAP", f"Gaps in sequence '{prefix}N': missing {gaps[:10]}", "", "liquibase"))
    return f
