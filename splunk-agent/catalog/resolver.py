"""Datasource & field resolution: maps logical datasources/fields onto the real environment.

Rule packs speak in *logical* terms ("authentication" datasource, canonical field
"user").  The resolver scores every discovered (index, sourcetype) pair against the
datasource profile (index/sourcetype patterns + field coverage), picks the best
datasets, and maps each canonical field to the actual field name via the alias
table.  When selected datasets disagree on a field name, it emits an
``eval x=coalesce(...)`` normalisation so one SPL works across all of them.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, fields as dc_fields
from fnmatch import fnmatchcase
from typing import Any, Iterable, Mapping

from catalog.metadata_store import MetadataStore
from catalog.models import METRICS_SOURCETYPE, FieldInfo
from core.exceptions import ConfigError
from core.spl import quote_eval_field, quote_value

log = logging.getLogger(__name__)


def _match_any(value: str, patterns: Iterable[str]) -> str | None:
    v = value.lower()
    for p in patterns:
        if fnmatchcase(v, p.lower()):
            return p
    return None


@dataclass(frozen=True)
class DataSourceProfile:
    name: str
    description: str = ""
    type: str = "event"  # event | metric | any
    index_patterns: tuple[str, ...] = ()
    sourcetype_patterns: tuple[str, ...] = ()
    pinned_indexes: tuple[str, ...] = ()
    pinned_sourcetypes: tuple[str, ...] = ()
    default_index: str = "main"
    default_sourcetype: str | None = None
    datamodel: str | None = None
    default_fields: Mapping[str, str] = field(default_factory=dict)
    default_metrics: Mapping[str, str] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, name: str, data: Mapping[str, Any]) -> "DataSourceProfile":
        known = {f.name for f in dc_fields(cls)} - {"name"}
        unknown = set(data) - known
        if unknown:
            raise ConfigError(f"Datasource '{name}': unknown key(s) {', '.join(sorted(unknown))}")
        kwargs = dict(data)
        for key in ("index_patterns", "sourcetype_patterns", "pinned_indexes", "pinned_sourcetypes"):
            if key in kwargs:
                v = kwargs[key]
                kwargs[key] = (v,) if isinstance(v, str) else tuple(v or ())
        if kwargs.get("type", "event") not in ("event", "metric", "any"):
            raise ConfigError(f"Datasource '{name}': type must be event|metric|any")
        return cls(name=name, **kwargs)


@dataclass(frozen=True)
class DatasetRef:
    index: str
    sourcetype: str | None = None

    def clause(self) -> str:
        parts = [f"index={quote_value(self.index)}"]
        if self.sourcetype:
            st = self.sourcetype
            parts.append(f'sourcetype="{st}"' if not re.fullmatch(r"[\w\-.*]+", st) else f"sourcetype={st}")
        return " ".join(parts)


@dataclass
class ResolvedDataSource:
    profile: str
    datasets: list[DatasetRef]
    field_map: dict[str, str] = field(default_factory=dict)
    metric_map: dict[str, str] = field(default_factory=dict)
    normalization: dict[str, list[str]] = field(default_factory=dict)
    datamodel: str | None = None
    datamodel_accelerated: bool = False
    origin: str = "default"  # pinned | catalog | default
    confidence: float = 0.0
    is_metric: bool = False
    warnings: list[str] = field(default_factory=list)

    def field(self, canonical: str) -> str:
        return self.field_map.get(canonical, canonical)

    def metric(self, canonical: str) -> str:
        return self.metric_map.get(canonical, canonical)

    @property
    def base(self) -> str:
        clauses = [d.clause() for d in self.datasets]
        if len(clauses) == 1:
            return clauses[0]
        return "(" + " OR ".join(f"({c})" for c in clauses) + ")"

    @property
    def index_clause(self) -> str:
        idx = list(dict.fromkeys(d.index for d in self.datasets))
        if len(idx) == 1:
            return f"index={quote_value(idx[0])}"
        return "(" + " OR ".join(f"index={quote_value(i)}" for i in idx) + ")"

    @property
    def normalization_eval(self) -> str | None:
        if not self.normalization:
            return None
        parts = [f"{canon}=coalesce({', '.join(quote_eval_field(a) for a in aliases)})"
                 for canon, aliases in sorted(self.normalization.items())]
        return "eval " + ", ".join(parts)

    def describe(self) -> str:
        where = "; ".join(d.clause() for d in self.datasets)
        origin = {"catalog": "selected from the discovered catalog", "pinned": "pinned in configuration",
                  "default": "profile default (not found in catalog)"}[self.origin]
        mapped = ", ".join(f"{k}->{v}" for k, v in sorted(self.field_map.items()) if k != v)
        text = f"Datasource '{self.profile}' resolved to {where} ({origin}, confidence {self.confidence:.0%})."
        return text + (f" Field mapping: {mapped}." if mapped else "")

    def to_dict(self) -> dict[str, Any]:
        return {"profile": self.profile, "datasets": [d.__dict__ for d in self.datasets], "base": self.base,
                "field_map": self.field_map, "metric_map": self.metric_map, "normalization": self.normalization,
                "datamodel": self.datamodel, "datamodel_accelerated": self.datamodel_accelerated,
                "origin": self.origin, "confidence": round(self.confidence, 2), "warnings": self.warnings}


class DataSourceResolver:
    def __init__(self, store: MetadataStore, profiles: Mapping[str, Mapping[str, Any]],
                 field_aliases: Mapping[str, list[str]] | None = None,
                 metric_aliases: Mapping[str, list[str]] | None = None, *, max_datasets: int = 3) -> None:
        self.store = store
        self.profiles = {name: DataSourceProfile.from_dict(name, data) for name, data in profiles.items()}
        self.field_aliases = dict(field_aliases or {})
        self.metric_aliases = dict(metric_aliases or {})
        self.max_datasets = max_datasets

    def profile(self, name: str) -> DataSourceProfile:
        try:
            return self.profiles[name]
        except KeyError as exc:
            raise ConfigError(f"Unknown datasource profile '{name}'. Define it in config/datasources.yaml") from exc

    def aliases(self, canonical: str) -> list[str]:
        return list(dict.fromkeys([canonical, *self.field_aliases.get(canonical, [])]))

    def metric_aliases_for(self, canonical: str) -> list[str]:
        return list(dict.fromkeys([*self.metric_aliases.get(canonical, []), canonical]))

    # -------------------------------------------------------------- resolve
    def resolve(self, profile_name: str, fields: Iterable[str] = (), metrics: Iterable[str] = (), *,
                pinned_indexes: Iterable[str] | None = None,
                pinned_sourcetypes: Iterable[str] | None = None) -> ResolvedDataSource:
        profile = self.profile(profile_name)
        wanted_fields = sorted(set(fields))
        wanted_metrics = sorted(set(metrics))
        warnings: list[str] = []
        pinned_indexes = list(pinned_indexes or [])
        pinned_sourcetypes = list(pinned_sourcetypes or [])
        is_metric = profile.type == "metric"

        if pinned_indexes or profile.pinned_indexes:
            idx = pinned_indexes or list(profile.pinned_indexes)
            sts = pinned_sourcetypes or ([] if pinned_indexes else list(profile.pinned_sourcetypes))
            datasets = [DatasetRef(i, None if is_metric else s) for i in idx for s in (sts or [None])]
            origin, confidence = "pinned", 1.0
        elif is_metric:
            datasets, confidence = self._match_metric_indexes(profile, wanted_metrics, wanted_fields)
            origin = "catalog"
        else:
            datasets, confidence = self._match_datasets(profile, wanted_fields)
            origin = "catalog"
        if not datasets:
            datasets = [DatasetRef(profile.default_index, None if is_metric else profile.default_sourcetype)]
            origin, confidence = "default", 0.3
            warnings.append(
                f"No discovered dataset matches datasource '{profile.name}'; using default "
                f"index={profile.default_index}. Run discovery or pin it in config/datasources.yaml.")

        field_map, normalization = self._map_fields(profile, datasets, wanted_fields, warnings,
                                                     allow_normalization=not is_metric)
        metric_map = self._map_metrics(profile, datasets, wanted_metrics, warnings)
        dm_name, accelerated = profile.datamodel, False
        if dm_name:
            dm = self.store.datamodel(dm_name)
            accelerated = bool(dm and dm.accelerated)
        return ResolvedDataSource(profile.name, datasets, field_map, metric_map, normalization, dm_name, accelerated,
                                  origin, confidence, is_metric, warnings)

    # -------------------------------------------------------------- scoring
    def _fields_of(self, ds: DatasetRef, cache: dict) -> dict[str, FieldInfo]:
        key = (ds.index, ds.sourcetype)
        if key not in cache:
            st = ds.sourcetype or (METRICS_SOURCETYPE if self._is_metric_index(ds.index) else "*")
            cache[key] = {k.lower(): v for k, v in self.store.fields(ds.index, st).items()}
        return cache[key]

    def _is_metric_index(self, name: str) -> bool:
        info = self.store.index(name)
        return bool(info and info.datatype == "metric")

    def _coverage(self, available: Mapping[str, FieldInfo], canonicals: list[str], metric: bool = False) -> float:
        if not canonicals:
            return 0.0
        hits = 0
        for c in canonicals:
            names = self.metric_aliases_for(c) if metric else self.aliases(c)
            if any(a.lower() in available and (available[a.lower()].kind == "metric") == metric for a in names):
                hits += 1
        return hits / len(canonicals)

    def _select(self, scored: list[tuple[float, DatasetRef]]) -> tuple[list[DatasetRef], float]:
        if not scored:
            return [], 0.0
        scored.sort(key=lambda t: (-t[0], t[1].index, t[1].sourcetype or ""))
        best = scored[0][0]
        chosen = [ds for s, ds in scored if s >= best * 0.75][: self.max_datasets]
        return chosen, min(1.0, best / 11.5)

    def _match_datasets(self, profile: DataSourceProfile, wanted: list[str]) -> tuple[list[DatasetRef], float]:
        metric_names = {i.name for i in self.store.metric_indexes()}
        groups: dict[tuple[str, str], list[float]] = {}
        singles: list[tuple[float, DatasetRef]] = []
        cache: dict = {}
        for ds in self.store.datasets():
            if ds.index in metric_names or ds.sourcetype == METRICS_SOURCETYPE:
                continue
            idx_hit = _match_any(ds.index, profile.index_patterns) is not None
            st_pattern = _match_any(ds.sourcetype, profile.sourcetype_patterns)
            if profile.sourcetype_patterns and st_pattern is None:
                continue
            if not profile.sourcetype_patterns and not idx_hit:
                continue
            ref = DatasetRef(ds.index, ds.sourcetype)
            score = (4.0 if st_pattern else 0.0) + (3.0 if idx_hit else 0.0)
            score += 4.0 * self._coverage(self._fields_of(ref, cache), wanted)
            score += 0.5 if ds.event_count > 0 else 0.0
            if st_pattern and any(ch in st_pattern for ch in "*?"):
                groups.setdefault((ds.index, st_pattern), []).append(score)
            else:
                singles.append((score, ref))
        for (index, pattern), scores in groups.items():
            if len(scores) > 1:
                singles.append((max(scores), DatasetRef(index, pattern)))
            else:
                # single concrete sourcetype matched by a wildcard - keep it concrete
                for ds in self.store.datasets(index):
                    if fnmatchcase(ds.sourcetype.lower(), pattern.lower()):
                        singles.append((scores[0], DatasetRef(index, ds.sourcetype)))
                        break
        return self._select(singles)

    def _match_metric_indexes(self, profile: DataSourceProfile, metrics: list[str],
                              dims: list[str]) -> tuple[list[DatasetRef], float]:
        scored: list[tuple[float, DatasetRef]] = []
        cache: dict = {}
        for info in self.store.metric_indexes():
            ref = DatasetRef(info.name)
            available = self._fields_of(ref, cache)
            idx_hit = _match_any(info.name, profile.index_patterns) is not None
            m_cov = self._coverage(available, metrics, metric=True)
            if not idx_hit and m_cov == 0:
                continue
            score = (3.0 if idx_hit else 0.0) + 6.0 * m_cov + 2.0 * self._coverage(available, dims) + 0.5
            scored.append((score, ref))
        return self._select(scored)

    # -------------------------------------------------------------- mapping
    def _map_fields(self, profile: DataSourceProfile, datasets: list[DatasetRef], wanted: list[str],
                    warnings: list[str], *, allow_normalization: bool) -> tuple[dict[str, str], dict[str, list[str]]]:
        cache: dict = {}
        field_map: dict[str, str] = {}
        normalization: dict[str, list[str]] = {}
        have_catalog = any(self._fields_of(ds, cache) for ds in datasets)
        for canon in wanted:
            found: list[str] = []
            for ds in datasets:
                available = self._fields_of(ds, cache)
                for alias in self.aliases(canon):
                    info = available.get(alias.lower())
                    if info and info.kind != "metric":
                        found.append(info.name)
                        break
            distinct = list(dict.fromkeys(found))
            if not distinct:
                field_map[canon] = profile.default_fields.get(canon, canon)
                if have_catalog:
                    warnings.append(f"Field '{canon}' not found in catalog for '{profile.name}'; "
                                    f"using '{field_map[canon]}'.")
            elif len(distinct) == 1 or not allow_normalization:
                field_map[canon] = distinct[0]
            else:
                field_map[canon] = canon
                normalization[canon] = distinct
        return field_map, normalization

    def _map_metrics(self, profile: DataSourceProfile, datasets: list[DatasetRef], wanted: list[str],
                     warnings: list[str]) -> dict[str, str]:
        cache: dict = {}
        out: dict[str, str] = {}
        have_catalog = any(self._fields_of(ds, cache) for ds in datasets)
        for canon in wanted:
            actual = None
            for ds in datasets:
                available = self._fields_of(ds, cache)
                actual = next((available[a.lower()].name for a in self.metric_aliases_for(canon)
                               if a.lower() in available and available[a.lower()].kind == "metric"), None)
                if actual:
                    break
            if actual is None:
                actual = profile.default_metrics.get(canon) or self.metric_aliases_for(canon)[0]
                if have_catalog:
                    warnings.append(f"Metric '{canon}' not found in catalog; using '{actual}'.")
            out[canon] = actual
        return out
