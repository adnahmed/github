import { Octokit } from "octokit";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function create_github_client(token = null) {
  const resolved_token = token || process.env.GITHUB_TOKEN;

  if (!resolved_token) {
    throw new Error("No GitHub token provided and GITHUB_TOKEN env var is not set");
  }

  if (process.env.GITHUB_ACTIONS === "true" && !token) {
    console.info("Using GitHub Actions built-in authentication");
  }

  const gh = new Octokit({
    auth: resolved_token,
    request: {
      timeout: 30000,
      retries: 3,
    },
    retry: {
      doNotRetry: [400, 401, 403, 404, 422],
    },
    throttle: {
      onRateLimit: (retryAfter, options, octokit, retryCount) => {
        if (retryCount < 3) {
          octokit.log.warn(
            `Rate limit exceeded for ${options.method} ${options.url}; retrying after ${retryAfter}s`
          );
          return true;
        }
        return false;
      },
      onSecondaryRateLimit: (retryAfter, options, octokit) => {
        octokit.log.warn(
          `Secondary rate limit for ${options.method} ${options.url}; retrying after ${retryAfter}s`
        );
        return true;
      },
    },
  });

  gh.__auth_token = resolved_token;

  gh.hook.wrap("request", async (request, options) => {
    let retry_count = 0;
    for (;;) {
      try {
        return await request(options);
      } catch (err) {
        if (err && err.status === 409 && retry_count < 3) {
          const wait_seconds = Math.min(2 ** retry_count, 5);
          retry_count += 1;
          await sleep(wait_seconds * 1000);
          continue;
        }
        throw err;
      }
    }
  });

  return gh;
}
