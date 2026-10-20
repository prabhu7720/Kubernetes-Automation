"""Collectors fetch raw cluster state (read-only) and assemble diagnostic contexts."""
from __future__ import annotations

from config.settings import Settings
from core.kube_client import KubeClient

from .cluster_collector import ClusterCollector
from .deployment_collector import DeploymentCollector
from .event_collector import EventCollector
from .node_collector import NodeCollector
from .pod_collector import PodCollector
from .storage_collector import StorageCollector


class CollectorSet:
    """Wires collectors together so they share one client cache per run."""

    def __init__(self, client: KubeClient, settings: Settings):
        self.client = client
        self.settings = settings
        self.events = EventCollector(client, settings)
        self.nodes = NodeCollector(client, settings, self.events)
        self.deployments = DeploymentCollector(client, settings, self.events)
        self.storage = StorageCollector(client, settings, self.events)
        self.pods = PodCollector(client, settings, self.events, self.nodes, self.deployments, self.storage)
        self.cluster = ClusterCollector(client, settings, self.events, self.nodes, self.storage)


__all__ = ["CollectorSet", "EventCollector", "NodeCollector", "DeploymentCollector",
           "StorageCollector", "PodCollector", "ClusterCollector"]
