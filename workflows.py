"""GitHub Actions workflow dispatch and monitoring.

Built on githubkit.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from githubkit import GitHub

logger = logging.getLogger(__name__)
_ACTIVE_WORKFLOW_RUN_STATUSES = ("queued", "in_progress")


@dataclass(frozen=True)
class WorkflowDispatchResult:
    """Metadata returned by a workflow_dispatch request."""

    workflow_run_id: str = ""
    workflow_run_attempt: str = ""
    run_url: str = ""
    html_url: str = ""


@dataclass(frozen=True)
class WorkflowJob:
    """Metadata for a single workflow job."""

    job_id: str
    name: str = ""
    status: str = ""
    conclusion: str = ""
    run_id: str = ""
    run_attempt: str = ""
    html_url: str = ""
    url: str = ""


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


def _optional_scalar_string(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, int):
        return str(value)
    return ""


def _require_int_id(raw_value: str | int, *, field_name: str) -> int:
    if isinstance(raw_value, int):
        return raw_value
    normalized = str(raw_value or "").strip()
    if not normalized:
        raise ValueError(f"{field_name} is required")
    try:
        return int(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer: {raw_value}") from exc


def _build_workflow_job(payload: dict[str, Any]) -> WorkflowJob:
    return WorkflowJob(
        job_id=_optional_scalar_string(payload.get("id")),
        name=_optional_scalar_string(payload.get("name")),
        status=_optional_scalar_string(payload.get("status")),
        conclusion=_optional_scalar_string(payload.get("conclusion")),
        run_id=_optional_scalar_string(payload.get("run_id")),
        run_attempt=_optional_scalar_string(payload.get("run_attempt")),
        html_url=_optional_scalar_string(payload.get("html_url")),
        url=_optional_scalar_string(payload.get("url")),
    )


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
    ) -> WorkflowDispatchResult:
        """Trigger a workflow_dispatch event.

        Args:
            workflow_file: Workflow filename (e.g., "slot_01.yml").
            inputs: Input parameters for the workflow.
            ref: Git ref to run on.
        """
        selected_ref = ref or self._default_ref
        try:
            response = await self._gh.rest.actions.async_create_workflow_dispatch(
                self._owner,
                self._repo,
                workflow_file,
                ref=selected_ref,
                inputs=inputs,
                return_run_details=True,
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

        result = WorkflowDispatchResult()
        try:
            payload = response.json()
        except Exception:
            payload = None

        if isinstance(payload, dict):
            result = WorkflowDispatchResult(
                workflow_run_id=_optional_scalar_string(payload.get("workflow_run_id")),
                workflow_run_attempt=_optional_scalar_string(payload.get("workflow_run_attempt")),
                run_url=_optional_scalar_string(payload.get("run_url")),
                html_url=_optional_scalar_string(payload.get("html_url")),
            )

        logger.info(
            "Dispatched workflow %s ref=%s with input_keys=%s workflow_run_id=%s",
            workflow_file,
            selected_ref,
            sorted(str(key) for key in inputs),
            result.workflow_run_id or "(unknown)",
        )
        return result

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

    async def get_workflow_run_attempt(self, run_id: str | int) -> str:
        """Return the current attempt number for a workflow run."""
        normalized_run_id = _require_int_id(run_id, field_name="run_id")
        response = await self._gh.rest.actions.async_get_workflow_run(
            self._owner,
            self._repo,
            normalized_run_id,
        )
        payload = response.json()
        if not isinstance(payload, dict):
            return ""
        return _optional_scalar_string(payload.get("run_attempt"))

    async def list_jobs_for_workflow_run_attempt(
        self,
        run_id: str | int,
        attempt_number: str | int,
    ) -> list[WorkflowJob]:
        """List all jobs for a specific workflow run attempt."""
        normalized_run_id = _require_int_id(run_id, field_name="run_id")
        normalized_attempt = _require_int_id(attempt_number, field_name="attempt_number")
        page = 1
        jobs: list[WorkflowJob] = []

        while True:
            response = await self._gh.rest.actions.async_list_jobs_for_workflow_run_attempt(
                self._owner,
                self._repo,
                normalized_run_id,
                normalized_attempt,
                per_page=100,
                page=page,
            )
            payload = response.json()
            if not isinstance(payload, dict):
                break

            page_items = payload.get("jobs")
            if not isinstance(page_items, list):
                break

            jobs.extend(
                _build_workflow_job(item)
                for item in page_items
                if isinstance(item, dict)
            )
            if len(page_items) < 100:
                break
            page += 1

        return jobs

    async def rerun_job(
        self,
        job_id: str | int,
        *,
        enable_debug_logging: bool = False,
    ) -> None:
        """Re-run a specific workflow job and its dependent jobs."""
        normalized_job_id = _require_int_id(job_id, field_name="job_id")
        kwargs: dict[str, object] = {}
        if enable_debug_logging:
            kwargs["data"] = {"enable_debug_logging": True}
        await self._gh.rest.actions.async_re_run_job_for_workflow_run(
            self._owner,
            self._repo,
            normalized_job_id,
            **kwargs,
        )

    async def rerun_failed_jobs(
        self,
        run_id: str | int,
        *,
        enable_debug_logging: bool = False,
    ) -> None:
        """Re-run all failed jobs in a workflow run."""
        normalized_run_id = _require_int_id(run_id, field_name="run_id")
        kwargs: dict[str, object] = {}
        if enable_debug_logging:
            kwargs["data"] = {"enable_debug_logging": True}
        await self._gh.rest.actions.async_re_run_workflow_failed_jobs(
            self._owner,
            self._repo,
            normalized_run_id,
            **kwargs,
        )

    async def cancel_workflow_run(self, run_id: str | int) -> None:
        """Cancel a workflow run."""
        normalized_run_id = _require_int_id(run_id, field_name="run_id")
        await self._gh.rest.actions.async_cancel_workflow_run(
            self._owner,
            self._repo,
            normalized_run_id,
        )

    async def force_cancel_workflow_run(self, run_id: str | int) -> None:
        """Force-cancel a workflow run."""
        normalized_run_id = _require_int_id(run_id, field_name="run_id")
        await self._gh.rest.actions.async_force_cancel_workflow_run(
            self._owner,
            self._repo,
            normalized_run_id,
        )
