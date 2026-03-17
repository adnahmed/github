export class GitHubRepoSettings {
  constructor({ state_branch = "state", default_workflow_ref = "main" } = {}) {
    this.state_branch = state_branch;
    this.default_workflow_ref = default_workflow_ref;
    Object.freeze(this);
  }
}
