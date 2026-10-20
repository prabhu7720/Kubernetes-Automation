"""Hard guarantee that the agent's Python process cannot open network connections.

The agent never needs the network itself: all cluster access goes through the
``kubectl`` subprocess, which uses your kubeconfig to reach the API server.
Installing this guard makes any accidental outbound connection (a stray
library, a future contributor adding an HTTP call, an LLM SDK, telemetry...)
fail loudly instead of silently leaking cluster data.
"""
from __future__ import annotations

import socket

_installed = False


class ExternalEgressBlocked(PermissionError):
    pass


def _deny(address):
    raise ExternalEgressBlocked(
        f"Outbound network access to {address!r} was blocked. The Kubernetes Diagnostic Agent "
        "never sends data off-host; only the kubectl subprocess talks to your API server."
    )


def install() -> None:
    global _installed
    if _installed:
        return
    original_connect = socket.socket.connect
    original_connect_ex = socket.socket.connect_ex

    def guarded_connect(self, address):
        if getattr(socket, "AF_UNIX", None) is not None and self.family == socket.AF_UNIX:
            return original_connect(self, address)
        _deny(address)

    def guarded_connect_ex(self, address):
        if getattr(socket, "AF_UNIX", None) is not None and self.family == socket.AF_UNIX:
            return original_connect_ex(self, address)
        _deny(address)

    def guarded_getaddrinfo(host, *args, **kwargs):
        _deny(host)

    socket.socket.connect = guarded_connect          # type: ignore[assignment]
    socket.socket.connect_ex = guarded_connect_ex    # type: ignore[assignment]
    socket.getaddrinfo = guarded_getaddrinfo         # type: ignore[assignment]
    _installed = True


def is_installed() -> bool:
    return _installed
