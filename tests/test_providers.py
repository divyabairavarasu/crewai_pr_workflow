"""Tests for the providers module."""
import os
import pytest

from pr_workflow.providers import (
    LLMProvider,
    ProviderConfig,
    PROVIDER_CONFIGS,
    get_provider_config,
)


class TestProviderConfig:
    def test_deepseek_config(self):
        config = get_provider_config("deepseek-reasoner")
        assert config.provider == LLMProvider.DEEPSEEK
        assert config.model == "deepseek-reasoner"
        assert config.base_url == "https://api.deepseek.com"

    def test_openai_config(self):
        config = get_provider_config("gpt-4o")
        assert config.provider == LLMProvider.OPENAI
        assert config.model == "gpt-4o"

    def test_anthropic_config(self):
        config = get_provider_config("claude-sonnet")
        assert config.provider == LLMProvider.ANTHROPIC
        assert "claude" in config.model

    def test_groq_config(self):
        config = get_provider_config("llama-3.3-70b")
        assert config.provider == LLMProvider.GROQ

    def test_ollama_config(self):
        config = get_provider_config("qwen2.5-coder")
        assert config.provider == LLMProvider.OLLAMA
        assert config.base_url == "http://localhost:11434"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError):
            get_provider_config("unknown-model")


class TestProviderConfigs:
    def test_all_configs_have_required_fields(self):
        for name, config in PROVIDER_CONFIGS.items():
            assert config.provider is not None
            assert config.model is not None
            assert config.temperature >= 0
            assert config.max_tokens > 0
