"""GitHub Releases API wrapper.

Built on githubkit. Uses arequest() for release asset upload (uploads.github.com)
and httpx for direct asset download URLs.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from githubkit import GitHub

logger = logging.getLogger(__name__)


class ReleasesAPI:
    """Manage GitHub releases and release assets."""

    def __init__(
        self,
        gh: GitHub,
        owner: str,
        repo: str,
    ) -> None:
        self._gh = gh
        self._owner = owner
        self._repo = repo

    async def get_latest_release(self, tag_prefix: str | None = None) -> dict | None:
        """Get the latest release, optionally filtered by tag prefix."""
        resp = await self._gh.rest.repos.async_list_releases(
            self._owner, self._repo
        )
        releases = resp.json()

        if not releases:
            return None

        if not tag_prefix:
            return releases[0]

        for release in releases:
            if release["tag_name"].startswith(tag_prefix):
                return release

        return None

    async def create_release(
        self,
        *,
        tag_name: str,
        name: str,
        body: str = "",
        target_commitish: str = "main",
        draft: bool = False,
        prerelease: bool = False,
    ) -> dict:
        """Create a release and return its JSON payload."""
        resp = await self._gh.rest.repos.async_create_release(
            self._owner,
            self._repo,
            tag_name=tag_name,
            name=name,
            body=body,
            draft=draft,
            prerelease=prerelease,
            target_commitish=target_commitish,
        )
        return resp.json()

    async def upload_asset_to_release(
        self,
        *,
        upload_url: str,
        asset_path: Path,
        asset_name: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Upload a local file as an asset to an existing release.

        Returns:
            Browser download URL of the uploaded asset.
        """
        clean_upload_url = upload_url.replace("{?name,label}", "")
        asset_bytes = asset_path.read_bytes()

        resp = await self._gh.arequest(
            "POST",
            clean_upload_url,
            params={"name": asset_name},
            content=asset_bytes,
            headers={"Content-Type": content_type},
        )

        asset_url = resp.json()["browser_download_url"]
        logger.info("Uploaded release asset %s (%d bytes)", asset_name, len(asset_bytes))
        return asset_url

    async def upload_asset(
        self,
        *,
        tag_name: str,
        name: str,
        asset_path: Path,
        asset_name: str,
        body: str = "",
        target_commitish: str = "main",
        draft: bool = False,
        prerelease: bool = False,
        content_type: str = "application/octet-stream",
    ) -> str:
        """Create a release and upload an asset to it.

        Returns:
            Browser download URL of the uploaded asset.
        """
        release = await self.create_release(
            tag_name=tag_name,
            name=name,
            body=body,
            target_commitish=target_commitish,
            draft=draft,
            prerelease=prerelease,
        )
        return await self.upload_asset_to_release(
            upload_url=release["upload_url"],
            asset_path=asset_path,
            asset_name=asset_name,
            content_type=content_type,
        )

    async def download_asset(
        self,
        *,
        download_url: str,
        dest: Path | None = None,
        default_filename: str = "release-asset.bin",
    ) -> Path:
        """Download a release asset from its browser download URL."""

        if dest is None:
            dest = Path(tempfile.mkdtemp()) / default_filename

        # Download with auth via separate httpx client (different host)
        token = self._gh.auth.token if hasattr(self._gh.auth, "token") else ""
        async with httpx.AsyncClient(follow_redirects=True, timeout=120.0) as http:
            resp = await http.get(
                download_url,
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            dest.write_bytes(resp.content)

        logger.info("Downloaded release asset to %s (%d bytes)", dest, dest.stat().st_size)
        return dest
