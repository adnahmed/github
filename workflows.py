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


def _status_code_from_exc(exc: Exception) -> int | None:
    response = getattr(exc, "response", None)
    status_code = getattr(response, "status_code", None)
    if isinstance(status_code, int):
        return status_code
    return None


def _detail_from_exc(exc: Exception) -> str:
    response = getattr(exc, "response", None)
    if response is None:
        return ""

    data_model = getattr(response, "data_model", None)
    if data_model not in (None, ""):
        return str(data_model)

    message = getattr(response, "message", None)
    if isinstance(message, str) and message.strip():
        return message.strip()

    json_loader = getattr(response, "json", None)
    if callable(json_loader):
        try:
            payload = json_loader()
        except Exception:
            payload = None
        if isinstance(payload, (dict, list, str, int, float, bool)):
            return str(payload)

    text = getattr(response, "text", None)
    if isinstance(text, str) and text.strip():
        return text.strip()

    return ""


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
        selected_ref = ref or self._default_ref
        try:
            await self._gh.rest.actions.async_create_workflow_dispatch(
                self._owner,
                self._repo,
                workflow_file,
                ref=selected_ref,
                inputs=inputs,
            )
        except Exception as exc:
            status_code = _status_code_from_exc(exc)
            detail = _detail_from_exc(exc)
            logger.error(
                "Workflow dispatch failed workflow=%s ref=%s status=%s input_keys=%s detail=%s",
                workflow_file,
                selected_ref,
                status_code,
                sorted(str(key) for key in inputs),
                detail or "(none)",
            )
            raise

        logger.info(
            "Dispatched workflow %s ref=%s with input_keys=%s",
            workflow_file,
            selected_ref,
            sorted(str(key) for key in inputs),
        )

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
