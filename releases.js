import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";

export class ReleasesAPI {
  constructor(gh, owner, repo) {
    this._gh = gh;
    this._owner = owner;
    this._repo = repo;
  }

  async get_latest_release(tag_prefix = null) {
    const resp = await this._gh.rest.repos.listReleases({
      owner: this._owner,
      repo: this._repo,
    });
    const releases = resp.data;

    if (!releases || releases.length === 0) {
      return null;
    }

    if (!tag_prefix) {
      return releases[0];
    }

    for (const release of releases) {
      if (release.tag_name.startsWith(tag_prefix)) {
        return release;
      }
    }

    return null;
  }

  async create_release({
    tag_name,
    name,
    body = "",
    target_commitish = "main",
    draft = false,
    prerelease = false,
  }) {
    const resp = await this._gh.rest.repos.createRelease({
      owner: this._owner,
      repo: this._repo,
      tag_name,
      name,
      body,
      draft,
      prerelease,
      target_commitish,
    });
    return resp.data;
  }

  async upload_asset_to_release({
    upload_url,
    asset_path,
    asset_name,
    content_type = "application/octet-stream",
  }) {
    const clean_upload_url = upload_url.replace("{?name,label}", "");
    const asset_bytes = await fs.readFile(asset_path);

    const resp = await this._gh.rest.repos.uploadReleaseAsset({
      url: clean_upload_url,
      name: asset_name,
      data: asset_bytes,
      headers: {
        "content-type": content_type,
        "content-length": asset_bytes.length,
      },
    });

    const asset_url = resp.data.browser_download_url;
    console.info("Uploaded release asset %s (%d bytes)", asset_name, asset_bytes.length);
    return asset_url;
  }

  async upload_asset({
    tag_name,
    name,
    asset_path,
    asset_name,
    body = "",
    target_commitish = "main",
    draft = false,
    prerelease = false,
    content_type = "application/octet-stream",
  }) {
    const release = await this.create_release({
      tag_name,
      name,
      body,
      target_commitish,
      draft,
      prerelease,
    });

    return this.upload_asset_to_release({
      upload_url: release.upload_url,
      asset_path,
      asset_name,
      content_type,
    });
  }

  async download_asset({
    download_url,
    dest = null,
    default_filename = "release-asset.bin",
  }) {
    let target = dest;
    if (!target) {
      const temp_dir = await fs.mkdtemp(path.join(os.tmpdir(), "trystero-release-"));
      target = path.join(temp_dir, default_filename);
    }

    const token = this._gh.__auth_token || "";
    const resp = await fetch(download_url, {
      headers: {
        Authorization: `Bearer ${token}`,
      },
      redirect: "follow",
    });

    if (!resp.ok) {
      throw new Error(`Failed to download asset: ${resp.status} ${resp.statusText}`);
    }

    const bytes = Buffer.from(await resp.arrayBuffer());
    await fs.mkdir(path.dirname(target), { recursive: true });
    await fs.writeFile(target, bytes);

    console.info("Downloaded release asset to %s (%d bytes)", target, bytes.length);
    return target;
  }

  async getLatestRelease(tag_prefix = null) {
    return this.get_latest_release(tag_prefix);
  }

  async createRelease(options) {
    return this.create_release(options);
  }

  async uploadAssetToRelease(options) {
    return this.upload_asset_to_release(options);
  }

  async uploadAsset(options) {
    return this.upload_asset(options);
  }

  async downloadAsset(options) {
    return this.download_asset(options);
  }
}
