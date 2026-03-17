import type { GitHubRepoSettings } from "./config.js";

export class WorkflowsAPI {
  constructor(
    gh: unknown,
    owner: string,
    repo: string,
    repo_settings?: GitHubRepoSettings | null
  );

  dispatch(workflow_file: string, inputs: Record<string, string>, ref?: string | null): Promise<void>;
  get_workflow_runs(workflow_file: string, status?: string): Promise<Array<Record<string, unknown>>>;

  getWorkflowRuns(workflow_file: string, status?: string): Promise<Array<Record<string, unknown>>>;
}
