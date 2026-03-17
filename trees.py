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

from src.github.config import GitHubRepoSettings

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
        repo_settings: GitHubRepoSettings | None = None,
    ) -> None:
        self._gh = gh
        self._owner = owner
        self._repo = repo
        self._repo_settings = repo_settings or GitHubRepoSettings()

    async def get_branch_sha(self) -> str:
        """Get the current commit SHA of the state branch."""
        resp = await self._gh.rest.git.async_get_ref(
            self._owner,
            self._repo,
            f"heads/{self._repo_settings.state_branch}",
        )
        return resp.json()["object"]["sha"]

    async def batch_write(
        self,
        files: dict[str, str | bytes],
        message: str = "batch event write",
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

        logger.info("Batch writing %d files to state branch", len(files))

        # 1. Get current branch SHA and its tree
        branch_sha = await self.get_branch_sha()
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
            f"heads/{self._repo_settings.state_branch}",
            sha=new_commit_sha,
        )

        logger.info("Batch commit %s: %d files written", new_commit_sha[:8], len(files))
        return new_commit_sha
