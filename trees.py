"""Git Trees API — batch commit N files in 4 API calls instead of N individual PUTs.

Built on githubkit. Flow:
1. GET current ref SHA → get base tree SHA
2. POST new tree with all file blobs
3. POST new commit referencing new tree + parent
4. PATCH ref to point to new commit
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from githubkit import GitHub

logger = logging.getLogger(__name__)


class TreesAPI:
    """Batch file writes using Git Trees API.

    Use this instead of individual Contents API PUTs when writing
    multiple files (e.g., flushing an event buffer). Saves rate limit
    budget: 4 API calls vs N calls.
    """

    def __init__(
        self,
        gh: GitHub,
        owner: str,
        repo: str,
        default_branch: str = "main",
        default_base_ref: str = "main",
    ) -> None:
        self._gh = gh
        self._owner = owner
        self._repo = repo
        self._default_branch = default_branch
        self._default_base_ref = default_base_ref

    def _resolve_branch(self, branch: str | None) -> str:
        return branch or self._default_branch

    def _resolve_base_ref(self, base_ref: str | None) -> str:
        return base_ref or self._default_base_ref

    async def get_branch_sha(self, branch: str | None = None) -> str:
        """Get the current commit SHA of a branch."""
        selected_branch = self._resolve_branch(branch)
        resp = await self._gh.rest.git.async_get_ref(
            self._owner,
            self._repo,
            f"heads/{selected_branch}",
        )
        return resp.json()["object"]["sha"]

    @staticmethod
    def _status_code(exc: Exception) -> int | None:
        """Extract HTTP status code from githubkit-style exceptions when available."""
        response = getattr(exc, "response", None)
        return getattr(response, "status_code", None)

    async def ensure_branch_exists(
        self,
        branch: str | None = None,
        base_ref: str | None = None,
    ) -> bool:
        """Ensure a branch exists.

        Returns:
            True if branch was created, False if it already existed.
        """
        selected_branch = self._resolve_branch(branch)
        selected_base_ref = self._resolve_base_ref(base_ref)
        branch_ref = f"heads/{selected_branch}"
        try:
            await self._gh.rest.git.async_get_ref(self._owner, self._repo, branch_ref)
            return False
        except Exception as exc:
            if self._status_code(exc) != 404:
                raise

        base_ref = f"heads/{selected_base_ref}"
        base_resp = await self._gh.rest.git.async_get_ref(
            self._owner,
            self._repo,
            base_ref,
        )
        base_sha = base_resp.json()["object"]["sha"]

        try:
            await self._gh.rest.git.async_create_ref(
                self._owner,
                self._repo,
                ref=f"refs/{branch_ref}",
                sha=base_sha,
            )
            logger.info(
                "Created missing branch '%s' from '%s'",
                selected_branch,
                selected_base_ref,
            )
            return True
        except Exception as exc:
            status_code = self._status_code(exc)
            if status_code not in {409, 422}:
                raise

            # Concurrent creators may race; confirm branch now exists.
            await self._gh.rest.git.async_get_ref(self._owner, self._repo, branch_ref)
            logger.info(
                "Branch '%s' already exists",
                selected_branch,
            )
            return False

    async def batch_write(
        self,
        files: dict[str, str | bytes],
        message: str = "batch event write",
        branch: str | None = None,
    ) -> str:
        """Write multiple files in a single commit.

        Args:
            files: Mapping of file_path → content (str or bytes).
            message: Commit message.

        Returns:
            New commit SHA.
        """
        if not files:
            raise ValueError("No files to write")

        selected_branch = self._resolve_branch(branch)
        logger.info("Batch writing %d files to branch '%s'", len(files), selected_branch)

        # 1. Get current branch SHA and its tree
        branch_sha = await self.get_branch_sha(selected_branch)
        commit_resp = await self._gh.rest.git.async_get_commit(
            self._owner, self._repo, branch_sha
        )
        base_tree_sha = commit_resp.json()["tree"]["sha"]

        # 2. Build tree entries with inline content
        tree_entries = []
        for path, content in files.items():
            if isinstance(content, bytes):
                encoded = content.decode("utf-8", errors="replace")
            else:
                encoded = content
            tree_entries.append(
                {
                    "path": path,
                    "mode": "100644",
                    "type": "blob",
                    "content": encoded,
                }
            )

        # 3. Create new tree
        tree_resp = await self._gh.rest.git.async_create_tree(
            self._owner,
            self._repo,
            tree=tree_entries,
            base_tree=base_tree_sha,
        )
        new_tree_sha = tree_resp.json()["sha"]

        # 4. Create commit
        commit_resp = await self._gh.rest.git.async_create_commit(
            self._owner,
            self._repo,
            message=message,
            tree=new_tree_sha,
            parents=[branch_sha],
        )
        new_commit_sha = commit_resp.json()["sha"]

        # 5. Update branch ref
        await self._gh.rest.git.async_update_ref(
            self._owner,
            self._repo,
            f"heads/{selected_branch}",
            sha=new_commit_sha,
        )

        logger.info("Batch commit %s: %d files written", new_commit_sha[:8], len(files))
        return new_commit_sha
