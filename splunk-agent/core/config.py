"""Configuration management.

Settings are layered (lowest to highest precedence):

1. dataclass defaults (this module)
2. ``config/settings.yaml`` (or the file in ``$SPLUNK_AGENT_CONFIG``)
3. ``${ENV_VAR:-default}`` interpolation inside YAML values
4. well-known environment variables (``SPLUNK_HOST``, ``SPLUNK_TOKEN`` ...)
5. explicit ``overrides`` passed by the caller (CLI flags, tests)

Secrets (password / token) should come from the environment or a secrets manager
that injects environment variables - never commit them to YAML.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import MISSING, dataclass, field, fields
from pathlib import Path
from typing import Any, Mapping

import yaml

from core.exceptions import ConfigError

log = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_DIR = PROJECT_ROOT / "config"
CONFIG_ENV_VAR = "SPLUNK_AGENT_CONFIG"

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?::-([^}]*))?\}")
_TRUE = {"1", "true", "yes", "on", "y"}
_FALSE = {"0", "false", "no", "off", "n"}
_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

_ENV_OVERRIDES: dict[str, tuple[str, str]] = {
    "SPLUNK_HOST": ("splunk", "host"),
    "SPLUNK_PORT": ("splunk", "port"),
    "SPLUNK_SCHEME": ("splunk", "scheme"),
    "SPLUNK_USERNAME": ("splunk", "username"),
    "SPLUNK_PASSWORD": ("splunk", "password"),
    "SPLUNK_TOKEN": ("splunk", "token"),
    "SPLUNK_APP": ("splunk", "app"),
    "SPLUNK_VERIFY_SSL": ("splunk", "verify_ssl"),
    "SPLUNK_CA_BUNDLE": ("splunk", "ca_bundle"),
    "SPLUNK_AGENT_CATALOG": ("catalog", "path"),
    "SPLUNK_AGENT_LOG_LEVEL": ("logging", "level"),
}


# --------------------------------------------------------------------------- sections
@dataclass(frozen=True)
class SplunkSettings:
    host: str = "localhost"
    port: int = 8089
    scheme: str = "https"
    username: str | None = None
    password: str | None = field(default=None, repr=False)
    token: str | None = field(default=None, repr=False)
    app: str = "search"
    owner: str = "nobody"
    verify_ssl: bool = True
    ca_bundle: str | None = None
    timeout: int = 60
    retries: int = 3
    retry_delay: float = 2.0

    def validate(self) -> None:
        if self.scheme not in ("http", "https"):
            raise ConfigError(f"splunk.scheme must be http or https, got {self.scheme!r}")
        if not 1 <= self.port <= 65535:
            raise ConfigError(f"splunk.port out of range: {self.port}")
        if self.timeout <= 0 or self.retries < 0 or self.retry_delay < 0:
            raise ConfigError("splunk.timeout must be > 0 and retries/retry_delay >= 0")

    @property
    def has_credentials(self) -> bool:
        return bool(self.token or (self.username and self.password))


@dataclass(frozen=True)
class DiscoverySettings:
    lookback: str = "-7d"
    field_sample_size: int = 500
    max_datasets_for_fields: int = 100
    include_internal_indexes: bool = False
    max_hosts: int = 5000
    max_sources: int = 2000
    max_workers: int = 4
    collectors: tuple[str, ...] = ()

    def validate(self) -> None:
        for name in ("field_sample_size", "max_datasets_for_fields", "max_hosts", "max_sources", "max_workers"):
            if getattr(self, name) <= 0:
                raise ConfigError(f"discovery.{name} must be > 0")


@dataclass(frozen=True)
class CatalogSettings:
    path: str = "catalog/metadata.db"


@dataclass(frozen=True)
class PluginSettings:
    rule_dirs: tuple[str, ...] = ()
    generator_dirs: tuple[str, ...] = ()
    collector_dirs: tuple[str, ...] = ()
    strict: bool = False


@dataclass(frozen=True)
class GenerationSettings:
    name_prefix: str = "AUTO - "
    default_earliest: str = "-24h"
    min_match_score: float = 1.5
    max_dashboard_panels: int = 16
    dashboard_theme: str = "dark"
    include_accelerated: bool = True
    strict_lint: bool = False
    alert_email_to: str | None = None
    alert_webhook_url: str | None = None

    def validate(self) -> None:
        if self.dashboard_theme not in ("dark", "light"):
            raise ConfigError("generation.dashboard_theme must be 'dark' or 'light'")
        if self.min_match_score <= 0:
            raise ConfigError("generation.min_match_score must be > 0")


@dataclass(frozen=True)
class PublishSettings:
    enabled: bool = False
    app: str = "search"
    owner: str = "nobody"
    sharing: str = "app"
    overwrite: bool = False

    def validate(self) -> None:
        if self.sharing not in ("user", "app", "global"):
            raise ConfigError("publish.sharing must be one of user|app|global")


@dataclass(frozen=True)
class LoggingSettings:
    level: str = "INFO"
    file: str | None = None
    json: bool = False
    max_bytes: int = 10_485_760
    backup_count: int = 5

    def validate(self) -> None:
        if self.level.upper() not in _LOG_LEVELS:
            raise ConfigError(f"logging.level must be one of {sorted(_LOG_LEVELS)}")


@dataclass(frozen=True)
class Settings:
    splunk: SplunkSettings = field(default_factory=SplunkSettings)
    discovery: DiscoverySettings = field(default_factory=DiscoverySettings)
    catalog: CatalogSettings = field(default_factory=CatalogSettings)
    plugins: PluginSettings = field(default_factory=PluginSettings)
    generation: GenerationSettings = field(default_factory=GenerationSettings)
    publish: PublishSettings = field(default_factory=PublishSettings)
    logging: LoggingSettings = field(default_factory=LoggingSettings)
    datasources: dict[str, dict[str, Any]] = field(default_factory=dict)
    enrichments: dict[str, dict[str, Any]] = field(default_factory=dict)
    field_aliases: dict[str, list[str]] = field(default_factory=dict)
    metric_aliases: dict[str, list[str]] = field(default_factory=dict)
    use_case_overrides: dict[str, dict[str, Any]] = field(default_factory=dict)
    config_dir: Path = DEFAULT_CONFIG_DIR
    templates_dir: Path = PROJECT_ROOT / "templates"


_SECTIONS: dict[str, type] = {
    "splunk": SplunkSettings,
    "discovery": DiscoverySettings,
    "catalog": CatalogSettings,
    "plugins": PluginSettings,
    "generation": GenerationSettings,
    "publish": PublishSettings,
    "logging": LoggingSettings,
}
_TOP_LEVEL = set(_SECTIONS) | {"use_case_overrides", "templates_dir", "files"}


# --------------------------------------------------------------------------- helpers
def interpolate_env(value: Any) -> Any:
    """Expand ``${VAR}`` / ``${VAR:-default}`` recursively."""
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), m.group(2) or ""), value)
    if isinstance(value, Mapping):
        return {k: interpolate_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate_env(v) for v in value]
    return value


def _coerce(value: Any, default: Any, key: str) -> Any:
    if value is None:
        return default
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _TRUE:
            return True
        if text in _FALSE:
            return False
        raise ConfigError(f"{key}: expected boolean, got {value!r}")
    if isinstance(default, int):
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{key}: expected integer, got {value!r}") from exc
    if isinstance(default, float):
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ConfigError(f"{key}: expected number, got {value!r}") from exc
    if isinstance(default, tuple):
        if isinstance(value, str):
            return tuple(v.strip() for v in value.split(",") if v.strip())
        if isinstance(value, (list, tuple)):
            return tuple(str(v) for v in value)
        raise ConfigError(f"{key}: expected list, got {value!r}")
    if default is None and isinstance(value, str) and value.strip() == "":
        return None
    return str(value) if not isinstance(value, (dict, list)) else value


def _build_section(cls: type, data: Mapping[str, Any] | None, section: str) -> Any:
    data = dict(data or {})
    known = {f.name: f for f in fields(cls)}
    unknown = set(data) - set(known)
    if unknown:
        raise ConfigError(f"Unknown key(s) in '{section}': {', '.join(sorted(unknown))}")
    kwargs: dict[str, Any] = {}
    for name, f in known.items():
        if name not in data:
            continue
        default = f.default if f.default is not MISSING else None
        kwargs[name] = _coerce(data[name], default, f"{section}.{name}")
    obj = cls(**kwargs)
    validate = getattr(obj, "validate", None)
    if callable(validate):
        validate()
    return obj


def _read_yaml(path: Path, *, required: bool = False) -> dict[str, Any]:
    if not path.exists():
        if required:
            raise ConfigError(f"Configuration file not found: {path}")
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path} must contain a mapping at the top level")
    return data


def _deep_merge(base: dict[str, Any], extra: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in extra.items():
        if isinstance(value, Mapping) and isinstance(out.get(key), Mapping):
            out[key] = _deep_merge(dict(out[key]), value)
        else:
            out[key] = value
    return out


def _resolve_path(value: str | Path, root: Path = PROJECT_ROOT) -> Path:
    p = Path(value).expanduser()
    return p if p.is_absolute() else (root / p)


# --------------------------------------------------------------------------- loader
def load_settings(
    config_path: str | Path | None = None,
    *,
    overrides: Mapping[str, Any] | None = None,
    use_env: bool = True,
) -> Settings:
    """Load, merge and validate settings."""
    explicit = config_path or (os.environ.get(CONFIG_ENV_VAR) if use_env else None)
    path = Path(explicit) if explicit else DEFAULT_CONFIG_DIR / "settings.yaml"
    raw = _read_yaml(path, required=bool(explicit))
    raw = interpolate_env(raw) if use_env else raw

    if use_env:
        for env_name, (section, key) in _ENV_OVERRIDES.items():
            if env_name in os.environ and os.environ[env_name] != "":
                raw.setdefault(section, {})[key] = os.environ[env_name]
    if overrides:
        raw = _deep_merge(raw, overrides)

    unknown = set(raw) - _TOP_LEVEL
    if unknown:
        raise ConfigError(f"Unknown top-level configuration key(s): {', '.join(sorted(unknown))}")

    config_dir = path.parent if path.exists() else DEFAULT_CONFIG_DIR
    files = raw.get("files") or {}
    ds_doc = _read_yaml(config_dir / files.get("datasources", "datasources.yaml"))
    alias_doc = _read_yaml(config_dir / files.get("field_aliases", "field_aliases.yaml"))

    sections = {name: _build_section(cls, raw.get(name), name) for name, cls in _SECTIONS.items()}

    catalog = sections["catalog"]
    if catalog.path != ":memory:":
        sections["catalog"] = CatalogSettings(path=str(_resolve_path(catalog.path)))
    plugins = sections["plugins"]
    sections["plugins"] = PluginSettings(
        rule_dirs=tuple(str(_resolve_path(d)) for d in plugins.rule_dirs),
        generator_dirs=tuple(str(_resolve_path(d)) for d in plugins.generator_dirs),
        collector_dirs=tuple(str(_resolve_path(d)) for d in plugins.collector_dirs),
        strict=plugins.strict,
    )

    overrides_doc = raw.get("use_case_overrides") or {}
    if not isinstance(overrides_doc, Mapping):
        raise ConfigError("use_case_overrides must be a mapping of use-case id -> attributes")

    datasources = ds_doc.get("datasources") or {}
    enrichments = ds_doc.get("enrichments") or {}
    field_aliases = alias_doc.get("fields") or {}
    metric_aliases = alias_doc.get("metrics") or {}
    for name, doc in (("datasources", datasources), ("enrichments", enrichments),
                      ("fields", field_aliases), ("metrics", metric_aliases)):
        if not isinstance(doc, Mapping):
            raise ConfigError(f"'{name}' section must be a mapping")

    settings = Settings(
        **sections,
        datasources={k: dict(v or {}) for k, v in datasources.items()},
        enrichments={k: dict(v or {}) for k, v in enrichments.items()},
        field_aliases={k: [str(a) for a in (v or [])] for k, v in field_aliases.items()},
        metric_aliases={k: [str(a) for a in (v or [])] for k, v in metric_aliases.items()},
        use_case_overrides={k: dict(v or {}) for k, v in overrides_doc.items()},
        config_dir=config_dir,
        templates_dir=_resolve_path(raw.get("templates_dir", "templates")),
    )
    log.debug("Loaded settings from %s (host=%s)", path, settings.splunk.host)
    return settings
