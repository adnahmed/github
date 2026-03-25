"""GitHub Actions workflow dispatch and monitoring.

Built on githubkit.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from githubkit import GitHub

logger = logging.getLogger(__name__)
_ACTIVE_WORKFLOW_RUN_STATUSES = ("queued", "in_progress")


def _run_identity_strings(run: dict[str, Any]) -> set[str]:
    identities: set[str] = set()
    raw_run_id = run.get("id")
    if raw_run_id in (None, ""):
        return identities

    normalized_run_id = str(raw_run_id)
    identities.add(normalized_run_id)

    raw_attempt = run.get("run_attempt")
    if raw_attempt not in (None, ""):
        identities.add(f"{normalized_run_id}-{raw_attempt}")

    return identities


class WorkflowsAPI:
    """Dispatch and monitor GitHub Actions workflows."""

    def __init__(
        self,
        gh: GitHub,
        owner: str,
        repo: str,
        default_ref: str = "main",
    ) -> None:
        self._gh = gh
        self._owner = owner
        self._repo = repo
        self._default_ref = default_ref

    async def dispatch(
        self,
        workflow_file: str,
        inputs: dict[str, Any],
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
            ref=ref or self._default_ref,
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

    async def get_active_run_ids(
        self,
        workflow_file: str,
        statuses: tuple[str, ...] = _ACTIVE_WORKFLOW_RUN_STATUSES,
    ) -> set[str]:
        """Return run-id strings for currently active runs of a workflow.

        Includes both raw run IDs (for legacy heartbeats) and "<run_id>-<attempt>"
        identities that match workers using GITHUB_RUN_ATTEMPT in their run_id.
        """
        active_run_ids: set[str] = set()
        last_error: Exception | None = None
        successful_queries = 0

        for status in statuses:
            try:
                runs = await self.get_workflow_runs(workflow_file, status=status)
            except Exception as exc:
                last_error = exc
                logger.warning(
                    "Failed to list workflow runs for %s status=%s: %s",
                    workflow_file,
                    status,
                    exc,
                )
                continue

            successful_queries += 1
            for run in runs:
                if isinstance(run, dict):
                    active_run_ids.update(_run_identity_strings(run))

        if successful_queries == 0 and last_error is not None:
            raise RuntimeError(
                f"failed to query active runs for {workflow_file}"
            ) from last_error

        return active_run_ids
