import type { GitHubRepoSettings } from "./config.js";

export class ContentsAPI {
  constructor(
    gh: unknown,
    owner: string,
    repo: string,
    repo_settings?: GitHubRepoSettings | null
  );

  read(file_path: string): Promise<[string, string]>;
  read_bytes(file_path: string): Promise<[Buffer, string]>;
  read_json(file_path: string): Promise<[Record<string, unknown>, string]>;
  write(
    file_path: string,
    content: string | Buffer | Uint8Array,
    message?: string,
    sha?: string | null
  ): Promise<string>;
  write_json(
    file_path: string,
    data: Record<string, unknown>,
    message?: string,
    sha?: string | null
  ): Promise<string>;
  delete(file_path: string, sha: string, message?: string): Promise<void>;
  list_dir(dir_path: string): Promise<Array<Record<string, unknown>>>;
  exists(file_path: string): Promise<boolean>;

  readBytes(file_path: string): Promise<[Buffer, string]>;
  readJson(file_path: string): Promise<[Record<string, unknown>, string]>;
  writeJson(
    file_path: string,
    data: Record<string, unknown>,
    message?: string,
    sha?: string | null
  ): Promise<string>;
  listDir(dir_path: string): Promise<Array<Record<string, unknown>>>;
}
