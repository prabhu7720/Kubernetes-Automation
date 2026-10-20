"""Runtime settings for the agent.

Resolution order (later wins):
  1. Dataclass defaults below
  2. config/settings.yaml (or the file in $K8S_AGENT_CONFIG, or --config)
  3. CLI flags (applied in agent.py via Settings.override)
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

CONFIG_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CONFIG_DIR.parent
DEFAULT_CONFIG_PATH = CONFIG_DIR / "settings.yaml"
ENV_CONFIG = "K8S_AGENT_CONFIG"


@dataclass
class Settings:
    # collection
    log_tail_lines: int = 500
    log_limit_bytes: int = 2_000_000
    request_timeout: int = 30
    collect_logs: bool = True
    collect_metrics: bool = True
    workers: int = 4
    # triage
    restart_threshold: int = 3
    max_pods_per_deployment: int = 5
    max_pods_per_namespace: int = 25
    max_pods_cluster: int = 40
    # thresholds used by rules
    node_allocation_warn_pct: int = 90
    memory_usage_warn_pct: int = 90
    cpu_usage_warn_pct: int = 90
    quota_warn_pct: int = 90
    cert_expiry_warn_days: int = 14
    # reporting
    min_confidence: int = 0
    max_evidence_lines: int = 5
    redact_patterns: List[str] = field(default_factory=list)
    # rule management
    disabled_rules: List[str] = field(default_factory=list)
    extra_rule_dirs: List[str] = field(default_factory=list)
    rule_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    # safety
    block_network_egress: bool = True

    @classmethod
    def load(cls, path: Optional[str] = None) -> "Settings":
        explicit = path or os.environ.get(ENV_CONFIG)
        cfg_path = Path(explicit).expanduser() if explicit else DEFAULT_CONFIG_PATH
        if not cfg_path.exists():
            if explicit:
                raise FileNotFoundError(f"Config file not found: {cfg_path}")
            return cls()
        return cls.from_dict(_read_file(cfg_path, required=bool(explicit)))

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "Settings":
        data = data or {}
        if not isinstance(data, dict):
            raise ValueError("Configuration root must be a mapping")
        known = {f.name for f in fields(cls)}
        for key in sorted(set(data) - known):
            log.warning("Ignoring unknown configuration key '%s'", key)
        settings = cls(**{k: v for k, v in data.items() if k in known and v is not None})
        settings.validate()
        return settings

    def override(self, **kwargs: Any) -> "Settings":
        for key, value in kwargs.items():
            if value is not None and hasattr(self, key):
                setattr(self, key, value)
        self.validate()
        return self

    def validate(self) -> None:
        for name in ("log_tail_lines", "request_timeout", "workers", "max_pods_per_deployment",
                     "max_pods_per_namespace", "max_pods_cluster", "restart_threshold"):
            if int(getattr(self, name)) < 1:
                raise ValueError(f"Setting '{name}' must be >= 1")
        if not 0 <= int(self.min_confidence) <= 100:
            raise ValueError("min_confidence must be between 0 and 100")
        self.disabled_rules = [str(r) for r in self.disabled_rules or []]
        self.extra_rule_dirs = [str(d) for d in self.extra_rule_dirs or []]


def _read_file(path: Path, required: bool) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        return json.loads(text) or {}
    try:
        import yaml  # type: ignore
    except ImportError:
        if required:
            raise RuntimeError("PyYAML is required to read YAML config files: pip install pyyaml")
        log.info("PyYAML not installed; using built-in default settings")
        return {}
    return yaml.safe_load(text) or {}
