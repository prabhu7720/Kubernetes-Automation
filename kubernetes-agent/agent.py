#!/usr/bin/env python3
"""Kubernetes Diagnostic Agent - local, rule-based root cause analysis.

Usage:
  python agent.py analyze pod <pod> -n <namespace>
  python agent.py analyze deployment <deployment> -n <namespace>
  python agent.py analyze namespace <namespace>
  python agent.py analyze node <node>
  python agent.py analyze cluster
  python agent.py rules list

Common options: --kubeconfig PATH --context NAME -o text|markdown|json --output-file FILE
                --min-severity LEVEL --fail-on LEVEL --no-logs --no-metrics --tail N -v

No data ever leaves the machine: the only network activity is the kubectl
subprocess talking to the API server(s) in your kubeconfig.

Exit codes: 0 = no findings at/above --fail-on, 1 = findings at/above --fail-on,
            2 = usage/connection/collection error, 130 = interrupted.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from analyzers import AnalyzerSuite  # noqa: E402
from config.settings import Settings  # noqa: E402
from core import __version__, egress_guard  # noqa: E402
from core.kube_client import KubeClient, KubectlError, KubectlNotInstalled, ResourceNotFound  # noqa: E402
from core.models import Severity  # noqa: E402
from core.rule_engine import RuleEngine  # noqa: E402
from reporting import ReportGenerator  # noqa: E402

log = logging.getLogger("k8s-agent")
SEVERITIES = [s.name.lower() for s in Severity]


def _common_options() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(add_help=False)
    g = p.add_argument_group("connection")
    g.add_argument("--kubeconfig", help="kubeconfig file (default: kubectl default resolution, i.e. $KUBECONFIG or ~/.kube/config)")
    g.add_argument("--context", help="kubeconfig context to use (default: current-context)")
    g.add_argument("--kubectl", help="path to kubectl binary")
    g.add_argument("--request-timeout", type=int, help="API request timeout in seconds")
    o = p.add_argument_group("output")
    o.add_argument("-o", "--output", choices=ReportGenerator.FORMATS, default="text")
    o.add_argument("--output-file", help="write the report to this file as well")
    o.add_argument("--min-severity", choices=SEVERITIES, default="info", help="hide findings below this severity")
    o.add_argument("--fail-on", choices=SEVERITIES, default="high", help="exit 1 if findings at/above this severity")
    o.add_argument("--no-color", action="store_true")
    o.add_argument("--no-facts", action="store_true", help="omit the fact summary section")
    c = p.add_argument_group("collection")
    c.add_argument("--config", help="settings file (YAML/JSON); default config/settings.yaml")
    c.add_argument("--no-logs", action="store_true", help="do not fetch container logs")
    c.add_argument("--no-metrics", action="store_true", help="do not call kubectl top")
    c.add_argument("--tail", type=int, help="log lines per container")
    c.add_argument("--max-pods", type=int, help="max pods analyzed in deployment/namespace/cluster mode")
    c.add_argument("--workers", type=int, help="parallel pod analyses")
    p.add_argument("-v", "--verbose", action="count", default=0)
    return p


def build_parser() -> argparse.ArgumentParser:
    common = _common_options()
    parser = argparse.ArgumentParser(prog="agent.py", description="Kubernetes Diagnostic Agent (local RCA)",
                                     formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="run root cause analysis")
    targets = analyze.add_subparsers(dest="target", required=True)
    for kind in ("pod", "deployment"):
        t = targets.add_parser(kind, parents=[common], help=f"analyze a {kind}")
        t.add_argument("name")
        t.add_argument("-n", "--namespace", default="default")
    t = targets.add_parser("namespace", parents=[common], help="analyze all workloads in a namespace")
    t.add_argument("name")
    t = targets.add_parser("node", parents=[common], help="analyze a node and its unhealthy pods")
    t.add_argument("name")
    targets.add_parser("cluster", parents=[common], help="analyze nodes, system components and unhealthy pods")

    rules = sub.add_parser("rules", help="inspect the rule catalogue")
    rules_sub = rules.add_subparsers(dest="rules_cmd", required=True)
    rules_sub.add_parser("list", parents=[common], help="list loaded rules")
    return parser


def configure_logging(verbosity: int) -> None:
    level = logging.WARNING if verbosity == 0 else logging.INFO if verbosity == 1 else logging.DEBUG
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s", stream=sys.stderr)


def load_settings(args) -> Settings:
    settings = Settings.load(args.config)
    max_pods = getattr(args, "max_pods", None)
    settings.override(
        request_timeout=args.request_timeout, log_tail_lines=args.tail, workers=args.workers,
        collect_logs=False if args.no_logs else None, collect_metrics=False if args.no_metrics else None,
        max_pods_per_deployment=max_pods, max_pods_per_namespace=max_pods, max_pods_cluster=max_pods)
    return settings


def list_rules(settings: Settings) -> int:
    engine = RuleEngine(settings)
    print(f"{'ID':<16} {'SCOPES':<34} {'CATEGORY':<14} NAME")
    for rule in engine.rules:
        print(f"{rule.id:<16} {','.join(s.value for s in rule.scopes):<34} {rule.category:<14} {rule.name}")
    for err in engine.load_errors:
        print(f"! {err}", file=sys.stderr)
    print(f"\n{len(engine.rules)} rules loaded")
    return 0


def run(argv=None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.verbose)
    try:
        settings = load_settings(args)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if settings.block_network_egress:
        egress_guard.install()

    if args.command == "rules":
        return list_rules(settings)

    try:
        client = KubeClient(kubeconfig=args.kubeconfig, context=args.context, kubectl_path=args.kubectl,
                            request_timeout=settings.request_timeout, log_limit_bytes=settings.log_limit_bytes)
        suite = AnalyzerSuite(client, settings)
        for err in suite.engine.load_errors:
            log.warning(err)
        if args.target == "pod":
            result = suite.pod.analyze(args.name, args.namespace)
        elif args.target == "deployment":
            result = suite.deployment.analyze(args.name, args.namespace)
        elif args.target == "namespace":
            result = suite.namespace.analyze(args.name)
        elif args.target == "node":
            result = suite.node.analyze(args.name)
        else:
            result = suite.cluster.analyze()
    except (KubectlNotInstalled, FileNotFoundError, ResourceNotFound) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KubectlError as exc:
        hint = ""
        if exc.connection_failed:
            hint = " (cannot reach the API server - check VPN/network and the kubeconfig server URL)"
        elif exc.unauthorized:
            hint = " (credentials rejected - refresh your kubeconfig token / SSO login)"
        elif exc.forbidden:
            hint = " (RBAC forbidden - see deploy/rbac-readonly.yaml)"
        print(f"error: {exc.short}{hint}", file=sys.stderr)
        return 2

    color = not args.no_color and args.output == "text" and sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    reporter = ReportGenerator(args.output, color=color, min_severity=Severity.parse(args.min_severity),
                               metadata={"context": client.current_context()}, show_facts=not args.no_facts)
    report = reporter.render(result)
    print(report)
    if args.output_file:
        plain = ReportGenerator(args.output, color=False, min_severity=Severity.parse(args.min_severity),
                                metadata={"context": client.current_context()}, show_facts=not args.no_facts)
        Path(args.output_file).write_text(plain.render(result), encoding="utf-8")
        print(f"\nReport written to {args.output_file}", file=sys.stderr)

    worst = result.severity
    return 1 if worst is not None and worst >= Severity.parse(args.fail_on) else 0


def main() -> None:
    try:
        sys.exit(run())
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        sys.exit(130)


if __name__ == "__main__":
    main()
