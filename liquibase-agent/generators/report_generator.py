"""Markdown + JSON report: the 6 mandatory sections plus pre/post-check SQL."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from typing import List

from core import models as M

SEV_ICON = {"CRITICAL": "🟥 CRITICAL", "HIGH": "🟧 HIGH", "MEDIUM": "🟨 MEDIUM", "LOW": "🟦 LOW", "INFO": "⬜ INFO"}


def _status(findings: List[M.Finding], cats, codes=None, fail_at="HIGH", inputs=False):
    sel = [f for f in findings if f.category in cats and (codes is None or f.code in codes)
           and f.message.startswith("[input changelog]") == inputs]
    if not sel:
        return "PASS", sel
    worst = max(M.SEVERITY_ORDER[f.severity] for f in sel)
    if worst >= M.SEVERITY_ORDER[fail_at]:
        return "FAIL", sel
    if worst >= M.SEVERITY_ORDER["LOW"]:
        return "WARN", sel
    return "PASS", sel


def _md_escape(s: str) -> str:
    return (s or "").replace("|", "\\|").replace("\n", " ")


def deployment_notes(res) -> List[str]:
    p, d = res.profile, res.dialect
    kinds = Counter(o.kind for o in res.ops)
    codes = {f.code for f in res.findings}
    schemas = sorted({o.schema for o in res.ops if o.schema})
    notes = []
    tag = res.namer.fmt(p.get("tag_pattern", "{project}_{release}_pre"))
    xmlf = res.xml_file or "db.changelog-<release>.xml"
    notes.append("**Execution order** - deploy changeSets strictly in the generated order (ids are sequential; source "
                 "order is preserved and checked for dependency problems - see ORDER_DEPENDENCY findings).")
    notes.append("**Dry run first (no DB changes):** `liquibase --changelog-file=" + xmlf + " validate` then "
                 "`liquibase update-sql > update_preview.sql` and review the exact SQL.")
    notes.append(f"**Tag before deploy:** `liquibase tag --tag={tag}` (the XML changelog also contains a tagDatabase "
                 "changeSet) so `liquibase rollback --tag=" + tag + "` is possible.")
    notes.append("**Preview rollback:** `liquibase rollback-sql --tag=" + tag + "` must produce SQL with no TODO/MANUAL markers.")
    if res.sql_files:
        notes.append("**House formatted-SQL package:** run deploy scripts in file-number order, then confirm all tracker rows "
                     f"in `{p.get('tracker', {}).get('table', 'tracker')}` are COMPLETED. Rollback package: run the `*_ROLLBACK.sql` "
                     "script (forward execution) or `liquibase rollback` (inline --rollback).")
    lock_codes = {"INDEX_LOCK", "FK_VALIDATION", "SET_NOT_NULL", "ORA_DROP_COLUMN_REWRITE", "PG_TYPE_REWRITE", "UNIQUE_ON_EXISTING",
                  "TYPE_CHANGE", "MYSQL_MODIFY_RESETS", "TRIGGER_OVERHEAD"}
    if codes & lock_codes:
        if d == "oracle":
            notes.append("**Locking:** some DDL touches existing, possibly large tables. Deploy in a low-traffic window and "
                         "set `ALTER SESSION SET DDL_LOCK_TIMEOUT = 60;` (Liquibase: add it as the first changeSet or via "
                         "a session init SQL) so DDL waits for locks instead of failing with ORA-00054.")
        elif d == "postgresql":
            notes.append("**Locking:** set `SET lock_timeout = '5s'` and `statement_timeout` for the deployment session; "
                         "retry on lock timeout rather than queueing behind long transactions.")
        elif d in ("mysql", "mariadb"):
            notes.append("**Locking:** set `lock_wait_timeout` (e.g. 30) and check for long-running transactions "
                         "(information_schema.INNODB_TRX) before running DDL; consider gh-ost/pt-osc for very large tables.")
        else:
            notes.append("**Locking:** set `SET LOCK_TIMEOUT 30000` and prefer ONLINE = ON operations (Enterprise).")
    if "INVALID_WINDOW" in codes or "DEPENDENT_INVALIDATED" in codes:
        notes.append("**Invalidation window:** some code objects are INVALID between a column drop and their re-creation. "
                     "Run the whole release in ONE `liquibase update` with application writes paused.")
    if kinds[M.DROP_COLUMN] or kinds[M.DROP_TABLE] or kinds[M.TRUNCATE_TABLE] or kinds[M.DELETE] or kinds[M.UPDATE]:
        notes.append("**Data loss protection:** confirm a fresh backup (RMAN / expdp / pg_dump / mysqldump) and that the "
                     "generated `-bkp` backup changeSets ran before the destructive change. Keep backup tables until the "
                     "release is signed off, then drop them in a later release.")
        notes.append("**Application compatibility (expand/contract):** release application code that no longer reads/writes "
                     "dropped columns BEFORE this database change.")
    if kinds[M.CREATE_TRIGGER] or kinds[M.CREATE_PROCEDURE] or kinds[M.CREATE_FUNCTION] or kinds[M.CREATE_PACKAGE_BODY] \
            or kinds[M.CREATE_VIEW] or kinds[M.DROP_COLUMN]:
        if d == "oracle":
            sch = schemas[0] if schemas else "<SCHEMA>"
            notes.append(f"**Recompile:** after deploy run `EXEC DBMS_UTILITY.COMPILE_SCHEMA(schema => '{sch}', compile_all => FALSE);` "
                         "and verify the invalid-objects post-check returns no new rows.")
        else:
            notes.append("**Dependent objects:** verify views/routines still compile/execute after the change.")
    if kinds[M.CREATE_INDEX] or kinds[M.ADD_COLUMN] or kinds[M.CREATE_TABLE] or kinds[M.MODIFY_COLUMN]:
        stats = {"oracle": "EXEC DBMS_STATS.GATHER_TABLE_STATS(ownname => '<SCHEMA>', tabname => '<TABLE>', cascade => TRUE);",
                 "postgresql": "ANALYZE <schema>.<table>;", "mysql": "ANALYZE TABLE <schema>.<table>;",
                 "mariadb": "ANALYZE TABLE <schema>.<table>;", "mssql": "UPDATE STATISTICS <schema>.<table>;"}[d]
        notes.append(f"**Optimizer statistics:** refresh stats on altered/indexed existing tables: `{stats}`")
    if "NOLOGGING" in codes:
        notes.append("**NOLOGGING objects:** inform the DBA - take a backup after initial loads; Data Guard standbys need "
                     "the datafiles refreshed if non-logged loads occur (or enable FORCE LOGGING).")
    if kinds[M.GRANT] or kinds[M.CREATE_TABLE]:
        notes.append("**Grants/roles:** confirm target roles exist in every environment (pre-check) - missing roles "
                     "fail the GRANT and halt the deployment.")
    if any(o.kind in M.DML_KINDS for o in res.ops):
        notes.append("**Data migration:** DML is in separate changeSets. Compare the pre/post row counts; for >100k rows "
                     "rewrite as batched PL/SQL / chunked updates to limit undo and lock time.")
    if any(f.code == "REPLACE_UNKNOWN" or f.code == "REPLACE_NO_PREVIOUS" for f in res.findings):
        notes.append("**Replaced objects:** capture current source with the DBMS_METADATA pre-checks and re-run the agent "
                     "with `--baseline` so rollback restores the previous version instead of dropping the object.")
    notes.append("**Offline guarantee:** the agent and Liquibase run locally; Liquibase resolves the dbchangelog XSD from "
                 "its own jar, so no network access is required.")
    notes.extend(p.get("deployment_notes_extra", []))
    return notes


def checklist(res):
    f = res.findings
    rows = []

    def row(name, cats, codes=None, detail_ok="", fail_at="HIGH", inputs=False):
        st, sel = _status(f, cats, codes, fail_at, inputs)
        detail = f"{len(sel)} finding(s)" if sel else (detail_ok or "no findings")
        rows.append((name, st, detail))
    row("SQL syntax", {"syntax"})
    row("Liquibase syntax (generated + supplied changelogs)", {"liquibase"},
        {"LB_FILE", "LB_NO_ID", "LB_NO_AUTHOR", "LB_UNKNOWN_CHANGE", "LB_PLSQL_SPLIT", "LB_TABLE_NO_COLUMNS",
         "LB_COLUMN_NO_TYPE", "LB_EMPTY", "LB_DELIM_IN_BODY", "LB_PRO_CHANGE"}, "well-formed, ids/authors present")
    row("Duplicate changeSets", {"liquibase", "conflict"}, {"LB_DUPLICATE", "DUPLICATE_CREATE"}, "none")
    row("Rollback coverage", {"rollback"}, None, "every changeSet has an explicit rollback")
    row("Naming conventions", {"naming"})
    row("Existing object conflicts", {"conflict"}, None,
        "no conflicts" + ("" if any(True for _ in res.profile.get("_baseline", [])) else " (against supplied baseline)"))
    row("One logical change per changeSet", {"liquibase"}, {"LB_MULTI_CHANGE"}, "XML: enforced by construction")
    row("DDL and DML separated", {"liquibase", "best_practice"}, {"LB_DDL_DML_MIX", "LB_TRACKER_IN_DDL"}, "enforced by construction")
    row("Author naming", {"naming", "liquibase"}, {"AUTHOR_FORMAT"}, f"author = {res.profile.get('author')}")
    row("Sequential IDs", {"liquibase"}, {"LB_ID_ORDER", "LB_ID_GAP", "LB_ID_PATTERN"}, "sequential")
    row("Environment-independent scripts", {"best_practice"}, {"ENV_HARDCODED_SCHEMA", "ENV_HARDCODED_TABLESPACE",
                                                               "ENV_DBLINK", "ENV_SPECIFIC_DATA", "SEQ_HARDCODED_START"})
    if res.input_changelogs:
        row("Supplied Liquibase files (review of the input scripts)", {"liquibase", "rollback"}, None, "no issues", inputs=True)
    return rows


def render_markdown(res, include_xml=True) -> str:
    out = []
    p = res.profile
    risk_f = [f for f in res.findings if f.category in ("risk", "conflict")]
    overall = M.max_severity(risk_f) if risk_f else "INFO"
    cl = checklist(res)
    gate = "FAIL" if any(s == "FAIL" for _, s, _ in cl) else ("WARN" if any(s == "WARN" for _, s, _ in cl) else "PASS")
    out.append(f"# Liquibase Agent Report - {p.get('project', '')} release {res.release}")
    out.append("")
    out.append("| Item | Value |\n|---|---|")
    out.append(f"| Input(s) | {', '.join(res.sources)} |")
    out.append(f"| Dialect | {res.dialect}{' (auto-detected)' if res.dialect_scores else ''} |")
    out.append(f"| Profile / author | {p.get('_name')} / {p.get('author')} |")
    work = [o for o in res.ops if o.kind not in (M.TX_CONTROL, M.TRACKER, M.CLIENT_COMMAND)]
    out.append(f"| Operations analysed | {len(work)} |")
    if res.xml_meta:
        out.append(f"| XML changeSets | {len(res.xml_meta)} ({res.xml_meta[0]['id']} .. {res.xml_meta[-1]['id']}) |")
    if res.sql_meta:
        out.append(f"| Formatted-SQL scripts | {len(res.sql_meta)} ({res.sql_meta[0]['id']} .. {res.sql_meta[-1]['id']}) |")
    out.append(f"| Overall risk | **{overall}** |")
    out.append(f"| Validation gate | **{gate}** |")
    out.append("")

    # 1. change summary
    out.append("## 1. Change Summary")
    out.append("")
    out.append("| # | Operation | Object | What it does | Risk |")
    out.append("|---|---|---|---|---|")
    for r in res.results:
        o = r.op
        if o.kind in (M.TX_CONTROL, M.TRACKER):
            continue
        rs = [x for x in r.findings if x.category in ("risk", "conflict")]
        out.append(f"| {o.seq} | {o.kind} | {_md_escape(o.qualified)} | {_md_escape(r.impact)} | {M.max_severity(rs) if rs else '-'} |")
    out.append("")
    if res.sql_meta:
        out.append("**Deploy scripts (house formatted SQL):**")
        out.append("")
        out.append("| Script | changeSet | Contains |")
        out.append("|---|---|---|")
        for m in res.sql_meta:
            u = m["unit"]
            out.append(f"| `{m['file']}` | {m['id']} | {_md_escape(', '.join(dict.fromkeys(o.kind + ' ' + o.name for o in u.operations)))} |")
        out.append("")

    # 2. Liquibase output
    out.append("## 2. Liquibase XML")
    out.append("")
    if res.xml and include_xml:
        out.append(f"File: `changelog/{res.xml_file}`")
        out.append("")
        out.append("```xml")
        out.append(res.xml.rstrip())
        out.append("```")
    elif res.sql_files:
        out.append("XML output not requested - formatted SQL files generated:")
    if res.sql_files:
        out.append("")
        first = next(iter(res.sql_files.items()))
        out.append(f"Formatted SQL package: {len(res.sql_files)} file(s). First file `{first[0]}`:")
        out.append("")
        out.append("```sql")
        out.append(first[1].rstrip())
        out.append("```")
    out.append("")

    # 3. rollback
    out.append("## 3. Rollback Section")
    out.append("")
    out.append("| # | Object | Rollback | Complete | Notes |")
    out.append("|---|---|---|---|---|")
    for r in res.results:
        o = r.op
        if o.kind in (M.TX_CONTROL, M.TRACKER, M.CLIENT_COMMAND) or not r.rollback:
            continue
        rb = r.rollback
        sql = "<br>".join(_md_escape(s.split("\n")[0] + (" ..." if "\n" in s else "")) for s in rb.sql) or "-"
        pre = ("<br>**backup first:** " + "<br>".join(_md_escape(s) for s in rb.pre_sql)) if rb.pre_sql else ""
        out.append(f"| {o.seq} | {_md_escape(o.qualified)} | `{sql}`{pre} | {'yes' if rb.complete else '**NO**'} | "
                   f"{_md_escape('; '.join(rb.notes))} |")
    out.append("")
    if res.sql_files:
        rbf = [k for k in res.sql_files if "ROLLBACK" in k.upper()]
        if rbf:
            out.append(f"Consolidated rollback script: `{rbf[0]}` (reverse order of all deploy scripts).")
            out.append("")

    # 4. risk
    out.append("## 4. Risk Assessment")
    out.append("")
    out.append(f"Overall risk: **{overall}**")
    out.append("")
    cnt = Counter(f.severity for f in risk_f)
    out.append(" | ".join(f"{s}: {cnt.get(s, 0)}" for s in ("CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO")))
    out.append("")
    out.append("| Severity | Code | Finding | Recommendation | Location |")
    out.append("|---|---|---|---|---|")
    for f in risk_f:
        out.append(f"| {SEV_ICON[f.severity]} | {f.code} | {_md_escape(f.message)} | {_md_escape(f.recommendation)} | {_md_escape(f.location)} |")
    out.append("")

    # 5. deployment notes
    out.append("## 5. Deployment Notes")
    out.append("")
    for n in deployment_notes(res):
        out.append(f"- {n}")
    out.append("")

    # 6. validation checklist
    out.append("## 6. Validation Checklist")
    out.append("")
    out.append("| Check | Status | Detail |")
    out.append("|---|---|---|")
    icon = {"PASS": "✅ PASS", "WARN": "⚠️ WARN", "FAIL": "❌ FAIL"}
    for name, st, det in cl:
        out.append(f"| {name} | {icon[st]} | {det} |")
    out.append("")
    other = [f for f in res.findings if f.category not in ("risk", "conflict")]
    if other:
        out.append("<details><summary>Validation findings</summary>")
        out.append("")
        out.append("| Severity | Category | Code | Finding | Location |")
        out.append("|---|---|---|---|---|")
        for f in other:
            out.append(f"| {f.severity} | {f.category} | {f.code} | {_md_escape(f.message)} | {_md_escape(f.location)} |")
        out.append("")
        out.append("</details>")
        out.append("")

    # 7. checks
    out.append("## 7. Pre-check and Post-check SQL")
    out.append("")
    out.append("Run pre-checks before `liquibase update` and post-checks after. Files: `checks/precheck.sql`, `checks/postcheck.sql`.")
    out.append("")
    out.append("```sql")
    out.append(render_checks(res, "pre").rstrip())
    out.append("```")
    out.append("")
    out.append("```sql")
    out.append(render_checks(res, "post").rstrip())
    out.append("```")
    return "\n".join(out) + "\n"


def render_checks(res, which: str) -> str:
    out = [f"-- {'PRE' if which == 'pre' else 'POST'}-DEPLOYMENT CHECKS - release {res.release} ({res.dialect})",
           "-- Read-only queries. Compare each result with the expected value.", ""]
    rel = res.release_checks.get(which, [])
    label = res.namer.fmt(res.profile.get("tracker", {}).get("release_label", "{project} {release}")) if res.namer else ""
    if which == "pre":
        for c in rel:
            out.append(f"-- [release] {c['purpose']} | expected: {c['expect']}")
            out.append(c["sql"].replace("{release_label}", label) + ";")
            out.append("")
    for r in res.results:
        cs = r.checks.get(which) if r.checks else None
        if not cs:
            continue
        out.append(f"-- ---- step {r.op.seq}: {r.op.kind} {r.op.qualified}")
        for c in cs:
            if not c["sql"]:
                continue
            exp = f" | expected: {c['expect']}" if c["expect"] else ""
            out.append(f"-- {c['purpose']}{exp}")
            out.append(c["sql"] if c["sql"].startswith("--") else c["sql"] + ";")
        out.append("")
    if which == "post":
        for c in rel:
            out.append(f"-- [release] {c['purpose']} | expected: {c['expect']}")
            out.append(c["sql"].replace("{release_label}", label) + ";")
            out.append("")
    return "\n".join(out) + "\n"


def render_json(res) -> str:
    data = {
        "release": res.release, "dialect": res.dialect, "profile": res.profile.get("_name"), "sources": res.sources,
        "overall_risk": M.max_severity([f for f in res.findings if f.category in ("risk", "conflict")]),
        "checklist": [{"check": n, "status": s, "detail": d} for n, s, d in checklist(res)],
        "operations": [{"seq": r.op.seq, "kind": r.op.kind, "object": r.op.qualified, "impact": r.impact,
                        "rollback_complete": r.rollback.complete if r.rollback else None,
                        "rollback_sql": r.rollback.sql if r.rollback else [],
                        "source": f"{r.op.statement.source}:{r.op.statement.line_start}"}
                       for r in res.results if r.op.kind not in (M.TX_CONTROL, M.TRACKER)],
        "changesets_xml": [{"id": m["id"], "comment": m["comment"], "rollback_complete": m["rollback_complete"]} for m in res.xml_meta],
        "scripts_sql": [{"id": m["id"], "file": m["file"], "rollback_complete": m["rollback_complete"]} for m in res.sql_meta],
        "findings": [f.as_dict() for f in res.findings],
    }
    return json.dumps(data, indent=2)
