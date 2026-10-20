#!/usr/bin/env python3
"""
Offline Liquibase Automation Agent
==================================
Rule-based (no AI / no network) analysis of SQL scripts and generation of production-ready
Liquibase changelogs for Oracle, PostgreSQL, MySQL, MariaDB and SQL Server.

  python agent.py analyze  -i release_scripts/ --profile sol_services --release 1.35 -o out/
  python agent.py analyze  --sql "CREATE TABLE employee (employee_id NUMBER PRIMARY KEY);" --print
  python agent.py validate -i vibehub_1.34_deploy/ vibehub_1.34_Rollback/ --profile sol_services
  python agent.py profiles

Exit codes: 0 ok, 1 usage/input error, 2 validation gate failed (--fail-on threshold reached).
"""
from __future__ import annotations

import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from core import models as M  # noqa: E402
from core.config import load_profile, CONFIG_DIR  # noqa: E402
from core.engine import LiquibaseAgent  # noqa: E402
from generators.report_generator import render_markdown, render_json, render_checks, checklist  # noqa: E402
from parsers import liquibase_parser as LP  # noqa: E402
from validators import liquibase_validator, rollback_validator  # noqa: E402

SEV = ["INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"]


def _write(path, text):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _gate(findings, fail_on):
    if not fail_on or fail_on.upper() == "NONE":
        return False
    lim = M.SEVERITY_ORDER[fail_on.upper()]
    return any(M.SEVERITY_ORDER[f.severity] >= lim for f in findings)


def cmd_analyze(a) -> int:
    profile = load_profile(a.profile)
    agent = LiquibaseAgent(profile, dialect=a.dialect, release=a.release, author=a.author, default_schema=a.schema)
    if a.baseline:
        agent.add_baseline(a.baseline)
    if a.changelog:
        agent.add_existing_changelogs(a.changelog)
    inline = a.sql
    if a.stdin:
        inline = sys.stdin.read()
    formats = {"xml": ("xml",), "sql": ("sql",), "both": ("xml", "sql")}[a.format]
    res = agent.run(a.input or [], formats=formats, start_seq=a.start_seq, inline_sql=inline)
    report = render_markdown(res)
    if not a.no_files:
        out = a.output
        _write(os.path.join(out, "report.md"), report)
        _write(os.path.join(out, "report.json"), render_json(res))
        _write(os.path.join(out, "checks", "precheck.sql"), render_checks(res, "pre"))
        _write(os.path.join(out, "checks", "postcheck.sql"), render_checks(res, "post"))
        if res.xml:
            _write(os.path.join(out, "changelog", res.xml_file), res.xml)
        for name, text in res.sql_files.items():
            _write(os.path.join(out, name), text)
    if a.print:
        print(report)
    else:
        _summary(res, a)
    return 2 if _gate([f for f in res.findings if f.category in ("risk", "conflict", "syntax", "rollback", "liquibase")],
                      a.fail_on) else 0


def _summary(res, a):
    from collections import Counter
    risk = [f for f in res.findings if f.category in ("risk", "conflict")]
    c = Counter(f.severity for f in risk)
    print(f"Liquibase Agent | dialect={res.dialect} | profile={res.profile.get('_name')} | release={res.release}")
    print(f"  operations : {len([o for o in res.ops if o.kind not in (M.TX_CONTROL, M.TRACKER)])}")
    if res.xml_meta:
        print(f"  XML        : {len(res.xml_meta)} changeSets -> {os.path.join(a.output, 'changelog', res.xml_file)}")
    if res.sql_meta:
        print(f"  SQL        : {len(res.sql_files)} files -> {os.path.join(a.output, res.namer.deploy_dir())}")
    print("  risk       : " + ", ".join(f"{s}={c.get(s, 0)}" for s in reversed(SEV)))
    for name, st, det in checklist(res):
        print(f"  [{st:4}] {name} - {det}")
    if not a.no_files:
        print(f"  report     : {os.path.join(a.output, 'report.md')}")


def cmd_validate(a) -> int:
    profile = load_profile(a.profile)
    tt = (profile.get("tracker", {}) or {}).get("table", "")
    files = [LP.parse_changelog(p) for p in LP.collect_changelog_files(a.input)]
    if not files:
        print("No changelog files found.")
        return 1
    findings = liquibase_validator.validate(files, profile, tt) + rollback_validator.validate_existing(files, tt)
    # SQL-level checks of changeSet bodies
    body, dialect = [], a.dialect
    for path in a.input:   # each folder/file is analysed as its own run (deploy vs rollback packages)
        agent = LiquibaseAgent(load_profile(a.profile), dialect=a.dialect)
        res = agent.run([path], formats=())
        dialect = res.dialect
        body += [f for f in res.findings if f.category in ("syntax", "risk", "conflict", "naming", "best_practice")
                 and M.SEVERITY_ORDER[f.severity] >= M.SEVERITY_ORDER["LOW"]]
    allf = sorted(findings + body, key=lambda f: -M.SEVERITY_ORDER[f.severity])
    n_cs = sum(len(f.changesets) for f in files)
    lines = [f"# Liquibase validation report", "", f"Files: {len(files)} | changeSets: {n_cs} | dialect: {dialect}", "",
             "| Severity | Category | Code | Finding | Location |", "|---|---|---|---|---|"]
    for f in allf:
        lines.append(f"| {f.severity} | {f.category} | {f.code} | {f.message.replace('|', '/')} | {f.location} |")
    text = "\n".join(lines) + "\n"
    if a.output:
        _write(os.path.join(a.output, "validation_report.md"), text)
        print(f"Report written to {os.path.join(a.output, 'validation_report.md')}")
    from collections import Counter
    c = Counter(f.severity for f in allf)
    print(f"Validated {len(files)} file(s), {n_cs} changeSet(s): " + ", ".join(f"{s}={c.get(s, 0)}" for s in reversed(SEV)))
    if a.print or not a.output:
        print(text)
    return 2 if _gate(allf, a.fail_on) else 0


def cmd_profiles(a) -> int:
    print("default")
    for f in sorted(os.listdir(os.path.join(CONFIG_DIR, "profiles"))):
        if f.endswith(".json"):
            p = load_profile(f[:-5])
            print(f"{f[:-5]:15} dialect={p.get('dialect') or 'auto':10} author={p.get('author')}  id={p.get('changeset_id_pattern')}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="liquibase-agent", description="Offline rule-based Liquibase automation agent")
    sub = ap.add_subparsers(dest="cmd")

    def common(p):
        p.add_argument("--profile", default="default", help="profile name in config/profiles or path to JSON")
        p.add_argument("--dialect", help="oracle | postgresql | mysql | mariadb | mssql (default: profile or auto-detect)")
        p.add_argument("--fail-on", default="NONE", help="CRITICAL|HIGH|MEDIUM|LOW|NONE - exit 2 if findings at/above level")
        p.add_argument("--print", action="store_true", help="print the full report to stdout")

    an = sub.add_parser("analyze", help="analyse SQL and generate Liquibase changelogs")
    an.add_argument("-i", "--input", nargs="*", help="SQL / DDL / Liquibase files or directories")
    an.add_argument("--sql", help="inline SQL text")
    an.add_argument("--stdin", action="store_true", help="read SQL from stdin")
    an.add_argument("--release", help="release number, e.g. 1.35")
    an.add_argument("--author", help="changeSet author (overrides profile)")
    an.add_argument("--schema", help="default schema for unqualified objects")
    an.add_argument("--baseline", nargs="*", help="existing DB DDL (DBMS_METADATA / pg_dump -s / mysqldump -d) files/dirs")
    an.add_argument("--changelog", nargs="*", help="existing Liquibase changelogs (dup-id check, id continuation, objects)")
    an.add_argument("--format", choices=["xml", "sql", "both"], default="both")
    an.add_argument("--start-seq", type=int, help="first changeSet sequence number")
    an.add_argument("-o", "--output", default="out", help="output directory")
    an.add_argument("--no-files", action="store_true", help="do not write files")
    common(an)

    va = sub.add_parser("validate", help="validate existing Liquibase changelogs (XML / formatted SQL)")
    va.add_argument("-i", "--input", nargs="+", required=True)
    va.add_argument("-o", "--output")
    common(va)

    sub.add_parser("profiles", help="list available profiles")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "analyze":
            return cmd_analyze(a)
        if a.cmd == "validate":
            return cmd_validate(a)
        if a.cmd == "profiles":
            return cmd_profiles(a)
        ap.print_help()
        return 1
    except (FileNotFoundError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
