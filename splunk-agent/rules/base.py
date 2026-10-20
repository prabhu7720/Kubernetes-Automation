"""Rule-pack plugin contract and registry.

Add a capability by dropping a file into ``rules/`` (or any directory listed in
``plugins.rule_dirs``):

* Python: subclass :class:`RulePack`, set ``domain`` and return ``UseCase`` objects.
* YAML:   a declarative file with ``domain``, ``use_cases`` and optional ``dashboards``.

No registration code is required - subclasses register themselves and YAML files
are picked up by the registry scan.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, ClassVar, Iterable, Mapping

import yaml

from core.exceptions import PluginLoadError
from core.models import DashboardBlueprint, UseCase
from core.nlp import normalize
from core.plugins import load_plugins, package_dir, yaml_files

log = logging.getLogger(__name__)


class RulePack:
    """Base class for rule packs."""

    domain: ClassVar[str] = ""
    title: ClassVar[str] = ""
    description: ClassVar[str] = ""
    domain_keywords: ClassVar[tuple[str, ...]] = ()
    #: only match this pack when one of its domain keywords is mentioned (e.g. aws, azure, pci)
    exclusive: ClassVar[bool] = False
    #: datasource profiles contributed by the pack (config/datasources.yaml wins on conflict)
    datasources: ClassVar[dict[str, dict[str, Any]]] = {}
    source: str = ""

    _registry: ClassVar[dict[str, type["RulePack"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get("domain"):
            RulePack._registry[f"{cls.__module__}.{cls.__qualname__}"] = cls

    def use_cases(self) -> list[UseCase]:
        return []

    def dashboards(self) -> list[DashboardBlueprint]:
        return []

    def uc(self, id: str, name: str, **kwargs: Any) -> UseCase:  # noqa: A002 - mirrors UseCase.id
        """Shorthand constructor that fills in the pack's domain."""
        return UseCase(id=id, name=name, domain=self.domain, **kwargs)

    def bp(self, id: str, title: str, **kwargs: Any) -> DashboardBlueprint:  # noqa: A002
        return DashboardBlueprint(id=id, title=title, domain=self.domain, **kwargs)


class YamlRulePack(RulePack):
    """A rule pack defined declaratively in YAML."""

    def __init__(self, path: Path, data: Mapping[str, Any]) -> None:
        if not data.get("domain"):
            raise PluginLoadError(f"{path}: 'domain' is required")
        self.source = str(path)
        self.domain = str(data["domain"])  # type: ignore[misc]
        self.title = str(data.get("title", self.domain.title()))  # type: ignore[misc]
        self.description = str(data.get("description", ""))  # type: ignore[misc]
        self.domain_keywords = tuple(data.get("domain_keywords", ()))  # type: ignore[misc]
        self.exclusive = bool(data.get("exclusive", False))  # type: ignore[misc]
        self.datasources = dict(data.get("datasources") or {})  # type: ignore[misc]
        try:
            self._use_cases = [UseCase.from_dict(d, domain=self.domain) for d in data.get("use_cases", [])]
            self._dashboards = [DashboardBlueprint.from_dict(d, domain=self.domain) for d in data.get("dashboards", [])]
        except (TypeError, ValueError) as exc:
            raise PluginLoadError(f"{path}: {exc}") from exc

    @classmethod
    def load(cls, path: Path) -> "YamlRulePack":
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            raise PluginLoadError(f"Cannot read rule file {path}: {exc}") from exc
        if not isinstance(data, Mapping):
            raise PluginLoadError(f"{path}: top level must be a mapping")
        return cls(path, data)

    def use_cases(self) -> list[UseCase]:
        return list(self._use_cases)

    def dashboards(self) -> list[DashboardBlueprint]:
        return list(self._dashboards)


class RuleRegistry:
    """Holds every loaded use case and dashboard blueprint."""

    def __init__(self) -> None:
        self.packs: list[RulePack] = []
        self.use_cases: dict[str, UseCase] = {}
        self.blueprints: dict[str, DashboardBlueprint] = {}
        self.datasources: dict[str, dict[str, Any]] = {}
        self.domain_keywords: dict[str, set[str]] = {}
        self.domain_titles: dict[str, str] = {}
        self.exclusive_domains: set[str] = set()
        self.errors: list[str] = []
        self.strict = False

    # --------------------------------------------------------------- loading
    @classmethod
    def discover(cls, extra_dirs: Iterable[str | Path] = (), *, strict: bool = False,
                 overrides: Mapping[str, Mapping[str, Any]] | None = None,
                 package: str = "rules") -> "RuleRegistry":
        extra_dirs = list(extra_dirs)
        registry = cls()
        registry.strict = strict
        report = load_plugins(package, extra_dirs, strict=strict)
        registry.errors.extend(report.errors)
        loaded = report.module_names
        for name in sorted(RulePack._registry):
            klass = RulePack._registry[name]
            if klass.__module__ in loaded:
                try:
                    registry.add_pack(klass())
                except Exception as exc:  # noqa: BLE001
                    registry._error(f"Rule pack {name} failed: {exc}", exc)
        for path in yaml_files([package_dir(package), *extra_dirs]):
            try:
                registry.add_pack(YamlRulePack.load(path))
            except PluginLoadError as exc:
                registry._error(str(exc), exc)
        if overrides:
            registry.apply_overrides(overrides)
        registry.validate()
        log.info("Loaded %d rule pack(s), %d use case(s), %d dashboard blueprint(s)",
                 len(registry.packs), len(registry.use_cases), len(registry.blueprints))
        return registry

    def _error(self, message: str, exc: Exception | None = None) -> None:
        if self.strict:
            raise PluginLoadError(message) from exc
        log.error(message)
        self.errors.append(message)

    def add_pack(self, pack: RulePack) -> None:
        source = pack.source or type(pack).__module__
        self.packs.append(pack)
        self.domain_keywords.setdefault(pack.domain, set()).update(
            t for kw in (pack.domain, *pack.domain_keywords) for t in normalize(kw))
        self.domain_titles.setdefault(pack.domain, pack.title or pack.domain.title())
        if pack.exclusive:
            self.exclusive_domains.add(pack.domain)
        for name, profile in (pack.datasources or {}).items():
            self.datasources.setdefault(name, dict(profile))
        for uc in pack.use_cases():
            if uc.id in self.use_cases:
                self._error(f"Duplicate use case id '{uc.id}' in {source}; keeping the first definition")
                continue
            self.use_cases[uc.id] = uc
        for bp in pack.dashboards():
            if bp.id in self.blueprints:
                self._error(f"Duplicate dashboard blueprint '{bp.id}' in {source}")
                continue
            self.blueprints[bp.id] = bp

    def apply_overrides(self, overrides: Mapping[str, Mapping[str, Any]]) -> None:
        for uc_id, ov in overrides.items():
            if uc_id not in self.use_cases:
                log.warning("use_case_overrides: unknown use case '%s'", uc_id)
                continue
            try:
                self.use_cases[uc_id] = self.use_cases[uc_id].with_overrides(ov)
            except (TypeError, ValueError) as exc:
                self._error(f"Invalid override for '{uc_id}': {exc}", exc)

    def validate(self) -> None:
        for uc in self.use_cases.values():
            for rel in uc.related:
                if rel not in self.use_cases:
                    log.debug("Use case %s references unknown related use case %s", uc.id, rel)
        for bp_id, bp in list(self.blueprints.items()):
            missing = [p.use_case for p in bp.panels if p.use_case not in self.use_cases]
            if missing:
                self._error(f"Blueprint '{bp_id}' references unknown use case(s): {', '.join(missing)}")
                kept = tuple(p for p in bp.panels if p.use_case in self.use_cases)
                if kept:
                    from dataclasses import replace
                    self.blueprints[bp_id] = replace(bp, panels=kept)
                else:
                    del self.blueprints[bp_id]

    # ---------------------------------------------------------------- access
    def get(self, use_case_id: str) -> UseCase:
        try:
            return self.use_cases[use_case_id]
        except KeyError as exc:
            raise KeyError(f"Unknown use case '{use_case_id}'") from exc

    def by_domain(self, domain: str) -> list[UseCase]:
        return [uc for uc in self.use_cases.values() if uc.domain == domain]

    @property
    def domains(self) -> list[str]:
        return sorted({uc.domain for uc in self.use_cases.values()})

    def capabilities(self) -> dict[str, Any]:
        return {
            domain: {
                "title": self.domain_titles.get(domain, domain),
                "use_cases": [{"id": uc.id, "name": uc.name, "datasource": uc.datasource} for uc in self.by_domain(domain)],
                "dashboards": [bp.id for bp in self.blueprints.values() if bp.domain == domain],
            }
            for domain in self.domains
        }
