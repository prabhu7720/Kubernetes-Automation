"""Extract Secret / ConfigMap references from a pod spec (names only, never values)."""
from __future__ import annotations

from typing import Any, Dict, List

from .k8s_utils import all_containers, dig


def _refs(pod: Dict[str, Any], kind: str) -> Dict[str, List[str]]:
    """kind: 'secret' or 'configmap'. Returns {name: [where it is referenced]} (non-optional only)."""
    key_ref = "secretKeyRef" if kind == "secret" else "configMapKeyRef"
    from_ref = "secretRef" if kind == "secret" else "configMapRef"
    refs: Dict[str, List[str]] = {}

    def add(name, where):
        if name:
            refs.setdefault(name, []).append(where)

    for c in all_containers(pod):
        cname = c.get("name")
        for env in c.get("env") or []:
            ref = dig(env, "valueFrom", key_ref)
            if ref and not ref.get("optional"):
                add(ref.get("name"), f"env {env.get('name')} (key '{ref.get('key')}') in container {cname}")
        for env_from in c.get("envFrom") or []:
            ref = env_from.get(from_ref)
            if ref and not ref.get("optional"):
                add(ref.get("name"), f"envFrom in container {cname}")
    for vol in dig(pod, "spec", "volumes") or []:
        if kind == "secret" and vol.get("secret") and not vol["secret"].get("optional"):
            add(vol["secret"].get("secretName"), f"volume '{vol.get('name')}'")
        if kind == "configmap" and vol.get("configMap") and not vol["configMap"].get("optional"):
            add(vol["configMap"].get("name"), f"volume '{vol.get('name')}'")
        for src in dig(vol, "projected", "sources") or []:
            item = src.get("secret" if kind == "secret" else "configMap")
            if item and not item.get("optional"):
                add(item.get("name"), f"projected volume '{vol.get('name')}'")
    return refs


def secret_references(pod: Dict[str, Any]) -> Dict[str, List[str]]:
    return _refs(pod, "secret")


def configmap_references(pod: Dict[str, Any]) -> Dict[str, List[str]]:
    return _refs(pod, "configmap")


def image_pull_secret_names(pod: Dict[str, Any]) -> List[str]:
    return [s.get("name") for s in dig(pod, "spec", "imagePullSecrets") or [] if s.get("name")]
