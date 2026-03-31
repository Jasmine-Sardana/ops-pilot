"""ops-pilot CI provider package.

Exports the abstract base class and all concrete providers.
Use make_provider() to instantiate the right one from config.
"""

from providers.base import CIProvider
from providers.factory import make_provider
from providers.github import GitHubProvider
from providers.gitlab import GitLabProvider
from providers.jenkins import JenkinsProvider

__all__ = [
    "CIProvider",
    "GitHubProvider",
    "GitLabProvider",
    "JenkinsProvider",
    "make_provider",
]
