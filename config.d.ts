export class GitHubRepoSettings {
  readonly state_branch: string;
  readonly default_workflow_ref: string;
  constructor(options?: {
    state_branch?: string;
    default_workflow_ref?: string;
  });
}
