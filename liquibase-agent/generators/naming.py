"""Changeset id / file / folder naming driven by the profile."""
from __future__ import annotations

import re
from typing import List

from core import models as M

SUFFIX = {"TABLE": "DDL", "ALTER": "ALTER_DDL", "INDEX": "IDX_DDL", "VIEW": "VW_DDL", "TRIGGER": "TRIG_DDL",
          "ROUTINE": "PROC_DDL", "SEQUENCE": "SEQ_DDL", "DML": "DML", "DROP": "DROP_DDL", "GRANT": "GRANTS_DDL",
          "COMMENT": "COMMENTS_DDL", "OTHER": "DDL"}


class Namer:
    def __init__(self, profile: dict, release: str):
        self.p = profile
        self.release = release or profile.get("release", "1.0")
        self.app = profile.get("app", "APP")
        self.project = profile.get("project", "PROJECT")

    def fmt(self, pattern: str, **kw) -> str:
        base = dict(project=self.project, release=self.release, app=self.app, app_lower=self.app.lower(),
                    release_tag=f"{self.release.replace('.', '_')}", author=self.p.get("author", "agent"))
        base.update(kw)
        return pattern.format(**base)

    def changeset_id(self, seq: int) -> str:
        return self.fmt(self.p.get("changeset_id_pattern", "{seq:03d}"), seq=seq)

    def rollback_id(self, cid: str) -> str:
        return self.p.get("rollback_id_prefix", "RB.") + cid

    def label(self, unit: M.ChangeUnit) -> str:
        lab = (unit.label or "OBJECT").upper().replace('"', "")
        if unit.unit_type == "TRIGGER":
            lab = re.sub(r"^(TRG_|TRG|TR_|T_)", "", lab)
            lab = re.sub(r"(_TRG|_TRIG)$", "", lab)
        if unit.unit_type == "VIEW" and lab.endswith(("_VW", "_V", "_VIEW")):
            return lab
        if unit.unit_type == "ALTER":
            kinds = {o.kind for o in unit.operations}
            if kinds == {M.DROP_COLUMN}:
                lab += "_DROP_COLUMNS"
            elif kinds == {M.ADD_COLUMN}:
                lab += "_ADD_COLUMNS"
            elif kinds == {M.MODIFY_COLUMN}:
                lab += "_MODIFY_COLUMNS"
        if unit.unit_type == "TABLE" and any(o.kind == M.CREATE_INDEX for o in unit.operations) and False:
            lab += "_TABLE"
        return lab

    def suffix(self, unit: M.ChangeUnit) -> str:
        sfx = dict(SUFFIX, **self.p.get("file_suffixes", {}))
        s = sfx.get(unit.unit_type, "DDL")
        if unit.unit_type == "VIEW" and unit.label.upper().endswith(("_VW", "_V", "_VIEW")):
            s = "DDL"
        if unit.unit_type == "TRIGGER" and unit.replaces_existing:
            s = sfx.get("TRIGGER_REPLACE", "TRIG_ALTER_DDL")
        if unit.unit_type == "ROUTINE":
            k = unit.operations[0].kind
            s = {M.CREATE_FUNCTION: "FUNC_DDL", M.CREATE_PACKAGE: "PKG_DDL", M.CREATE_PACKAGE_BODY: "PKG_BODY_DDL"}.get(k, s)
        return s

    def file_name(self, unit: M.ChangeUnit, seq: int) -> str:
        schema = (unit.schema or self.p.get("default_schema") or "SCHEMA").upper()
        return self.fmt(self.p.get("file_name_pattern", "{seq:02d}_{app}_{schema}_{object}_{suffix}.sql"),
                        seq=seq, schema=schema, object=self.label(unit), suffix=self.suffix(unit))

    def rollback_file_name(self, schema: str, seq: int = 91) -> str:
        return self.fmt(self.p.get("rollback_file_pattern", "{rb_seq}_{app}_{schema}_{release_tag}_ROLLBACK.sql"),
                        rb_seq=seq, schema=(schema or "SCHEMA").upper())

    def deploy_dir(self) -> str:
        return self.fmt(self.p.get("deploy_dir_pattern", "{app_lower}_{release}_deploy"))

    def rollback_dir(self) -> str:
        return self.fmt(self.p.get("rollback_dir_pattern", "{app_lower}_{release}_Rollback"))

    def xml_file_name(self) -> str:
        return self.fmt(self.p.get("xml_file_pattern", "db.changelog-{release}.xml"))
