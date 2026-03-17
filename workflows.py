"""GitHub Actions workflow dispatch and monitoring.

Built on githubkit.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.github.config import GitHubRepoSettings

if TYPE_CHECKING:
    from githubkit import GitHub

logger = logging.getLogger(__name__)


class WorkflowsAPI:
    """Dispatch and monitor GitHub Actions workflows."""

    def __init__(
        self,
        gh: GitHub,
        owner: str,
        repo: str,
        repo_settings: GitHubRepoSettings | None = None,
    ) -> None:
        self._gh = gh
        self._owner = owner
        self._repo = repo
        self._repo_settings = repo_settings or GitHubRepoSettings()

    async def dispatch(
        self,
        workflow_file: str,
        inputs: dict[str, str],
        ref: str | None = None,
    ) -> None:
        """Trigger a workflow_dispatch event.

        Args:
            workflow_file: Workflow filename (e.g., "slot_01.yml").
            inputs: Input parameters for the workflow.
            ref: Git ref to run on.
        """
        await self._gh.rest.actions.async_create_workflow_dispatch(
            self._owner,
            self._repo,
            workflow_file,
            ref=ref or self._repo_settings.default_workflow_ref,
            inputs=inputs,
        )
        logger.info("Dispatched workflow %s with inputs %s", workflow_file, inputs)

    async def get_workflow_runs(
        self,
        workflow_file: str,
        status: str = "in_progress",
    ) -> list[dict]:
        """List workflow runs filtered by status."""
        resp = await self._gh.rest.actions.async_list_workflow_runs(
            self._owner, self._repo, workflow_file, status=status
        )
        return resp.json().get("workflow_runs", [])
