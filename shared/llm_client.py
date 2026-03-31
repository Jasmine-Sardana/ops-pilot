"""LLM client factory for ops-pilot.

Returns either an ``anthropic.Anthropic`` (direct API) or
``anthropic.AnthropicBedrock`` (AWS Bedrock) client depending on the config.

Both clients expose the same ``messages.create()`` interface, so agents
work without modification.

AWS credentials for Bedrock are resolved in the standard boto3 order:
  1. Explicit ``AWS_ACCESS_KEY_ID`` / ``AWS_SECRET_ACCESS_KEY`` env vars
  2. ``AWS_PROFILE`` env var (named profile in ~/.aws/credentials)
  3. EC2 / ECS / Lambda instance role (IAM)
  4. ~/.aws/credentials default profile

No boto3 credential configuration is needed when running on AWS compute.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Union

import anthropic

if TYPE_CHECKING:
    from shared.config import OpsPilotConfig

# Type alias accepted everywhere a client is expected
LLMClient = Union[anthropic.Anthropic, anthropic.AnthropicBedrock]


def make_client(cfg: "OpsPilotConfig") -> LLMClient:
    """Create the appropriate LLM client based on ``cfg.llm_provider``.

    Args:
        cfg: Loaded ``OpsPilotConfig`` instance.

    Returns:
        ``anthropic.Anthropic`` for ``llm_provider: anthropic`` (default).
        ``anthropic.AnthropicBedrock`` for ``llm_provider: bedrock``.
    """
    if cfg.llm_provider == "bedrock":
        kwargs: dict = {}
        if cfg.aws_region:
            kwargs["aws_region"] = cfg.aws_region
        return anthropic.AnthropicBedrock(**kwargs)

    return anthropic.Anthropic(api_key=cfg.anthropic_api_key or None)
