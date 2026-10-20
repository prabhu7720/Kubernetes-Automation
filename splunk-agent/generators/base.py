"""Generator plugin contract.

``SearchGenerator`` (always available) turns a use case into SPL.  Everything else
- reports, alerts, dashboards, correlation searches, runbooks - is an
:class:`ArtifactGenerator` plugin: drop a module into ``generators/`` that subclasses
it, set ``name``, implement ``applies``/``generate`` and the agent emits the new
artifact for every matching request.
"""

from __future__ import annotations

import inspect
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Iterable

from core.intent import Intent
from core.models import ArtifactType, DashboardBlueprint, UseCase
from core.plugins import load_plugins

if TYPE_CHECKING:  # pragma: no cover
    from catalog.metadata_store import MetadataStore
    from core.config import Settings
    from core.templates import TemplateStore
    from generators.dashboard_generator import DashboardComponent
    from generators.search_generator import GeneratedSearch, SearchGenerator
    from rules.base import RuleRegistry

log = logging.getLogger(__name__)


class Artifact(ABC):
    kind: ClassVar[str] = ""
    title: str

    @abstractmethod
    def to_dict(self) -> dict[str, Any]: ...

    def files(self) -> dict[str, str]:
        """Files to write for this artifact (relative name -> content)."""
        return {}

    def to_markdown(self) -> str:
        return ""


@dataclass
class GeneratorServices:
    settings: "Settings"
    store: "MetadataStore"
    registry: "RuleRegistry"
    search_generator: "SearchGenerator"
    templates: "TemplateStore"


@dataclass
class GenerationRequest:
    intent: Intent
    title: str
    use_case: UseCase
    search: "GeneratedSearch"
    use_cases: list[UseCase] = field(default_factory=list)
    searches: dict[str, "GeneratedSearch"] = field(default_factory=dict)
    components: list["DashboardComponent"] = field(default_factory=list)
    blueprint: DashboardBlueprint | None = None

    @property
    def artifact_type(self) -> ArtifactType:
        return self.intent.artifact_type


class ArtifactGenerator(ABC):
    name: ClassVar[str] = ""
    order: ClassVar[int] = 100
    _registry: ClassVar[dict[str, type["ArtifactGenerator"]]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if cls.__dict__.get("name") and not inspect.isabstract(cls):
            ArtifactGenerator._registry[cls.name] = cls

    def __init__(self, services: GeneratorServices) -> None:
        self.services = services

    @abstractmethod
    def applies(self, request: GenerationRequest) -> bool: ...

    @abstractmethod
    def generate(self, request: GenerationRequest) -> Artifact | None: ...

    @classmethod
    def load_all(cls, services: GeneratorServices, extra_dirs: Iterable[str] = (), *,
                 strict: bool = False) -> list["ArtifactGenerator"]:
        load_plugins("generators", extra_dirs, strict=strict, skip=("base",))
        gens = [g(services) for g in cls._registry.values()]
        return sorted(gens, key=lambda g: (g.order, g.name))
