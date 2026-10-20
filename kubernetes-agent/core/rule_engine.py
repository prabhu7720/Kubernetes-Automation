"""Rule discovery (plugin loading) and evaluation.

Any ``*.py`` file dropped into ``rules/`` (or a directory listed in
``extra_rule_dirs``) that defines a concrete subclass of ``rules.base.Rule``
with a non-empty ``id`` is picked up automatically. Files starting with ``_``
are treated as private helpers and skipped.
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
import logging
import pkgutil
import sys
from pathlib import Path
from typing import List, Type

from config.settings import PROJECT_ROOT, Settings
from rules.base import Rule

from .models import Finding

log = logging.getLogger(__name__)


class RuleLoadError(RuntimeError):
    pass


class RuleLoader:
    def __init__(self, settings: Settings, package: str = "rules"):
        self.settings = settings
        self.package = package
        self.errors: List[str] = []

    @staticmethod
    def rule_classes(module) -> List[Type[Rule]]:
        found = []
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if (issubclass(obj, Rule) and obj is not Rule and obj.__module__ == module.__name__
                    and not inspect.isabstract(obj) and getattr(obj, "id", "")):
                found.append(obj)
        return found

    def _builtin_modules(self):
        pkg = importlib.import_module(self.package)
        for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
            if info.name.startswith("_") or info.name == "base":
                continue
            try:
                yield importlib.import_module(f"{self.package}.{info.name}")
            except Exception as exc:  # a broken plugin must not kill the agent
                msg = f"Failed to load rule module '{info.name}': {exc}"
                log.error(msg)
                self.errors.append(msg)

    def _external_modules(self):
        for raw in self.settings.extra_rule_dirs:
            directory = Path(raw).expanduser()
            if not directory.is_absolute():
                directory = PROJECT_ROOT / directory
            if not directory.is_dir():
                self.errors.append(f"extra_rule_dirs entry not found: {directory}")
                continue
            for file in sorted(directory.glob("*.py")):
                if file.name.startswith("_"):
                    continue
                mod_name = f"k8s_agent_ext_rules.{directory.name}.{file.stem}"
                try:
                    spec = importlib.util.spec_from_file_location(mod_name, file)
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[mod_name] = module
                    spec.loader.exec_module(module)  # type: ignore[union-attr]
                    yield module
                except Exception as exc:
                    msg = f"Failed to load external rule file '{file}': {exc}"
                    log.error(msg)
                    self.errors.append(msg)

    def load(self) -> List[Rule]:
        disabled = {r.upper() for r in self.settings.disabled_rules}
        rules: List[Rule] = []
        seen = {}
        for module in list(self._builtin_modules()) + list(self._external_modules()):
            for cls in self.rule_classes(module):
                if cls.id in seen:
                    self.errors.append(f"Duplicate rule id {cls.id} in {module.__name__} "
                                       f"(already defined in {seen[cls.id]}); ignoring")
                    continue
                seen[cls.id] = module.__name__
                overrides = self.settings.rule_overrides.get(cls.id, {}) or {}
                if not cls.enabled or cls.id.upper() in disabled or overrides.get("enabled") is False:
                    continue
                rules.append(cls(self.settings))
        return sorted(rules, key=lambda r: r.id)


class RuleEngine:
    def __init__(self, settings: Settings):
        self.settings = settings
        loader = RuleLoader(settings)
        self.rules = loader.load()
        self.load_errors = loader.errors

    def evaluate(self, ctx) -> List[Finding]:
        findings: List[Finding] = []
        for rule in self.rules:
            if not rule.applies_to(ctx):
                continue
            try:
                findings.extend(rule.evaluate(ctx) or [])
            except Exception as exc:  # isolate faulty rules
                log.exception("Rule %s failed", rule.id)
                ctx.collection_errors.append(f"Rule {rule.id} raised {type(exc).__name__}: {exc}")
        return findings
