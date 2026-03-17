import { GitHubRepoSettings } from "./config.js";

function is_array(value) {
  return Array.isArray(value);
}

export class ContentsAPI {
  constructor(gh, owner, repo, repo_settings = null) {
    this._gh = gh;
    this._owner = owner;
    this._repo = repo;
    this._repo_settings = repo_settings || new GitHubRepoSettings();
  }

  async read(file_path) {
    const resp = await this._gh.rest.repos.getContent({
      owner: this._owner,
      repo: this._repo,
      path: file_path,
      ref: this._repo_settings.state_branch,
    });
    const data = resp.data;

    if (is_array(data)) {
      throw new Error(`Path is a directory, not a file: ${file_path}`);
    }

    const content = Buffer.from(data.content, "base64").toString("utf-8");
    return [content, data.sha];
  }

  async read_bytes(file_path) {
    const resp = await this._gh.rest.repos.getContent({
      owner: this._owner,
      repo: this._repo,
      path: file_path,
      ref: this._repo_settings.state_branch,
    });
    const data = resp.data;

    if (is_array(data)) {
      throw new Error(`Path is a directory, not a file: ${file_path}`);
    }

    const raw = Buffer.from(data.content, "base64");
    return [raw, data.sha];
  }

  async read_json(file_path) {
    const [content, sha] = await this.read(file_path);
    return [JSON.parse(content), sha];
  }

  async write(file_path, content, message = "update", sha = null) {
    const content_bytes = typeof content === "string" ? Buffer.from(content, "utf-8") : Buffer.from(content);
    const encoded = content_bytes.toString("base64");

    const body = {
      owner: this._owner,
      repo: this._repo,
      path: file_path,
      message,
      content: encoded,
      branch: this._repo_settings.state_branch,
    };

    if (sha) {
      body.sha = sha;
    }

    const resp = await this._gh.rest.repos.createOrUpdateFileContents(body);
    return resp.data.content.sha;
  }

  async write_json(file_path, data, message = "update", sha = null) {
    const content = JSON.stringify(
      data,
      (_key, value) => {
        if (typeof value === "bigint") {
          return value.toString();
        }
        if (typeof value === "symbol" || typeof value === "function") {
          return String(value);
        }
        return value;
      },
      2
    );
    return this.write(file_path, content, message, sha);
  }

  async delete(file_path, sha, message = "delete") {
    await this._gh.rest.repos.deleteFile({
      owner: this._owner,
      repo: this._repo,
      path: file_path,
      message,
      sha,
      branch: this._repo_settings.state_branch,
    });
  }

  async list_dir(dir_path) {
    const resp = await this._gh.rest.repos.getContent({
      owner: this._owner,
      repo: this._repo,
      path: dir_path,
      ref: this._repo_settings.state_branch,
    });
    const data = resp.data;
    if (!is_array(data)) {
      throw new Error(`Path is not a directory: ${dir_path}`);
    }
    return data;
  }

  async exists(file_path) {
    try {
      await this.read(file_path);
      return true;
    } catch (_err) {
      return false;
    }
  }

  async readBytes(file_path) {
    return this.read_bytes(file_path);
  }

  async readJson(file_path) {
    return this.read_json(file_path);
  }

  async writeJson(file_path, data, message = "update", sha = null) {
    return this.write_json(file_path, data, message, sha);
  }

  async listDir(dir_path) {
    return this.list_dir(dir_path);
  }
}
