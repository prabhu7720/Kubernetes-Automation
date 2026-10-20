"""Group operations into ChangeUnits.

mode='statement' : one logical change per changeSet (XML default, strict best practice)
mode='object'    : one deploy script per object (house formatted-SQL style):
                   table + its sequence/indexes/comments/grants, consecutive ALTERs on a
                   table, index batches on existing tables, one view/trigger/routine each,
                   DML always separated from DDL.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from core import models as M

SKIP = {M.TX_CONTROL, M.TRACKER, M.CLIENT_COMMAND}
ALTER_KINDS = {M.ADD_COLUMN, M.MODIFY_COLUMN, M.DROP_COLUMN, M.RENAME_COLUMN, M.ADD_CONSTRAINT,
               M.DROP_CONSTRAINT, M.ALTER_TABLE_RAW, M.RENAME_TABLE}
DROP_KINDS = {M.DROP_TABLE, M.DROP_INDEX, M.DROP_VIEW, M.DROP_SEQUENCE, M.DROP_TRIGGER, M.DROP_ROUTINE,
              M.TRUNCATE_TABLE}
ROUTINE_KINDS = {M.CREATE_PROCEDURE, M.CREATE_FUNCTION, M.CREATE_PACKAGE, M.CREATE_PACKAGE_BODY}


def _u(x):
    return (x or "").upper()


def sequence_table(seq_name: str, tables: List[str]) -> Optional[str]:
    """Map a sequence to its table: exact (SEQ_<T>_ID, <T>_SEQ) or abbreviated token match
    (SEQ_SHADOW_PROD_ORDER_AUD_ID -> SHADOW_PRODUCT_ORDER_AUDIT)."""
    s = _u(seq_name)
    core = re.sub(r"^(SEQ_|SQ_|S_)", "", s)
    core = re.sub(r"(_SEQ|_SQ|_ID_SEQ)$", "", core)
    core2 = re.sub(r"_ID$", "", core)
    for t in sorted(tables, key=len, reverse=True):
        if _u(t) in (core, core2):
            return t
    stoks = [x for x in core2.split("_") if x]
    best = None
    for t in tables:
        ttoks = _u(t).split("_")
        if len(stoks) != len(ttoks):
            continue
        if all(tt.startswith(st) for st, tt in zip(stoks, ttoks)):
            if best is None or len(t) > len(best):
                best = t
    return best


def unit_type_of(op: M.Operation) -> str:
    k = op.kind
    if k in (M.CREATE_TABLE, M.CREATE_TABLE_AS):
        return "TABLE"
    if k in ALTER_KINDS:
        return "ALTER"
    if k == M.CREATE_INDEX:
        return "INDEX"
    if k == M.CREATE_VIEW:
        return "VIEW"
    if k == M.CREATE_TRIGGER:
        return "TRIGGER"
    if k in ROUTINE_KINDS:
        return "ROUTINE"
    if k in (M.CREATE_SEQUENCE, M.ALTER_SEQUENCE):
        return "SEQUENCE"
    if k in M.DML_KINDS:
        return "DML"
    if k in DROP_KINDS:
        return "DROP"
    if k in (M.GRANT, M.REVOKE):
        return "GRANT"
    if k == M.COMMENT:
        return "COMMENT"
    return "OTHER"


def group(ops: List[M.Operation], mode: str = "object") -> List[M.ChangeUnit]:
    ops = [o for o in ops if o.kind not in SKIP]
    if mode == "statement":
        return _group_statement(ops)
    return _group_object(ops)


def _group_statement(ops):
    units: List[M.ChangeUnit] = []
    new_tables = {_u(o.qualified) for o in ops if o.kind == M.CREATE_TABLE}
    table_units: Dict[str, M.ChangeUnit] = {}
    grant_units: Dict[str, M.ChangeUnit] = {}
    for op in ops:
        # merge COMMENT on a new table into the createTable remarks
        if op.kind == M.COMMENT and _u(op.qualified_table) in table_units and op.details.get("target") in ("TABLE", "COLUMN"):
            table_units[_u(op.qualified_table)].operations.append(op)
            continue
        if op.kind in (M.GRANT, M.REVOKE):
            key = f"{op.kind}:{_u(op.qualified)}"
            if key in grant_units and grant_units[key] is units[-1]:
                units[-1].operations.append(op)
                continue
            u = M.ChangeUnit([op], "GRANT", op.name, op.schema)
            grant_units[key] = u
            units.append(u)
            continue
        u = M.ChangeUnit([op], unit_type_of(op), op.table or op.name, op.schema)
        units.append(u)
        if op.kind == M.CREATE_TABLE and _u(op.qualified) in new_tables:
            table_units[_u(op.qualified)] = u
    return units


def _group_object(ops):
    tables_new = [o.name for o in ops if o.kind in (M.CREATE_TABLE, M.CREATE_TABLE_AS)]
    new_keys = {_u(o.qualified) for o in ops if o.kind in (M.CREATE_TABLE, M.CREATE_TABLE_AS)}
    seq_owner = {}
    for o in ops:
        if o.kind == M.CREATE_SEQUENCE:
            t = sequence_table(o.name, tables_new)
            if t:
                seq_owner[_u(o.qualified)] = t
    units: List[M.ChangeUnit] = []
    table_unit: Dict[str, M.ChangeUnit] = {}   # table name (upper) -> unit
    obj_unit: Dict[str, M.ChangeUnit] = {}     # view/routine/sequence qualified -> unit
    pending_seq: Dict[str, List[M.Operation]] = {}
    last: Optional[M.ChangeUnit] = None
    altered = set()

    def new_unit(op, utype, label):
        nonlocal last
        u = M.ChangeUnit([op], utype, label, op.schema)
        units.append(u)
        last = u
        return u

    for op in ops:
        tname = _u(op.table or op.name)
        q = _u(op.qualified)
        # sequences belonging to a new table travel with that table
        if op.kind == M.CREATE_SEQUENCE and q in seq_owner:
            owner = _u(seq_owner[q])
            if owner in table_unit:
                table_unit[owner].operations.append(op)
            else:
                pending_seq.setdefault(owner, []).append(op)
            obj_unit[q] = table_unit.get(owner) or M.ChangeUnit([], "TABLE", owner, op.schema)
            continue
        if op.kind in (M.GRANT, M.REVOKE, M.COMMENT) and q in seq_owner and _u(seq_owner[q]) not in table_unit:
            pending_seq.setdefault(_u(seq_owner[q]), []).append(op)
            continue
        if op.kind in (M.CREATE_TABLE, M.CREATE_TABLE_AS):
            u = new_unit(op, "TABLE", op.name)
            pre = pending_seq.pop(tname, [])
            u.operations = pre + u.operations
            table_unit[tname] = u
            for s in pre:
                obj_unit[_u(s.qualified)] = u
            continue
        if op.kind == M.CREATE_INDEX and op.details.get("concurrently"):
            new_unit(op, "INDEX", op.table)
            last = None
            continue
        # attach dependants of a new table
        if op.kind in (M.COMMENT, M.GRANT, M.REVOKE) and tname in table_unit:
            table_unit[tname].operations.append(op)
            continue
        if op.kind in (M.CREATE_INDEX, M.ADD_CONSTRAINT) and tname in table_unit and tname not in altered:
            table_unit[tname].operations.append(op)
            continue
        if op.kind in (M.GRANT, M.REVOKE, M.COMMENT) and q in obj_unit and obj_unit[q].operations:
            obj_unit[q].operations.append(op)
            continue
        ut = unit_type_of(op)
        if ut in ("ALTER", "DML", "DROP"):
            altered.add(tname)
        if ut == "ALTER":
            if last and last.unit_type == "ALTER" and _u(last.label) == tname:
                last.operations.append(op)
                continue
            new_unit(op, "ALTER", op.table or op.name)
            continue
        if ut == "INDEX":
            if last and last.unit_type == "INDEX":
                last.operations.append(op)
                tabs = {_u(o.table) for o in last.operations}
                if len(tabs) == 1:
                    last.label = last.operations[0].table
                else:
                    fkish = all(all(c["name"].upper().endswith("_ID") for c in o.details.get("columns", []))
                                for o in last.operations)
                    last.label = "FK" if fkish else "MULTI_TABLE"
                continue
            new_unit(op, "INDEX", op.table)
            continue
        if ut in ("VIEW", "TRIGGER", "ROUTINE"):
            u = new_unit(op, ut, op.name)
            obj_unit[q] = u
            continue
        if ut == "SEQUENCE":
            if last and last.unit_type == "SEQUENCE":
                last.operations.append(op)
                last.label = "SEQUENCES"
            else:
                new_unit(op, "SEQUENCE", op.name)
            obj_unit[q] = last
            continue
        if ut == "DML":
            if last and last.unit_type == "DML" and _u(last.label) == tname:
                last.operations.append(op)
                continue
            new_unit(op, "DML", op.table or op.name)
            continue
        if ut in ("DROP", "GRANT", "COMMENT", "OTHER"):
            if last and last.unit_type == ut and ut != "OTHER":
                last.operations.append(op)
                if _u(last.label) != tname:
                    last.label = {"DROP": "OBJECTS", "GRANT": "GRANTS", "COMMENT": "COMMENTS"}[ut]
                continue
            new_unit(op, ut, op.table or op.name)
            continue
    # orphan sequences whose table never appeared go first (nothing can depend on them earlier)
    orphans = [M.ChangeUnit([s], "SEQUENCE", s.name, s.schema) for seqs in pending_seq.values() for s in seqs]
    return orphans + units
