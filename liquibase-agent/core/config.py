"""Profile / configuration loading (JSON, stdlib only)."""
from __future__ import annotations

import copy
import json
import os
from typing import Optional

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_DIR = os.path.join(HERE, "config")


def deep_merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _read(path):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    data.pop("_comment", None)
    return data


def load_profile(name_or_path: Optional[str] = None) -> dict:
    prof = _read(os.path.join(CONFIG_DIR, "default.json"))
    if not name_or_path or name_or_path == "default":
        prof["_name"] = "default"
        return prof
    path = name_or_path
    if not os.path.isfile(path):
        path = os.path.join(CONFIG_DIR, "profiles", f"{name_or_path}.json")
    if not os.path.isfile(path):
        avail = ", ".join(sorted(f[:-5] for f in os.listdir(os.path.join(CONFIG_DIR, "profiles")) if f.endswith(".json")))
        raise FileNotFoundError(f"Profile '{name_or_path}' not found. Available: default, {avail}")
    over = _read(path)
    parent = over.pop("extends", None)
    if parent and parent != "default":
        prof = load_profile(parent)
    prof = deep_merge(prof, over)
    prof["_name"] = os.path.splitext(os.path.basename(path))[0]
    return prof
