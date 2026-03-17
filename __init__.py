"""GitHub API layer — built on githubkit.

Usage:
    from src.github.client import create_github_client
    gh = create_github_client(token)

    from src.github.contents import ContentsAPI
    contents = ContentsAPI(gh, owner, repo)
"""

from src.github.client import create_github_client
from src.github.config import GitHubRepoSettings
from src.github.contents import ContentsAPI
from src.github.releases import ReleasesAPI
from src.github.trees import TreesAPI
from src.github.workflows import WorkflowsAPI

__all__ = [
    "create_github_client",
    "GitHubRepoSettings",
    "ContentsAPI",
    "ReleasesAPI",
    "TreesAPI",
    "WorkflowsAPI",
]
