import { GitHubRepoSettings } from "./config.js";

export class WorkflowsAPI {
  constructor(gh, owner, repo, repo_settings = null) {
    this._gh = gh;
    this._owner = owner;
    this._repo = repo;
    this._repo_settings = repo_settings || new GitHubRepoSettings();
  }

  async dispatch(workflow_file, inputs, ref = null) {
    await this._gh.rest.actions.createWorkflowDispatch({
      owner: this._owner,
      repo: this._repo,
      workflow_id: workflow_file,
      ref: ref || this._repo_settings.default_workflow_ref,
      inputs,
    });
    console.info("Dispatched workflow %s with inputs %o", workflow_file, inputs);
  }

  async get_workflow_runs(workflow_file, status = "in_progress") {
    const resp = await this._gh.rest.actions.listWorkflowRuns({
      owner: this._owner,
      repo: this._repo,
      workflow_id: workflow_file,
      status,
    });
    return resp.data.workflow_runs || [];
  }

  async getWorkflowRuns(workflow_file, status = "in_progress") {
    return this.get_workflow_runs(workflow_file, status);
  }
}
