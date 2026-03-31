"""Tests for the LLM client factory (shared/llm_client.py)."""

from __future__ import annotations

from unittest.mock import patch

import anthropic
import pytest

from shared.config import OpsPilotConfig
from shared.llm_client import make_client


def _cfg(**kwargs) -> OpsPilotConfig:
    """Build a minimal OpsPilotConfig with overrides."""
    base = {"pipelines": []}
    base.update(kwargs)
    return OpsPilotConfig(**base)


class TestMakeClient:
    def test_default_returns_anthropic_client(self) -> None:
        cfg = _cfg(anthropic_api_key="sk-ant-test")
        client = make_client(cfg)
        assert isinstance(client, anthropic.Anthropic)

    def test_explicit_anthropic_provider_returns_anthropic_client(self) -> None:
        cfg = _cfg(llm_provider="anthropic", anthropic_api_key="sk-ant-test")
        client = make_client(cfg)
        assert isinstance(client, anthropic.Anthropic)

    def test_bedrock_provider_returns_bedrock_client(self) -> None:
        cfg = _cfg(llm_provider="bedrock", aws_region="us-east-1")
        client = make_client(cfg)
        assert isinstance(client, anthropic.AnthropicBedrock)

    def test_bedrock_without_region_still_creates_client(self) -> None:
        # boto3 will use AWS_DEFAULT_REGION or its own defaults — no error at construction
        cfg = _cfg(llm_provider="bedrock")
        client = make_client(cfg)
        assert isinstance(client, anthropic.AnthropicBedrock)

    def test_anthropic_key_passed_to_client(self) -> None:
        cfg = _cfg(anthropic_api_key="sk-ant-mykey")
        client = make_client(cfg)
        assert isinstance(client, anthropic.Anthropic)
        # The API key should be reflected in the client's auth header
        assert client.api_key == "sk-ant-mykey"

    def test_invalid_llm_provider_raises_on_config(self) -> None:
        with pytest.raises(ValueError, match="llm_provider"):
            _cfg(llm_provider="openai")


class TestOpsPilotConfigBedrockFields:
    def test_has_bedrock_false_by_default(self) -> None:
        cfg = _cfg()
        assert cfg.has_bedrock is False

    def test_has_bedrock_true_when_provider_set(self) -> None:
        cfg = _cfg(llm_provider="bedrock")
        assert cfg.has_bedrock is True

    def test_aws_region_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AWS_REGION", "eu-west-1")
        from shared.config import load_config
        cfg = load_config()
        assert cfg.aws_region == "eu-west-1"

    def test_aws_default_region_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AWS_REGION", raising=False)
        monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-southeast-1")
        from shared.config import load_config
        cfg = load_config()
        assert cfg.aws_region == "ap-southeast-1"

    def test_llm_provider_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LLM_PROVIDER", "bedrock")
        from shared.config import load_config
        cfg = load_config()
        assert cfg.llm_provider == "bedrock"
        assert cfg.has_bedrock is True
