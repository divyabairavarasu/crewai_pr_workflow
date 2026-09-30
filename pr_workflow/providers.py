"""
Multi-provider LLM support for CrewAI PR Workflow.
Supports DeepSeek, OpenAI, Anthropic, Groq, and local Ollama models.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from crewai import LLM


class LLMProvider(str, Enum):
    """Supported LLM providers."""
    DEEPSEEK = "deepseek"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GROQ = "groq"
    OLLAMA = "ollama"
    CUSTOM = "custom"


@dataclass
class ProviderConfig:
    """Configuration for an LLM provider."""
    provider: LLMProvider
    model: str
    api_key: str = ""
    base_url: Optional[str] = None
    temperature: float = 0.1
    max_tokens: int = 4096
    
    # Provider-specific settings
    reasoning_effort: Optional[str] = None  # For OpenAI o1/o3 models
    
    def to_llm(self) -> LLM:
        """Create a CrewAI LLM instance from this config."""
        kwargs = {
            "model": self._get_model_string(),
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        
        if self.api_key:
            kwargs["api_key"] = self.api_key
            
        if self.base_url:
            kwargs["base_url"] = self.base_url
            
        return LLM(**kwargs)
    
    def _get_model_string(self) -> str:
        """Get the model string with provider prefix if needed."""
        if self.provider == LLMProvider.OLLAMA:
            return f"ollama/{self.model}"
        elif self.provider == LLMProvider.GROQ:
            return f"groq/{self.model}"
        elif self.provider == LLMProvider.ANTHROPIC:
            return f"anthropic/{self.model}"
        elif self.provider == LLMProvider.OPENAI:
            return f"openai/{self.model}"
        return self.model


# Pre-configured provider templates
PROVIDER_CONFIGS = {
    # DeepSeek - Great for reasoning tasks
    "deepseek-reasoner": ProviderConfig(
        provider=LLMProvider.DEEPSEEK,
        model="deepseek-reasoner",
        base_url="https://api.deepseek.com",
    ),
    "deepseek-chat": ProviderConfig(
        provider=LLMProvider.DEEPSEEK,
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
    ),
    
    # OpenAI
    "gpt-4o": ProviderConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4o",
    ),
    "gpt-4o-mini": ProviderConfig(
        provider=LLMProvider.OPENAI,
        model="gpt-4o-mini",
    ),
    "o1": ProviderConfig(
        provider=LLMProvider.OPENAI,
        model="o1",
        reasoning_effort="medium",
    ),
    "o3-mini": ProviderConfig(
        provider=LLMProvider.OPENAI,
        model="o3-mini",
        reasoning_effort="medium",
    ),
    
    # Anthropic
    "claude-sonnet": ProviderConfig(
        provider=LLMProvider.ANTHROPIC,
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
    ),
    "claude-haiku": ProviderConfig(
        provider=LLMProvider.ANTHROPIC,
        model="claude-3-5-haiku-20241022",
    ),
    
    # Groq (fast inference)
    "llama-3.3-70b": ProviderConfig(
        provider=LLMProvider.GROQ,
        model="llama-3.3-70b-versatile",
    ),
    "llama-3.1-8b": ProviderConfig(
        provider=LLMProvider.GROQ,
        model="llama-3.1-8b-instant",
    ),
    "mixtral-8x7b": ProviderConfig(
        provider=LLMProvider.GROQ,
        model="mixtral-8x7b-32768",
    ),
    
    # Ollama (local)
    "qwen2.5-coder": ProviderConfig(
        provider=LLMProvider.OLLAMA,
        model="qwen2.5-coder:7b",
        base_url="http://localhost:11434",
    ),
    "codellama": ProviderConfig(
        provider=LLMProvider.OLLAMA,
        model="codellama:13b",
        base_url="http://localhost:11434",
    ),
    "deepseek-coder-v2": ProviderConfig(
        provider=LLMProvider.OLLAMA,
        model="deepseek-coder-v2:16b",
        base_url="http://localhost:11434",
    ),
}


def get_provider_config(name: str) -> ProviderConfig:
    """Get a pre-configured provider by name."""
    if name not in PROVIDER_CONFIGS:
        available = ", ".join(PROVIDER_CONFIGS.keys())
        raise ValueError(f"Unknown provider config: {name}. Available: {available}")
    return PROVIDER_CONFIGS[name]


def build_llm_from_env(
    model_env: str = "REVIEWER_MODEL",
    api_key_env: str = "REVIEWER_API_KEY",
    base_url_env: str = "REVIEWER_BASE_URL",
    default_model: str = "deepseek-reasoner",
) -> LLM:
    """
    Build an LLM from environment variables.
    
    Supports both pre-configured providers (by name) and custom configurations.
    """
    model = os.getenv(model_env, default_model)
    api_key = os.getenv(api_key_env, "")
    base_url = os.getenv(base_url_env, "")
    
    # Check if it's a pre-configured provider
    if model in PROVIDER_CONFIGS:
        config = get_provider_config(model)
        # Override with env vars if provided
        if api_key:
            config.api_key = api_key
        if base_url:
            config.base_url = base_url
        return config.to_llm()
    
    # Custom configuration
    config = ProviderConfig(
        provider=LLMProvider.CUSTOM,
        model=model,
        api_key=api_key,
        base_url=base_url if base_url else None,
    )
    return config.to_llm()


class LLMFactory:
    """Factory for creating LLMs with different roles."""
    
    def __init__(self):
        self._cache: dict[str, LLM] = {}
    
    def get_reviewer_llm(self) -> LLM:
        """Get LLM for review tasks (reasoning-heavy)."""
        if "reviewer" not in self._cache:
            self._cache["reviewer"] = build_llm_from_env(
                model_env="REVIEWER_MODEL",
                api_key_env="REVIEWER_API_KEY",
                base_url_env="REVIEWER_BASE_URL",
                default_model="deepseek-reasoner",
            )
        return self._cache["reviewer"]
    
    def get_implementer_llm(self) -> LLM:
        """Get LLM for implementation tasks (code generation)."""
        if "implementer" not in self._cache:
            self._cache["implementer"] = build_llm_from_env(
                model_env="IMPLEMENTER_MODEL",
                api_key_env="IMPLEMENTER_API_KEY",
                base_url_env="IMPLEMENTER_BASE_URL",
                default_model="gpt-4o-mini",
            )
        return self._cache["implementer"]
    
    def get_fast_llm(self) -> LLM:
        """Get fast LLM for simple tasks (triage, summaries)."""
        if "fast" not in self._cache:
            self._cache["fast"] = build_llm_from_env(
                model_env="FAST_MODEL",
                api_key_env="FAST_API_KEY",
                base_url_env="FAST_BASE_URL",
                default_model="gpt-4o-mini",
            )
        return self._cache["fast"]
    
    def clear_cache(self):
        """Clear the LLM cache."""
        self._cache.clear()


# Global factory instance
llm_factory = LLMFactory()
