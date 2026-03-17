"""GitHub Contents API — read/write/delete individual files on state branch.

Built on githubkit. All operations are async.
"""

from __future__ import annotations

import base64
import json
import logging
from typing import TYPE_CHECKING, Any

from src.github.config import GitHubRepoSettings

if TYPE_CHECKING:
    from githubkit import GitHub

logger = logging.getLogger(__name__)


class ContentsAPI:
    """Wrapper around GitHub Contents API for the state branch.

    Critical constraints:
    - PUT and DELETE cannot run in parallel (409 conflict)
    - Max file size: 1 MB
    - Directory listing capped at 1000 entries
    - All writes require the current file SHA for updates
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

    async def read(self, file_path: str) -> tuple[str, str]:
        """Read a file from the state branch.

        Returns:
            Tuple of (decoded_content, sha).
        """
        resp = await self._gh.rest.repos.async_get_content(
            self._owner,
            self._repo,
            file_path,
            ref=self._repo_settings.state_branch,
        )
        data = resp.json()

        if isinstance(data, list):
            raise ValueError(f"Path is a directory, not a file: {file_path}")

        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]

    async def read_bytes(self, file_path: str) -> tuple[bytes, str]:
        """Read a binary file from the state branch.

        Returns:
            Tuple of (raw_bytes, sha). Unlike read(), does not decode to string.
        """
        resp = await self._gh.rest.repos.async_get_content(
            self._owner,
            self._repo,
            file_path,
            ref=self._repo_settings.state_branch,
        )
        data = resp.json()

        if isinstance(data, list):
            raise ValueError(f"Path is a directory, not a file: {file_path}")

        raw = base64.b64decode(data["content"])
        return raw, data["sha"]

    async def read_json(self, file_path: str) -> tuple[dict[str, Any], str]:
        """Read and parse a JSON file from the state branch."""
        content, sha = await self.read(file_path)
        return json.loads(content), sha

    async def write(
        self,
        file_path: str,
        content: str | bytes,
        message: str = "update",
        sha: str | None = None,
    ) -> str:
        """Write (create or update) a file on the state branch.

        Args:
            file_path: Path relative to repo root.
            content: File content (str or bytes).
            message: Commit message.
            sha: Required for updates (current file SHA). None for new files.

        Returns:
            New SHA of the written file.
        """
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content

        encoded = base64.b64encode(content_bytes).decode("ascii")

        body: dict[str, Any] = {
            "message": message,
            "content": encoded,
            "branch": self._repo_settings.state_branch,
        }
        if sha:
            body["sha"] = sha

        resp = await self._gh.rest.repos.async_create_or_update_file_contents(
            self._owner, self._repo, file_path, data=body
        )
        return resp.json()["content"]["sha"]

    async def write_json(
        self,
        file_path: str,
        data: dict[str, Any],
        message: str = "update",
        sha: str | None = None,
    ) -> str:
        """Write a JSON file to the state branch."""
        content = json.dumps(data, default=str, indent=2)
        return await self.write(file_path, content, message, sha)

    async def delete(self, file_path: str, sha: str, message: str = "delete") -> None:
        """Delete a file from the state branch."""
        await self._gh.rest.repos.async_delete_file(
            self._owner,
            self._repo,
            file_path,
            message=message,
            sha=sha,
            branch=self._repo_settings.state_branch,
        )

    async def list_dir(self, dir_path: str) -> list[dict[str, Any]]:
        """List files in a directory on the state branch.

        Note: Capped at 1000 entries. Use Git Trees API for larger directories.
        """
        resp = await self._gh.rest.repos.async_get_content(
            self._owner,
            self._repo,
            dir_path,
            ref=self._repo_settings.state_branch,
        )
        data = resp.json()
        if not isinstance(data, list):
            raise ValueError(f"Path is not a directory: {dir_path}")
        return data

    async def exists(self, file_path: str) -> bool:
        """Check if a file exists on the state branch."""
        try:
            await self.read(file_path)
            return True
        except Exception:
            return False
