"""Analyzers orchestrate collection + rule evaluation for each analysis mode."""
from __future__ import annotations

from collectors import CollectorSet
from config.settings import Settings
from core.kube_client import KubeClient
from core.redact import Redactor
from core.rule_engine import RuleEngine

from .cluster_analyzer import ClusterAnalyzer, NamespaceAnalyzer, NodeAnalyzer
from .deployment_analyzer import DeploymentAnalyzer
from .pod_analyzer import PodAnalyzer


class AnalyzerSuite:
    """Builds every analyzer around one shared client cache, rule engine and redactor."""

    def __init__(self, client: KubeClient, settings: Settings, engine: RuleEngine = None):
        self.settings = settings
        self.engine = engine or RuleEngine(settings)
        self.collectors = CollectorSet(client, settings)
        redactor = Redactor(settings.redact_patterns)
        common = (self.collectors, self.engine, settings, redactor)
        self.pod = PodAnalyzer(*common)
        self.deployment = DeploymentAnalyzer(*common, pod_analyzer=self.pod)
        self.node = NodeAnalyzer(*common, pod_analyzer=self.pod)
        self.namespace = NamespaceAnalyzer(*common, pod_analyzer=self.pod, deployment_analyzer=self.deployment)
        self.cluster = ClusterAnalyzer(*common, pod_analyzer=self.pod, node_analyzer=self.node)


__all__ = ["AnalyzerSuite", "PodAnalyzer", "DeploymentAnalyzer", "NamespaceAnalyzer", "NodeAnalyzer", "ClusterAnalyzer"]
