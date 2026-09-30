"""
Performance optimization settings for the PR workflow.
Reduces CPU usage and speeds up reviews.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class PerformanceConfig:
    """Performance tuning settings."""

    # Ollama settings
    ollama_num_threads: int = 4
    ollama_num_gpu: int = 0
    ollama_batch_size: int = 128
    ollama_context_size: int = 2048

    # Workflow settings
    enable_parallel_agents: bool = False
    max_patch_size: int = 500
    skip_test_files: bool = True
    strip_patch_for_coverage: bool = True
    skip_doc_files: bool = True

    # Model selection
    use_deepseek_only: bool = False
    use_haiku_for_simple: bool = False

    # Caching
    enable_review_cache: bool = True
    cache_ttl_seconds: int = 3600
    max_review_agents: int = 3
    review_only: bool = False

    @classmethod
    def from_env(cls) -> "PerformanceConfig":
        """Load performance config from environment variables."""
        return cls(
            ollama_num_threads=int(os.getenv("OLLAMA_NUM_THREADS", "4")),
            ollama_num_gpu=int(os.getenv("OLLAMA_NUM_GPU", "0")),
            ollama_batch_size=int(os.getenv("OLLAMA_BATCH_SIZE", "128")),
            ollama_context_size=int(os.getenv("OLLAMA_CONTEXT_SIZE", "2048")),
            enable_parallel_agents=os.getenv("PARALLEL_AGENTS", "false").lower() == "true",
            max_patch_size=int(os.getenv("MAX_PATCH_SIZE", "500")),
            skip_test_files=os.getenv("SKIP_TEST_REVIEWS", "true").lower() == "true",
            strip_patch_for_coverage=os.getenv("STRIP_PATCH_FOR_COVERAGE", "true").lower() == "true",
            skip_doc_files=os.getenv("SKIP_DOC_REVIEWS", "true").lower() == "true",
            use_deepseek_only=os.getenv("USE_DEEPSEEK_ONLY", "false").lower() == "true",
            enable_review_cache=os.getenv("ENABLE_CACHE", "true").lower() == "true",
            cache_ttl_seconds=int(os.getenv("CACHE_TTL", "3600")),
            max_review_agents=int(os.getenv("MAX_REVIEW_AGENTS", "3")),
            review_only=os.getenv("REVIEW_ONLY", "false").lower() == "true",
        )

    def apply_ollama_settings(self):
        """Apply Ollama performance settings to environment."""
        os.environ["OLLAMA_NUM_THREADS"] = str(self.ollama_num_threads)
        os.environ["OLLAMA_NUM_GPU"] = str(self.ollama_num_gpu)
        os.environ["OLLAMA_CONTEXT_SIZE"] = str(self.ollama_context_size)

        print(f"🔧 Performance Settings:")
        print(f"   Ollama Threads: {self.ollama_num_threads}")
        print(f"   Context Size: {self.ollama_context_size} tokens")
        print(f"   Max Patch Size: {self.max_patch_size} lines")
        print(f"   Review Agents: {self.max_review_agents}")
        print(f"   Caching: {'enabled' if self.enable_review_cache else 'disabled'}")
        print()
