"""Base class for collectors: shared client/settings + uniform error capture."""
from __future__ import annotations

import logging
from typing import Any, Callable, List

from config.settings import Settings
from core.kube_client import KubeClient, KubectlError


class BaseCollector:
    def __init__(self, client: KubeClient, settings: Settings):
        self.client = client
        self.settings = settings
        self.log = logging.getLogger(self.__class__.__module__)

    @staticmethod
    def describe_error(description: str, exc: KubectlError) -> str:
        if exc.forbidden:
            return f"{description}: permission denied (RBAC forbidden) - {exc.short}"
        if exc.unauthorized:
            return f"{description}: unauthorized - kubeconfig credentials rejected/expired"
        return f"{description}: {exc.short}"

    def safe(self, errors: List[str], description: str, fn: Callable[..., Any], *args,
             default: Any = None, **kwargs) -> Any:
        """Run a collection step; on failure record a warning and return ``default``.

        Partial data is better than no report: a missing permission for, e.g.,
        nodes must not prevent pod analysis.
        """
        try:
            return fn(*args, **kwargs)
        except KubectlError as exc:
            if exc.not_found and not exc.unknown_resource:
                return default
            if exc.connection_failed:
                raise  # cluster unreachable: abort, nothing useful can be produced
            msg = self.describe_error(description, exc)
            self.log.debug(msg)
            errors.append(msg)
            return default
