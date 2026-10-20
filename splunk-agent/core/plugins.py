"""Plugin discovery.

Three extension points use the same mechanism:

* ``rules/``       - rule packs (``RulePack`` subclasses or declarative ``*.yaml``)
* ``generators/``  - artifact generators (``ArtifactGenerator`` subclasses)
* ``discovery/``   - metadata collectors (``Collector`` subclasses)

Every non-private module in the package is imported; classes register themselves
via ``__init_subclass__``.  Extra directories (outside the code base) can be added
in ``config/settings.yaml -> plugins.*_dirs`` - drop a file in, get a capability.
"""

from __future__ import annotations

import hashlib
import importlib
import importlib.util
import logging
import pkgutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Iterable

from core.exceptions import PluginLoadError

log = logging.getLogger(__name__)


@dataclass
class PluginLoadReport:
    modules: list[ModuleType] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def module_names(self) -> set[str]:
        return {m.__name__ for m in self.modules}


def load_python_file(path: Path, namespace: str) -> ModuleType:
    digest = hashlib.sha1(str(path.resolve()).encode()).hexdigest()[:8]
    mod_name = f"_plugin_{namespace}_{digest}_{path.stem}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise PluginLoadError(f"Cannot load plugin file {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - surface any plugin error uniformly
        sys.modules.pop(mod_name, None)
        raise PluginLoadError(f"Plugin {path} failed to import: {exc}") from exc
    return module


def load_plugins(package: str, extra_dirs: Iterable[str | Path] = (), *, strict: bool = False,
                 skip: Iterable[str] = ("base",)) -> PluginLoadReport:
    report = PluginLoadReport()
    skip = set(skip)
    pkg = importlib.import_module(package)
    for info in sorted(pkgutil.iter_modules(pkg.__path__), key=lambda i: i.name):
        if info.ispkg or info.name.startswith("_") or info.name in skip:
            continue
        full = f"{package}.{info.name}"
        try:
            report.modules.append(importlib.import_module(full))
        except Exception as exc:  # noqa: BLE001
            msg = f"Failed to import plugin module {full}: {exc}"
            if strict:
                raise PluginLoadError(msg) from exc
            log.error(msg)
            report.errors.append(msg)
    for directory in extra_dirs:
        d = Path(directory)
        if not d.is_dir():
            msg = f"Plugin directory not found: {d}"
            if strict:
                raise PluginLoadError(msg)
            log.warning(msg)
            report.errors.append(msg)
            continue
        for path in sorted(d.glob("*.py")):
            if path.name.startswith("_"):
                continue
            try:
                report.modules.append(load_python_file(path, package))
            except PluginLoadError as exc:
                if strict:
                    raise
                log.error(str(exc))
                report.errors.append(str(exc))
    log.debug("Loaded %d plugin module(s) for %s", len(report.modules), package)
    return report


def package_dir(package: str) -> Path:
    return Path(importlib.import_module(package).__path__[0])


def yaml_files(dirs: Iterable[str | Path]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        p = Path(d)
        if p.is_dir():
            out.extend(sorted(list(p.glob("*.yaml")) + list(p.glob("*.yml"))))
    return out
