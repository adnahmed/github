export class ReleasesAPI {
  constructor(gh: unknown, owner: string, repo: string);

  get_latest_release(tag_prefix?: string | null): Promise<Record<string, unknown> | null>;
  create_release(options: {
    tag_name: string;
    name: string;
    body?: string;
    target_commitish?: string;
    draft?: boolean;
    prerelease?: boolean;
  }): Promise<Record<string, unknown>>;
  upload_asset_to_release(options: {
    upload_url: string;
    asset_path: string;
    asset_name: string;
    content_type?: string;
  }): Promise<string>;
  upload_asset(options: {
    tag_name: string;
    name: string;
    asset_path: string;
    asset_name: string;
    body?: string;
    target_commitish?: string;
    draft?: boolean;
    prerelease?: boolean;
    content_type?: string;
  }): Promise<string>;
  download_asset(options: {
    download_url: string;
    dest?: string | null;
    default_filename?: string;
  }): Promise<string>;

  getLatestRelease(tag_prefix?: string | null): Promise<Record<string, unknown> | null>;
  createRelease(options: {
    tag_name: string;
    name: string;
    body?: string;
    target_commitish?: string;
    draft?: boolean;
    prerelease?: boolean;
  }): Promise<Record<string, unknown>>;
  uploadAssetToRelease(options: {
    upload_url: string;
    asset_path: string;
    asset_name: string;
    content_type?: string;
  }): Promise<string>;
  uploadAsset(options: {
    tag_name: string;
    name: string;
    asset_path: string;
    asset_name: string;
    body?: string;
    target_commitish?: string;
    draft?: boolean;
    prerelease?: boolean;
    content_type?: string;
  }): Promise<string>;
  downloadAsset(options: {
    download_url: string;
    dest?: string | null;
    default_filename?: string;
  }): Promise<string>;
}
