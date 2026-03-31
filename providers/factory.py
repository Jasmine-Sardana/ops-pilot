"""Provider factory for ops-pilot.

Single place that reads PipelineConfig + OpsPilotConfig and returns the
right CIProvider instance. Keeps all provider-wiring logic out of the
watch loop and agents.
"""

from __future__ import annotations

from providers.base import CIProvider
from providers.github import GitHubProvider
from providers.gitlab import GitLabProvider
from providers.jenkins import JenkinsProvider
from shared.config import OpsPilotConfig, PipelineConfig


def make_provider(pipeline: PipelineConfig, cfg: OpsPilotConfig) -> CIProvider:
    """Instantiate the correct CIProvider for a pipeline config.

    Args:
        pipeline: Per-pipeline configuration (provider type, credentials).
        cfg:      Global ops-pilot config (shared tokens, model, etc.).

    Returns:
        A fully-configured CIProvider ready to call.

    Raises:
        ValueError: For unknown provider values (caught at config load time
                    by the Pydantic validator, but re-raised here for safety).
    """
    provider = pipeline.provider

    if provider == "github_actions":
        token = pipeline.github_token or cfg.github_token
        return GitHubProvider(token=token)

    if provider == "gitlab_ci":
        token = pipeline.gitlab_token or cfg.gitlab_token
        base_url = pipeline.gitlab_url or "https://gitlab.com"
        return GitLabProvider(token=token, base_url=base_url)

    if provider == "jenkins":
        # Build the code-host provider for git/PR operations
        code_host = _make_code_host(pipeline, cfg)
        return JenkinsProvider(
            url=pipeline.jenkins_url or "",
            job=pipeline.jenkins_job or pipeline.repo,
            user=cfg.jenkins_user,
            token=cfg.jenkins_token,
            code_host=code_host,
        )

    raise ValueError(
        f"Unknown provider '{provider}' for repo '{pipeline.repo}'. "
        f"Expected one of: github_actions, gitlab_ci, jenkins."
    )


def _make_code_host(pipeline: PipelineConfig, cfg: OpsPilotConfig) -> CIProvider:
    """Build the code-host provider used by Jenkins for git/PR operations."""
    code_host = pipeline.code_host or "github"

    if code_host == "github":
        token = pipeline.github_token or cfg.github_token
        return GitHubProvider(token=token)

    if code_host == "gitlab":
        token = pipeline.gitlab_token or cfg.gitlab_token
        base_url = pipeline.gitlab_url or "https://gitlab.com"
        return GitLabProvider(token=token, base_url=base_url)

    raise ValueError(
        f"Unknown code_host '{code_host}' for Jenkins pipeline '{pipeline.repo}'. "
        f"Expected one of: github, gitlab."
    )
