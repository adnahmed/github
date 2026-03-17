"""Shared GitHub client factory built on githubkit.

Replaces the hand-rolled httpx client + RateLimitTracker with githubkit's
built-in rate limiting, retry, HTTP caching, and throttling.
"""

from __future__ import annotations

import os
import logging
from datetime import timedelta

import httpx
from githubkit import GitHub, TokenAuthStrategy, ActionAuthStrategy
from githubkit.retry import RetryChainDecision, RetryRateLimit, RetryServerError, RetryOption
from githubkit.exception import GitHubException
from githubkit.throttling import LocalThrottler

logger = logging.getLogger(__name__)


def _conflict_retry(exc: GitHubException, retry_count: int) -> RetryOption:
    """Short retry on 409 Conflict (concurrent writes to same ref)."""
    from githubkit.exception import RequestFailed

    if isinstance(exc, RequestFailed) and exc.response.status_code == 409:
        if retry_count < 3:
            return RetryOption(True, timedelta(seconds=min(2 ** retry_count, 5)))
    return RetryOption(False)


def create_github_client(token: str | None = None) -> GitHub:
    """Create a configured githubkit client.

    Auto-detects GitHub Actions environment (GITHUB_TOKEN env var).
    Falls back to explicit token authentication.

    Args:
        token: GitHub PAT / gho_* OAuth token. If None, checks environment.

    Returns:
        Configured githubkit GitHub instance.
    """
    # Resolve token: explicit > GITHUB_TOKEN env var
    resolved_token = token or os.environ.get("GITHUB_TOKEN")

    if not resolved_token:
        raise ValueError("No GitHub token provided and GITHUB_TOKEN env var is not set")

    # Detect GitHub Actions environment for built-in auth
    if os.environ.get("GITHUB_ACTIONS") == "true" and not token:
        auth = ActionAuthStrategy()
        logger.info("Using GitHub Actions built-in authentication")
    else:
        auth = TokenAuthStrategy(resolved_token)

    return GitHub(
        auth,
        timeout=httpx.Timeout(30.0),
        http_cache=True,
        auto_retry=RetryChainDecision(
            RetryRateLimit(max_retry=3),
            RetryServerError(max_retry=3),
            _conflict_retry,
        ),
        throttler=LocalThrottler(100),
        follow_redirects=True,
    )
