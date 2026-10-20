"""Core building blocks of the Kubernetes Diagnostic Agent.

Nothing in this package talks to the network directly. The only I/O performed
is executing the local ``kubectl`` binary (see :mod:`core.kube_client`), which
authenticates with your existing kubeconfig and talks exclusively to the
Kubernetes API servers defined there.
"""

__version__ = "1.0.0"
