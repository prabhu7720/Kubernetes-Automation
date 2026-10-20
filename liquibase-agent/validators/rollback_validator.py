"""Rollback coverage validation for generated output and for existing changelogs."""
from __future__ import annotations

import re
from typing import List

from core import models as M
from parsers.liquibase_parser import ChangelogFile

AUTO_ROLLBACK_XML = {"createTable", "addColumn", "createIndex", "createSequence", "createView", "renameColumn",
                     "renameTable", "renameView", "addForeignKeyConstraint", "addPrimaryKey", "addUniqueConstraint",
                     "addNotNullConstraint", "dropNotNullConstraint", "addDefaultValue", "tagDatabase",
                     "setTableRemarks", "setColumnRemarks", "addLookupTable", "addAutoIncrement", "createProcedure"}
DESTRUCTIVE = {"dropTable", "dropColumn", "dropIndex", "dropSequence", "dropView", "dropForeignKeyConstraint",
               "dropPrimaryKey", "dropUniqueConstraint", "delete", "update", "sql", "sqlFile", "modifyDataType",
               "dropProcedure", "mergeColumns", "dropDefaultValue"}


def validate_generated(meta: List[dict], fmt: str) -> List[M.Finding]:
    f = []
    for m in meta:
        loc = m.get("file") or m["id"]
        if not m.get("rollback_complete", True):
            notes = "; ".join(dict.fromkeys(m.get("notes", []) or (m["op"] and []) or []))
            f.append(M.Finding("HIGH", "RB_INCOMPLETE", f"[{fmt}] changeSet {m['id']}: rollback is incomplete / manual. {notes}",
                               "Complete the ROLLBACK-MANUAL / TODO section before release (supply --baseline to automate).",
                               "rollback", loc))
        if fmt == "xml" and not m.get("has_rollback"):
            f.append(M.Finding("HIGH", "RB_MISSING", f"changeSet {m['id']} has no rollback.", "", "rollback", loc))
    return f


def validate_existing(files: List[ChangelogFile], tracker_table: str = "") -> List[M.Finding]:
    f = []
    tt = (tracker_table or "").upper()
    for cf in files:
        for cs in cf.changesets:
            loc = f"{cf.path}:{cs.line}" if cs.line else f"{cf.path}#{cs.id}"
            if cs.has_rollback:
                if cs.rollback_empty:
                    f.append(M.Finding("INFO", "RB_EMPTY", f"changeSet {cs.id} declares an empty rollback.", "", "rollback", loc))
                continue
            if cf.fmt == "xml":
                kinds = set(cs.change_types)
                if kinds and kinds <= AUTO_ROLLBACK_XML:
                    continue
                destructive = kinds & DESTRUCTIVE
                f.append(M.Finding("HIGH" if destructive else "MEDIUM", "RB_MISSING",
                                   f"changeSet {cs.id} ({', '.join(sorted(kinds))}) has no <rollback> and Liquibase cannot "
                                   "auto-generate one.", "Add an explicit <rollback> block.", "rollback", loc))
            else:
                body = cs.sql.upper()
                is_tracker = tt and tt in body and not re.search(r"^\s*(CREATE|ALTER|DROP)\b", body, re.M)
                sev = "LOW" if is_tracker else ("HIGH" if re.search(r"\bDROP\b|\bDELETE\b|\bTRUNCATE\b", body) else "MEDIUM")
                f.append(M.Finding(sev, "RB_MISSING", f"changeSet {cs.id} has no --rollback (formatted SQL never "
                                   "auto-generates rollbacks; `liquibase rollback` will fail here)." +
                                   (" Tracker bookkeeping changeSet." if is_tracker else ""),
                                   "Add --rollback statements (or an explicit no-op such as '--rollback SELECT 1 FROM DUAL;').", "rollback", loc))
    return f
