"""GitHub API layer — built on githubkit.

Usage:
    from src.github.client import create_github_client

    gh = create_github_client(token)

    from src.github.contents import ContentsAPI
    contents = ContentsAPI(gh, owner, repo, default_branch="state")
"""

from src.github.client import create_github_client
from src.github.contents import ContentsAPI
from src.github.releases import ReleasesAPI
from src.github.trees import TreesAPI
from src.github.workflows import WorkflowsAPI

__all__ = [
    "create_github_client",
    "ContentsAPI",
    "ReleasesAPI",
    "TreesAPI",
    "WorkflowsAPI",
]
