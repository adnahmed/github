import type { GitHubRepoSettings } from "./config.js";

export class TreesAPI {
  constructor(
    gh: unknown,
    owner: string,
    repo: string,
    repo_settings?: GitHubRepoSettings | null
  );

  get_branch_sha(): Promise<string>;
  batch_write(files: Record<string, string | Buffer | Uint8Array>, message?: string): Promise<string>;

  getBranchSha(): Promise<string>;
  batchWrite(files: Record<string, string | Buffer | Uint8Array>, message?: string): Promise<string>;
}
