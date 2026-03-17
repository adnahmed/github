import { GitHubRepoSettings } from "./config.js";

export class TreesAPI {
  constructor(gh, owner, repo, repo_settings = null) {
    this._gh = gh;
    this._owner = owner;
    this._repo = repo;
    this._repo_settings = repo_settings || new GitHubRepoSettings();
  }

  async get_branch_sha() {
    const resp = await this._gh.rest.git.getRef({
      owner: this._owner,
      repo: this._repo,
      ref: `heads/${this._repo_settings.state_branch}`,
    });
    return resp.data.object.sha;
  }

  async batch_write(files, message = "batch event write") {
    const entries = Object.entries(files || {});
    if (entries.length === 0) {
      throw new Error("No files to write");
    }

    console.info("Batch writing %d files to state branch", entries.length);

    const branch_sha = await this.get_branch_sha();
    const commit_resp = await this._gh.rest.git.getCommit({
      owner: this._owner,
      repo: this._repo,
      commit_sha: branch_sha,
    });
    const base_tree_sha = commit_resp.data.tree.sha;

    const tree_entries = [];
    for (const [file_path, content] of entries) {
      const encoded =
        typeof content === "string"
          ? content
          : Buffer.from(content).toString("utf-8");
      tree_entries.push({
        path: file_path,
        mode: "100644",
        type: "blob",
        content: encoded,
      });
    }

    const tree_resp = await this._gh.rest.git.createTree({
      owner: this._owner,
      repo: this._repo,
      tree: tree_entries,
      base_tree: base_tree_sha,
    });
    const new_tree_sha = tree_resp.data.sha;

    const new_commit_resp = await this._gh.rest.git.createCommit({
      owner: this._owner,
      repo: this._repo,
      message,
      tree: new_tree_sha,
      parents: [branch_sha],
    });
    const new_commit_sha = new_commit_resp.data.sha;

    await this._gh.rest.git.updateRef({
      owner: this._owner,
      repo: this._repo,
      ref: `heads/${this._repo_settings.state_branch}`,
      sha: new_commit_sha,
    });

    console.info("Batch commit %s: %d files written", new_commit_sha.slice(0, 8), entries.length);
    return new_commit_sha;
  }

  async getBranchSha() {
    return this.get_branch_sha();
  }

  async batchWrite(files, message = "batch event write") {
    return this.batch_write(files, message);
  }
}
