"""Exception hierarchy for the Splunk agent.

Every error raised intentionally by the agent derives from ``SplunkAgentError`` so
callers (CLI, automation, CI jobs) can catch a single base class.
"""

from __future__ import annotations


class SplunkAgentError(Exception):
    """Base class for all agent errors."""

    exit_code: int = 1


class ConfigError(SplunkAgentError):
    """Invalid or missing configuration."""

    exit_code = 2


class SplunkConnectionError(SplunkAgentError):
    """The Splunk management API could not be reached or authentication failed."""

    exit_code = 3


class SplunkQueryError(SplunkAgentError):
    """A search or REST call returned an error."""

    exit_code = 3


class DiscoveryError(SplunkAgentError):
    """A discovery collector failed."""


class CatalogError(SplunkAgentError):
    """Metadata catalog read/write failure."""


class PluginLoadError(SplunkAgentError):
    """A rule/generator/collector plugin could not be loaded."""


class IntentResolutionError(SplunkAgentError):
    """The natural-language request could not be mapped to a capability."""

    exit_code = 2

    def __init__(self, message: str, suggestions: list[str] | tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.suggestions = list(suggestions)


class TemplateRenderError(SplunkAgentError):
    """A rule template referenced an unknown placeholder or parameter."""


class GenerationError(SplunkAgentError):
    """An artifact could not be generated."""


class ValidationError(SplunkAgentError):
    """Generated SPL failed validation (strict mode)."""


class PublishError(SplunkAgentError):
    """Publishing an artifact to Splunk failed."""
