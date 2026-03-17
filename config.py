"""Configuration defaults for the reusable GitHub API layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class GitHubRepoSettings:
    """Repository-specific defaults used by the GitHub API wrappers.

    These defaults match the current jobs repository, but the settings object
    can be overridden by other consumers when this package is extracted.
    """

    state_branch: str = "state"
    default_workflow_ref: str = "main"