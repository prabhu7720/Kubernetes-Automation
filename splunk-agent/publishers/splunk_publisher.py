"""Idempotent publishing of saved searches/alerts/correlation searches and Studio dashboards."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote

from core.config import PublishSettings
from core.exceptions import PublishError

log = logging.getLogger(__name__)


@dataclass
class PublishResult:
    kind: str
    name: str
    action: str  # created | updated | skipped | dry_run | failed
    ok: bool = True
    message: str = ""
    payload: dict[str, Any] = field(default_factory=dict, repr=False)


def _status(exc: BaseException) -> int | None:
    return getattr(exc, "status", None)


class SplunkPublisher:
    def __init__(self, client: Any, settings: PublishSettings) -> None:
        self.client = client
        self.settings = settings

    @property
    def _ns(self) -> dict[str, str]:
        return {"owner": self.settings.owner, "app": self.settings.app, "sharing": self.settings.sharing}

    def _exists(self, path: str) -> bool:
        try:
            self.client.service.get(path, **self._ns)
            return True
        except Exception as exc:  # noqa: BLE001
            if _status(exc) == 404:
                return False
            raise PublishError(f"Cannot check {path}: {exc}") from exc

    def _upsert(self, kind: str, collection: str, name: str, payload: dict[str, Any], dry_run: bool) -> PublishResult:
        if dry_run:
            return PublishResult(kind, name, "dry_run", True, f"Would upsert {collection}/{name}", payload)
        item_path = f"{collection}/{quote(name, safe='')}"
        try:
            if self._exists(item_path):
                if not self.settings.overwrite:
                    return PublishResult(kind, name, "skipped", True, "exists (publish.overwrite=false)", payload)
                self.client.service.post(item_path, **self._ns, **payload)
                action = "updated"
            else:
                self.client.service.post(collection, **self._ns, name=name, **payload)
                action = "created"
        except PublishError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.error("Publishing %s '%s' failed: %s", kind, name, exc)
            return PublishResult(kind, name, "failed", False, str(exc), payload)
        log.info("%s %s '%s' in app %s", action.title(), kind, name, self.settings.app)
        return PublishResult(kind, name, action, True, f"{action} in {self.settings.app}", payload)

    def publish_saved_search(self, name: str, params: dict[str, Any], *, kind: str = "saved_search",
                             dry_run: bool = True) -> PublishResult:
        if "search" not in params:
            raise PublishError(f"{name}: saved search payload has no 'search'")
        return self._upsert(kind, "saved/searches", name, dict(params), dry_run)

    def publish_dashboard(self, name: str, xml: str, *, dry_run: bool = True) -> PublishResult:
        return self._upsert("dashboard", "data/ui/views", name, {"eai:data": xml}, dry_run)
