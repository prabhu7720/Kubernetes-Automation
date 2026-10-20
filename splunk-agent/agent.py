#!/usr/bin/env python3
"""Offline Splunk Automation Agent.

Converts natural-language requests into SPL searches, reports, alerts, Dashboard
Studio dashboards, ES correlation searches and runbooks - using only local,
rule-based reasoning over metadata discovered from Splunk's REST API. No LLM or
cloud service is ever called.

    python agent.py discover                      # build/refresh the metadata catalog
    python agent.py ask "Show failed logins"      # generate artifacts (offline)
    python agent.py ask "Create alert when HTTP 500 errors exceed 100 per hour" --out out/
    python agent.py ask "Generate dashboard for Kubernetes health" --deploy
    python agent.py capabilities | catalog summary | interactive | validate "<spl>"
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, Sequence

from catalog.enrichment import EnrichmentResolver
from catalog.metadata_store import MetadataStore
from catalog.resolver import DataSourceResolver
from core.config import Settings, load_settings
from core.exceptions import ConfigError, IntentResolutionError, SplunkAgentError
from core.intent import FieldFilter, Intent, IntentParser
from core.logging_setup import configure_logging
from core.matcher import UseCaseMatcher
from core.models import ArtifactType, UseCase, Visualization
from core.nlp import normalize
from core.response import AgentResponse
from core.splunk_client import SplunkClient, SplunkClientProtocol
from core.spl import lint
from core.templates import TemplateStore
from core.visualization import recommend
from generators.base import ArtifactGenerator, GenerationRequest, GeneratorServices
from generators.dashboard_generator import DashboardComposer
from generators.search_generator import SearchGenerator
from publishers.splunk_publisher import PublishResult, SplunkPublisher
from rules.base import RuleRegistry

log = logging.getLogger("splunk_agent")
__version__ = "1.0.0"


class SplunkAgent:
    """Orchestrates parsing, matching, resolution and artifact generation."""

    def __init__(self, settings: Settings, *, store: MetadataStore | None = None,
                 client: SplunkClientProtocol | None = None) -> None:
        self.settings = settings
        self.store = store or MetadataStore(settings.catalog.path)
        self._client = client
        self.registry = RuleRegistry.discover(settings.plugins.rule_dirs, strict=settings.plugins.strict,
                                              overrides=settings.use_case_overrides)
        profiles: dict[str, dict] = {**self.registry.datasources, **settings.datasources}
        profiles.setdefault("any", {"type": "any", "pinned_indexes": ["*"], "default_index": "*"})
        missing = sorted({uc.datasource for uc in self.registry.use_cases.values()} - set(profiles))
        if missing:
            raise ConfigError(f"Use cases reference undefined datasource profile(s): {', '.join(missing)}")
        self.resolver = DataSourceResolver(self.store, profiles, settings.field_aliases, settings.metric_aliases)
        self.enrichments = EnrichmentResolver(self.store, settings.enrichments)
        self.templates = TemplateStore(settings.templates_dir)
        self.parser = IntentParser()
        self.matcher = UseCaseMatcher(self.registry, settings.generation.min_match_score)
        self.search_generator = SearchGenerator(self.resolver, self.enrichments, settings.generation)
        self.composer = DashboardComposer(self.search_generator, self.registry,
                                          settings.generation.max_dashboard_panels)
        self.services = GeneratorServices(settings, self.store, self.registry, self.search_generator, self.templates)
        self.generators = ArtifactGenerator.load_all(self.services, settings.plugins.generator_dirs,
                                                     strict=settings.plugins.strict)

    # ------------------------------------------------------------ splunk
    @property
    def client(self) -> SplunkClientProtocol:
        if self._client is None:
            self._client = SplunkClient(self.settings.splunk)
        return self._client

    def discover(self, collectors: Sequence[str] | None = None):
        from discovery.engine import DiscoveryEngine

        connect = getattr(self.client, "connect", None)
        if callable(connect):
            connect()  # fail fast (auth/TLS/network) before running any collector
        engine = DiscoveryEngine(self.client, self.store, self.settings.discovery,
                                 self.settings.plugins.collector_dirs)
        return engine.run(collectors)

    # --------------------------------------------------------------- ask
    def ask(self, text: str) -> AgentResponse:
        intent = self.parser.parse(text)
        log.debug("intent: %s", intent.to_dict())
        if intent.artifact_type is ArtifactType.DASHBOARD:
            return self._dashboard(intent)

        matches = self.matcher.match(intent)
        if matches:
            uc, confidence = matches[0].use_case, matches[0].confidence
            alternatives = [m.use_case.id for m in matches[1:4]]
        else:
            uc = self._adhoc_use_case(intent)
            if uc is None:
                raise IntentResolutionError(
                    f"Could not map '{text}' to a known capability.", self.matcher.suggestions(intent))
            intent = self._with_index_filters(intent)
            confidence, alternatives = 0.3, []

        search = self.search_generator.generate(uc, intent)
        components = self.composer.suggest(uc, intent)
        request = GenerationRequest(intent=intent, title=intent.title or uc.name, use_case=uc, search=search,
                                    use_cases=[uc], searches={uc.id: search}, components=components)
        return self._finish(request, [search], confidence, alternatives)

    def _dashboard(self, intent: Intent) -> AgentResponse:
        bp_matches = self.matcher.match_blueprints(intent)
        blueprint = bp_matches[0].blueprint if bp_matches else None
        if blueprint:
            components = self.composer.from_blueprint(blueprint, intent)
            confidence = min(1.0, bp_matches[0].score / 4.5)
            alternatives = [m.blueprint.id for m in bp_matches[1:]]
        else:
            matches = self.matcher.match(intent, limit=20)
            if not matches:
                raise IntentResolutionError(f"No dashboard blueprint or use case matches '{intent.text}'.",
                                            self.matcher.suggestions(intent))
            domain = matches[0].use_case.domain
            ucs = [m.use_case for m in matches if m.use_case.domain == domain][:6]
            components = self.composer.auto(ucs, intent)
            confidence, alternatives = matches[0].confidence, []
        if not components:
            raise IntentResolutionError("Dashboard has no renderable panels.")
        ucs = [self.registry.use_cases[c.use_case_id] for c in components]
        primary = next((c for c in components if c.kind != "kpi"), components[0])
        primary_uc = self.registry.use_cases[primary.use_case_id]
        search = self.search_generator.generate(primary_uc, intent)
        title = intent.title or (blueprint.title if blueprint else f"{primary_uc.domain.title()} Dashboard")
        request = GenerationRequest(intent=intent, title=title, use_case=primary_uc, search=search,
                                    use_cases=list(dict.fromkeys(ucs)),
                                    searches={c.use_case_id: c.search for c in components if c.search},
                                    components=components, blueprint=blueprint)
        searches = [search] + [c.search for c in components if c.search]
        return self._finish(request, searches, round(confidence, 2), alternatives)

    def _finish(self, request: GenerationRequest, searches: list, confidence: float,
                alternatives: list[str]) -> AgentResponse:
        artifacts = {}
        warnings: list[str] = []
        for gen in self.generators:
            try:
                if gen.applies(request):
                    art = gen.generate(request)
                    if art is not None:
                        artifacts[gen.name] = art
            except SplunkAgentError:
                raise
            except Exception as exc:  # noqa: BLE001 - one plugin failing must not break the response
                log.exception("Generator %s failed", gen.name)
                warnings.append(f"Generator '{gen.name}' failed: {exc}")
        primary = request.search
        warnings = list(primary.warnings) + warnings + self._similar_objects(request.title, primary.spl)
        explanation = list(primary.explanation)
        if request.blueprint:
            explanation.insert(0, f"Dashboard blueprint '{request.blueprint.id}' selected with "
                                  f"{len(request.components)} panels; panels share a global time picker.")
        return AgentResponse(
            request=request.intent.text, intent=request.intent, title=request.title, use_cases=request.use_cases,
            searches=searches, explanation=explanation,
            visualization=recommend(primary.spl, request.use_case.visualization),
            components=request.components, artifacts=artifacts, confidence=confidence,
            alternatives=alternatives, warnings=warnings)

    # ---------------------------------------------------------- helpers
    def _known_indexes_in(self, intent: Intent) -> list[str]:
        names = {i.name.lower(): i.name for i in self.store.indexes()}
        words = set(intent.text.lower().replace(",", " ").split())
        return [names[w] for w in words if w in names]

    def _with_index_filters(self, intent: Intent) -> Intent:
        if intent.index_filters:
            return intent
        extra = [FieldFilter("index", name) for name in self._known_indexes_in(intent)]
        return replace(intent, filters=list(intent.filters) + extra)

    def _adhoc_use_case(self, intent: Intent) -> UseCase | None:
        """Metadata-driven fallback: request mentions a known index or explicit field filters."""
        if not (intent.index_filters or self._known_indexes_in(intent)):
            return None
        pipeline = ("| stats count BY {{groupby}}\n| sort - count\n| head {{limit}}" if intent.groupby
                    else "| stats count BY sourcetype\n| sort - count")
        return UseCase(id="adhoc_search", name="Ad-hoc Search", domain="adhoc",
                       description="Metadata-driven search built from indexes/filters named in the request.",
                       datasource="any", keywords=("adhoc",), pipeline=pipeline, groupby=intent.groupby,
                       visualization=Visualization.TABLE)

    def _similar_objects(self, title: str, spl: str) -> list[str]:
        mine = set(normalize(title))
        out = []
        for ko in self.store.knowledge_objects(("report", "alert", "saved_search")):
            theirs = set(normalize(ko.name))
            same_search = " ".join(str(ko.attributes.get("search") or "").split()) == " ".join(spl.split())
            jaccard = len(mine & theirs) / len(mine | theirs) if mine and theirs else 0
            contained = len(mine) >= 2 and mine <= theirs
            if same_search or jaccard >= 0.6 or contained:
                out.append(f"Existing {ko.kind} '{ko.name}' (app {ko.app or '?'}) looks similar - consider reusing it.")
        return out

    # ------------------------------------------------------------ deploy
    def deploy(self, response: AgentResponse, *, dry_run: bool = True) -> list[PublishResult]:
        if not dry_run and not self.settings.publish.enabled:
            raise ConfigError("Publishing is disabled. Set publish.enabled: true in config/settings.yaml.")
        client = self.client if not dry_run else None
        publisher = SplunkPublisher(client, self.settings.publish)
        results: list[PublishResult] = []
        kind = response.artifact_type
        if kind in (ArtifactType.REPORT, ArtifactType.SAVED_SEARCH, ArtifactType.SEARCH):
            rpt = response.artifact("report")
            results.append(publisher.publish_saved_search(rpt.name, rpt.saved_search_params(), kind="report",
                                                          dry_run=dry_run))
        if kind is ArtifactType.ALERT:
            for d in response.artifact("alert").definitions:
                results.append(publisher.publish_saved_search(d.name, d.saved_search_params(), kind="alert",
                                                              dry_run=dry_run))
        if kind is ArtifactType.CORRELATION or (kind is ArtifactType.ALERT and response.artifact("correlation")):
            cs = response.artifact("correlation")
            if cs:
                results.append(publisher.publish_saved_search(cs.name, cs.saved_search_params(), kind="correlation",
                                                              dry_run=dry_run))
        if kind is ArtifactType.DASHBOARD:
            dash = response.artifact("dashboard")
            results.append(publisher.publish_dashboard(dash.name, dash.to_xml(), dry_run=dry_run))
        return results

    def capabilities(self) -> dict[str, Any]:
        return {"version": __version__, "domains": self.registry.capabilities(),
                "generators": [g.name for g in self.generators], "plugin_errors": self.registry.errors}


# ====================================================================== CLI
def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="splunk-agent", description="Offline Splunk automation agent")
    p.add_argument("--config", help="Path to settings.yaml (default: config/settings.yaml or $SPLUNK_AGENT_CONFIG)")
    p.add_argument("--log-level", help="Override logging level (DEBUG, INFO, ...)")
    p.add_argument("--catalog", help="Override catalog path")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("discover", help="Discover the Splunk environment into the local catalog")
    d.add_argument("--collectors", help="Comma-separated subset (indexes,sourcetypes,hosts,sources,fields,...)")

    a = sub.add_parser("ask", help="Generate artifacts from a natural-language request")
    a.add_argument("request", nargs="+")
    a.add_argument("--format", choices=("markdown", "json"), default="markdown")
    a.add_argument("--out", help="Write SPL/conf/JSON/XML/runbook files into this directory")
    a.add_argument("--deploy", action="store_true", help="Publish to Splunk (requires publish.enabled)")
    a.add_argument("--dry-run", action="store_true", help="Show what --deploy would publish")

    sub.add_parser("interactive", help="Interactive prompt")
    c = sub.add_parser("catalog", help="Inspect / import / export the metadata catalog")
    c.add_argument("action", choices=("summary", "datasets", "fields", "export", "import"))
    c.add_argument("arg", nargs="*")
    cap = sub.add_parser("capabilities", help="List rule packs, use cases and generators")
    cap.add_argument("--format", choices=("text", "json"), default="text")
    v = sub.add_parser("validate", help="Lint SPL offline (optionally validate on the server)")
    v.add_argument("spl")
    v.add_argument("--remote", action="store_true")
    return p


def _print_capabilities(caps: dict[str, Any]) -> None:
    for domain, info in caps["domains"].items():
        print(f"\n[{domain}] {info['title']}  (dashboards: {', '.join(info['dashboards']) or '-'})")
        for uc in info["use_cases"]:
            print(f"  - {uc['id']:<32} {uc['name']}  <{uc['datasource']}>")
    print(f"\nGenerators: {', '.join(caps['generators'])}")
    if caps["plugin_errors"]:
        print("Plugin errors:\n  " + "\n  ".join(caps["plugin_errors"]))


def _handle_ask(agent: SplunkAgent, text: str, fmt: str, out: str | None, deploy: bool, dry_run: bool) -> int:
    response = agent.ask(text)
    print(response.to_json() if fmt == "json" else response.to_markdown())
    if out:
        files = response.write(out)
        print(f"\nWrote {len(files)} file(s) to {out}", file=sys.stderr)
    if deploy or dry_run:
        for r in agent.deploy(response, dry_run=not deploy or dry_run):
            print(f"[{r.action}] {r.kind} '{r.name}': {r.message}", file=sys.stderr)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        overrides = {"catalog": {"path": args.catalog}} if args.catalog else None
        settings = load_settings(args.config, overrides=overrides)
        configure_logging(settings.logging, level_override=args.log_level)
        agent = SplunkAgent(settings)

        if args.command == "discover":
            only = [c.strip() for c in args.collectors.split(",")] if args.collectors else None
            report = agent.discover(only)
            print(json.dumps(report.to_dict(), indent=2))
            print(json.dumps(agent.store.summary(), indent=2, default=str))
            return 0 if report.ok else 4
        if args.command == "ask":
            return _handle_ask(agent, " ".join(args.request), args.format, args.out, args.deploy, args.dry_run)
        if args.command == "interactive":
            print("Splunk agent (offline). Type a request, 'help' for capabilities, 'quit' to exit.")
            while True:
                try:
                    line = input("splunk-agent> ").strip()
                except (EOFError, KeyboardInterrupt):
                    print()
                    return 0
                if line in ("quit", "exit"):
                    return 0
                if line == "help":
                    _print_capabilities(agent.capabilities())
                    continue
                if line:
                    try:
                        print(agent.ask(line).to_markdown())
                    except IntentResolutionError as exc:
                        print(f"! {exc}" + (f" Did you mean: {', '.join(exc.suggestions)}?" if exc.suggestions else ""))
        if args.command == "catalog":
            if args.action == "summary":
                print(json.dumps(agent.store.summary(), indent=2, default=str))
            elif args.action == "datasets":
                for ds in agent.store.datasets():
                    print(f"{ds.index:<20} {ds.sourcetype:<40} {ds.event_count:>12}")
            elif args.action == "fields":
                if len(args.arg) != 2:
                    raise ConfigError("usage: catalog fields <index> <sourcetype>")
                for f in agent.store.fields(*args.arg).values():
                    print(f"{f.name:<40} {f.kind:<10} coverage={f.coverage:.0%} samples={list(f.sample_values)[:3]}")
            elif args.action == "export":
                print(agent.store.export_json(args.arg[0] if args.arg else "catalog/catalog_export.json"))
            elif args.action == "import":
                if not args.arg:
                    raise ConfigError("usage: catalog import <file.json>")
                agent.store.import_json(args.arg[0])
                print(json.dumps(agent.store.summary(), indent=2, default=str))
            return 0
        if args.command == "capabilities":
            caps = agent.capabilities()
            print(json.dumps(caps, indent=2)) if args.format == "json" else _print_capabilities(caps)
            return 0
        if args.command == "validate":
            issues = lint(args.spl)
            for i in issues:
                print(f"{i.level.upper():<8} {i.code}: {i.message}")
            ok = not any(i.level == "error" for i in issues)
            if args.remote:
                remote_ok, msg = agent.client.parse(args.spl)  # type: ignore[attr-defined]
                print(f"REMOTE   {'ok' if remote_ok else 'error'}: {msg}")
                ok = ok and remote_ok
            print("OK" if ok else "INVALID")
            return 0 if ok else 1
    except IntentResolutionError as exc:
        hint = f"\nDid you mean: {', '.join(exc.suggestions)}?" if exc.suggestions else ""
        print(f"error: {exc}{hint}", file=sys.stderr)
        return exc.exit_code
    except SplunkAgentError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:  # pragma: no cover
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
