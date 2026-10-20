"""Parsing/formatting helpers for Kubernetes resource quantities (CPU, memory)."""
from __future__ import annotations

from typing import Optional, Union

_BINARY = {"Ki": 2 ** 10, "Mi": 2 ** 20, "Gi": 2 ** 30, "Ti": 2 ** 40, "Pi": 2 ** 50, "Ei": 2 ** 60}
_DECIMAL = {"n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "K": 1e3, "M": 1e6, "G": 1e9,
            "T": 1e12, "P": 1e15, "E": 1e18}

Number = Union[int, float]


def parse_quantity(value) -> Optional[float]:
    """Parse any Kubernetes quantity ("512Mi", "250m", "1.5", "2G", "1e3") into a float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        for suffix, mult in _BINARY.items():
            if s.endswith(suffix):
                return float(s[: -len(suffix)]) * mult
        if s[-1] in _DECIMAL:
            return float(s[:-1]) * _DECIMAL[s[-1]]
        return float(s)
    except ValueError:
        return None


def parse_memory(value) -> Optional[int]:
    """Return bytes."""
    q = parse_quantity(value)
    return int(q) if q is not None else None


def parse_cpu(value) -> Optional[int]:
    """Return millicores."""
    q = parse_quantity(value)
    return int(round(q * 1000)) if q is not None else None


def format_bytes(num: Optional[Number]) -> str:
    if num is None:
        return "n/a"
    for suffix, mult in (("Ti", 2 ** 40), ("Gi", 2 ** 30), ("Mi", 2 ** 20), ("Ki", 2 ** 10)):
        if abs(num) >= mult:
            val = num / mult
            return f"{val:.0f}{suffix}" if val == int(val) else f"{val:.1f}{suffix}"
    return f"{int(num)}B"


def format_cpu(millicores: Optional[Number]) -> str:
    if millicores is None:
        return "n/a"
    if millicores >= 1000 and millicores % 1000 == 0:
        return str(int(millicores // 1000))
    return f"{int(millicores)}m"


def pct(used: Optional[Number], total: Optional[Number]) -> Optional[float]:
    if used is None or not total:
        return None
    return round(100.0 * used / total, 1)
