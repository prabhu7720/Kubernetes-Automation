"""Thin, resilient wrapper over the Splunk Python SDK (splunk-sdk / splunklib).

* lazy connection (the agent works fully offline from the cached catalog)
* token (bearer) or username/password auth, TLS verification with custom CA bundle
* retries with exponential backoff + jitter on transient failures (5xx, 429, network)
* uniform JSON helpers: ``search()`` -> list[dict], ``rest_get()`` -> list[dict]
"""

from __future__ import annotations

import functools
import json
import logging
import random
import socket
import ssl
import time
from typing import Any, Callable, Protocol, TypeVar

from core.config import SplunkSettings
from core.exceptions import SplunkConnectionError, SplunkQueryError

log = logging.getLogger(__name__)
T = TypeVar("T")


class SplunkClientProtocol(Protocol):
    """Interface used by discovery collectors (lets tests inject a fake)."""

    def search(self, spl: str, *, earliest: str | None = None, latest: str | None = None,
               max_results: int = 10000) -> list[dict[str, Any]]: ...

    def rest_get(self, path: str, **params: Any) -> list[dict[str, Any]]: ...

    def server_info(self) -> dict[str, Any]: ...


def _is_transient(exc: BaseException) -> bool:
    status = getattr(exc, "status", None)
    if isinstance(status, int):
        return status >= 500 or status == 429
    return isinstance(exc, (ConnectionError, TimeoutError, socket.timeout, ssl.SSLEOFError))


def with_retries(func: Callable[..., T]) -> Callable[..., T]:
    @functools.wraps(func)
    def wrapper(self: "SplunkClient", *args: Any, **kwargs: Any) -> T:
        attempts = self.settings.retries + 1
        delay = self.settings.retry_delay
        for attempt in range(1, attempts + 1):
            try:
                return func(self, *args, **kwargs)
            except (SplunkConnectionError, SplunkQueryError):
                raise
            except Exception as exc:  # noqa: BLE001
                if attempt >= attempts or not _is_transient(exc):
                    raise SplunkQueryError(f"{func.__name__} failed: {exc}") from exc
                sleep = delay * (2 ** (attempt - 1)) + random.uniform(0, delay / 2 or 0.1)
                log.warning("Transient Splunk error (%s); retry %d/%d in %.1fs", exc, attempt, attempts - 1, sleep)
                time.sleep(sleep)
        raise SplunkQueryError(f"{func.__name__} exhausted retries")  # pragma: no cover
    return wrapper


class SplunkClient:
    def __init__(self, settings: SplunkSettings) -> None:
        self.settings = settings
        self._service: Any = None

    # -------------------------------------------------------------- connection
    def connect(self) -> Any:
        if self._service is not None:
            return self._service
        if not self.settings.has_credentials:
            raise SplunkConnectionError(
                "No Splunk credentials configured. Set SPLUNK_TOKEN (preferred) or SPLUNK_USERNAME/SPLUNK_PASSWORD.")
        try:
            from splunklib import binding, client  # lazy: SDK only needed when online
        except ImportError as exc:  # pragma: no cover - environment specific
            raise SplunkConnectionError("splunk-sdk is not installed: pip install splunk-sdk") from exc

        context = None
        if self.settings.scheme == "https" and self.settings.verify_ssl:
            context = ssl.create_default_context(cafile=self.settings.ca_bundle) if self.settings.ca_bundle \
                else ssl.create_default_context()
        handler = binding.handler(timeout=self.settings.timeout, verify=self.settings.verify_ssl, context=context)
        kwargs: dict[str, Any] = {
            "host": self.settings.host, "port": self.settings.port, "scheme": self.settings.scheme,
            "app": self.settings.app, "owner": self.settings.owner, "handler": handler, "autologin": True,
        }
        if self.settings.token:
            kwargs["splunkToken"] = self.settings.token
        else:
            kwargs["username"] = self.settings.username
            kwargs["password"] = self.settings.password
        try:
            self._service = client.connect(**kwargs)
        except binding.AuthenticationError as exc:
            raise SplunkConnectionError("Splunk authentication failed - check credentials/token") from exc
        except (OSError, ssl.SSLError) as exc:
            raise SplunkConnectionError(
                f"Cannot reach Splunk at {self.settings.scheme}://{self.settings.host}:{self.settings.port}: {exc}") from exc
        log.info("Connected to Splunk %s:%s", self.settings.host, self.settings.port)
        return self._service

    @property
    def service(self) -> Any:
        return self.connect()

    def close(self) -> None:
        if self._service is not None and not self.settings.token:
            try:
                self._service.logout()
            except Exception:  # noqa: BLE001 - best effort
                pass
        self._service = None

    # ------------------------------------------------------------------ calls
    @with_retries
    def search(self, spl: str, *, earliest: str | None = None, latest: str | None = None,
               max_results: int = 10000) -> list[dict[str, Any]]:
        service = self.service  # connect first so auth/SDK errors surface clearly
        from splunklib import results

        query = spl.strip()
        if not query.startswith("|") and not query.lower().startswith("search "):
            query = "search " + query
        kwargs: dict[str, Any] = {"output_mode": "json", "count": max_results}
        if earliest:
            kwargs["earliest_time"] = earliest
        if latest:
            kwargs["latest_time"] = latest
        log.debug("oneshot: %s", query[:300])
        stream = service.jobs.oneshot(query, **kwargs)
        rows: list[dict[str, Any]] = []
        for item in results.JSONResultsReader(stream):
            if isinstance(item, dict):
                rows.append(item)
            elif getattr(item, "type", "") == "ERROR":
                raise SplunkQueryError(f"Search error: {item.message}")
        return rows

    @with_retries
    def rest_get(self, path: str, **params: Any) -> list[dict[str, Any]]:
        owner = params.pop("owner", "-")
        app = params.pop("app", "-")
        response = self.service.get(path, owner=owner, app=app, output_mode="json", count=0, **params)
        payload = json.loads(response.body.read() or b"{}")
        out: list[dict[str, Any]] = []
        for entry in payload.get("entry", []):
            item = dict(entry.get("content") or {})
            acl = entry.get("acl") or {}
            item.update({"name": entry.get("name"), "app": acl.get("app"), "owner": acl.get("owner"),
                         "sharing": acl.get("sharing")})
            out.append(item)
        return out

    def server_info(self) -> dict[str, Any]:
        info = self.service.info
        return {k: info.get(k) for k in ("serverName", "version", "build", "os_name", "guid")}

    def parse(self, spl: str) -> tuple[bool, str]:
        """Server-side syntax validation via the search/parser endpoint."""
        try:
            self.service.parse(spl, parse_only=True)
            return True, "ok"
        except Exception as exc:  # noqa: BLE001
            return False, str(exc)
