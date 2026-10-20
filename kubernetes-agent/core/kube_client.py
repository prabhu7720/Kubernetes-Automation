"""Thin, read-only wrapper around the local ``kubectl`` binary.

Why kubectl instead of the Python client?
  * Works with every kubeconfig auth flavour out of the box (exec plugins such as
    ``aws eks get-token``, ``kubelogin``, ``gke-gcloud-auth-plugin``, OIDC, certs).
  * Zero extra Python dependencies on jump hosts / bastions.
  * The exact commands are reproducible by the operator.

Only read verbs are ever executed: get, logs, top, version, auth can-i.
Secret *values* are never requested: secret existence is checked through the
server-side table printer (``kubectl get secrets --no-headers``) which returns
names/types/counts only.
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

from .quantity import parse_cpu, parse_memory

log = logging.getLogger(__name__)

# Verbs the client is allowed to run. Acts as a safety net against misuse.
_READ_ONLY_VERBS = {"get", "logs", "top", "version", "auth", "config", "api-resources"}


class ResourceNotFound(LookupError):
    """Raised when the resource the user asked to analyze does not exist."""


class KubectlNotInstalled(RuntimeError):
    pass


class KubectlError(RuntimeError):
    def __init__(self, command: Sequence[str], returncode: int, stderr: str):
        self.command = list(command)
        self.returncode = returncode
        self.stderr = (stderr or "").strip()
        super().__init__(f"kubectl exited with code {returncode}: {self.short}")

    @property
    def short(self) -> str:
        line = self.stderr.splitlines()[0] if self.stderr else "no error output"
        return line[:300]

    @property
    def _s(self) -> str:
        return self.stderr.lower()

    @property
    def not_found(self) -> bool:
        return "(notfound)" in self._s or " not found" in self._s

    @property
    def forbidden(self) -> bool:
        return "forbidden" in self._s

    @property
    def unauthorized(self) -> bool:
        return "unauthorized" in self._s or "you must be logged in" in self._s

    @property
    def unknown_resource(self) -> bool:
        return "doesn't have a resource type" in self._s

    @property
    def connection_failed(self) -> bool:
        markers = ("unable to connect to the server", "connection refused", "no such host",
                   "i/o timeout", "tls handshake timeout", "timed out")
        return any(m in self._s for m in markers)


class KubeClient:
    """Executes kubectl with the user's kubeconfig/context and caches read results."""

    def __init__(self, kubeconfig: Optional[str] = None, context: Optional[str] = None,
                 kubectl_path: Optional[str] = None, request_timeout: int = 30,
                 log_limit_bytes: int = 2_000_000):
        self.kubectl = kubectl_path or shutil.which("kubectl")
        if not self.kubectl:
            raise KubectlNotInstalled(
                "kubectl was not found on PATH. Install it or pass --kubectl /path/to/kubectl.")
        self.kubeconfig = None
        if kubeconfig:
            path = Path(os.path.expandvars(os.path.expanduser(kubeconfig)))
            if not path.exists():
                raise FileNotFoundError(f"kubeconfig not found: {path}")
            self.kubeconfig = str(path)
        self.context = context
        self.request_timeout = int(request_timeout)
        self.log_limit_bytes = int(log_limit_bytes)
        self._cache: Dict[tuple, Any] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------ plumbing
    def base_command(self) -> List[str]:
        # A *.py "kubectl" (e.g. tests/fake_kubectl.py) is run with the current interpreter,
        # which makes the offline demo work on Windows too.
        cmd = [sys.executable, self.kubectl] if str(self.kubectl).endswith(".py") else [self.kubectl]
        if self.kubeconfig:
            cmd += ["--kubeconfig", self.kubeconfig]
        if self.context:
            cmd += ["--context", self.context]
        cmd.append(f"--request-timeout={self.request_timeout}s")
        return cmd

    def display_prefix(self) -> str:
        """kubectl prefix used in the validation commands printed in reports."""
        parts = ["kubectl"]
        if self.kubeconfig:
            parts += ["--kubeconfig", shlex.quote(self.kubeconfig)]
        if self.context:
            parts += ["--context", shlex.quote(self.context)]
        return " ".join(parts)

    def run(self, args: Sequence[str], timeout: Optional[int] = None) -> str:
        if not args or args[0] not in _READ_ONLY_VERBS:
            raise ValueError(f"Refusing to run non read-only kubectl verb: {args[:1]}")
        cmd = self.base_command() + list(args)
        log.debug("exec: %s", " ".join(shlex.quote(c) for c in cmd))
        try:
            proc = subprocess.run(
                cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                encoding="utf-8", errors="replace", check=False,
                timeout=timeout or self.request_timeout + 15,
            )
        except subprocess.TimeoutExpired:
            raise KubectlError(cmd, -1, f"kubectl timed out after {timeout or self.request_timeout + 15}s")
        except OSError as exc:
            raise KubectlError(cmd, -1, f"failed to execute kubectl: {exc}")
        if proc.returncode != 0:
            raise KubectlError(cmd, proc.returncode, proc.stderr)
        return proc.stdout

    def _cached(self, key: tuple, loader):
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        value = loader()
        with self._lock:
            self._cache[key] = value
        return value

    def clear_cache(self) -> None:
        with self._lock:
            self._cache.clear()

    # ------------------------------------------------------------------ reads
    def get_json(self, resource: str, name: Optional[str] = None, namespace: Optional[str] = None,
                 all_namespaces: bool = False, label_selector: Optional[str] = None,
                 field_selector: Optional[str] = None, cache: bool = True) -> Dict[str, Any]:
        args = ["get", resource]
        if name:
            args.append(name)
        if all_namespaces:
            args.append("--all-namespaces")
        elif namespace:
            args += ["-n", namespace]
        if label_selector:
            args += ["-l", label_selector]
        if field_selector:
            args += ["--field-selector", field_selector]
        args += ["-o", "json"]

        def load():
            out = self.run(args)
            try:
                return json.loads(out) if out.strip() else {}
            except json.JSONDecodeError as exc:
                raise KubectlError(args, 0, f"invalid JSON from kubectl: {exc}")

        return self._cached(tuple(args), load) if cache else load()

    def get(self, resource: str, name: str, namespace: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Return the object or None when it does not exist. Other errors propagate."""
        try:
            return self.get_json(resource, name=name, namespace=namespace)
        except KubectlError as exc:
            if exc.not_found and not exc.unknown_resource:
                return None
            raise

    def list(self, resource: str, namespace: Optional[str] = None, all_namespaces: bool = False,
             label_selector: Optional[str] = None, field_selector: Optional[str] = None) -> List[Dict[str, Any]]:
        data = self.get_json(resource, namespace=namespace, all_namespaces=all_namespaces,
                             label_selector=label_selector, field_selector=field_selector)
        return list(data.get("items") or [])

    def resource_names(self, resource: str, namespace: str) -> Set[str]:
        """Names only, via the server-side table printer (no secret data is transferred)."""
        args = ["get", resource, "-n", namespace, "--no-headers", "--ignore-not-found"]

        def load():
            out = self.run(args)
            return {line.split()[0] for line in out.splitlines() if line.strip()}

        return self._cached(tuple(args), load)

    def logs(self, pod: str, namespace: str, container: str, previous: bool = False,
             tail: int = 500) -> Optional[str]:
        args = ["logs", pod, "-n", namespace, "-c", container, f"--tail={int(tail)}",
                f"--limit-bytes={self.log_limit_bytes}"]
        if previous:
            args.append("--previous")
        try:
            return self.run(args)
        except KubectlError as exc:
            s = exc.stderr.lower()
            if exc.not_found or "waiting to start" in s or "previous terminated container" in s \
                    or "is terminated" in s or "podinitializing" in s:
                return None
            raise

    def top_pod(self, pod: str, namespace: str) -> Optional[Dict[str, Dict[str, int]]]:
        """Per-container usage from metrics-server, or None if unavailable."""
        try:
            out = self.run(["top", "pod", pod, "-n", namespace, "--containers", "--no-headers"])
        except KubectlError:
            return None
        usage: Dict[str, Dict[str, int]] = {}
        for line in out.splitlines():
            cols = line.split()
            if len(cols) >= 4:
                usage[cols[1]] = {"cpu_m": parse_cpu(cols[2]) or 0, "memory_bytes": parse_memory(cols[3]) or 0}
        return usage or None

    def top_nodes(self) -> Optional[Dict[str, Dict[str, int]]]:
        try:
            out = self.run(["top", "nodes", "--no-headers"])
        except KubectlError:
            return None
        usage = {}
        for line in out.splitlines():
            cols = line.split()
            if len(cols) >= 5 and not cols[1].startswith("<"):
                usage[cols[0]] = {"cpu_m": parse_cpu(cols[1]) or 0, "memory_bytes": parse_memory(cols[3]) or 0}
        return usage or None

    def server_version(self) -> Optional[str]:
        try:
            data = json.loads(self.run(["version", "-o", "json"]))
            return (data.get("serverVersion") or {}).get("gitVersion")
        except (KubectlError, json.JSONDecodeError):
            return None

    def current_context(self) -> Optional[str]:
        if self.context:
            return self.context
        try:
            return self.run(["config", "current-context"]).strip() or None
        except KubectlError:
            return None

    def can_i(self, verb: str, resource: str, namespace: Optional[str] = None,
              as_user: Optional[str] = None) -> Optional[bool]:
        args = ["auth", "can-i", verb, resource]
        if namespace:
            args += ["-n", namespace]
        if as_user:
            args += ["--as", as_user]
        try:
            return self.run(args).strip().lower().startswith("yes")
        except KubectlError as exc:
            if exc.stderr.strip().lower().startswith("no") or exc.returncode == 1:
                return False
            return None
