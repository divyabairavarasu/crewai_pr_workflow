"""
Performance optimization settings for the PR workflow.
Reduces Ollama CPU usage and speeds up reviews.
"""
import os
from dataclasses import dataclass


@dataclass
class PerformanceConfig:
    """Performance tuning settings."""

    # Ollama settings
    ollama_num_threads: int = 4  # Limit CPU threads (default: use all cores)
    ollama_num_gpu: int = 0  # GPU layers (0 = CPU only, increase if you have GPU)
    ollama_batch_size: int = 128  # Smaller batch = less memory, slower
    ollama_context_size: int = 2048  # Reduce from default 4096 for speed

    # Workflow settings
    enable_parallel_agents: bool = False  # Run agents sequentially to reduce load
    max_patch_size: int = 500  # Limit patch size sent to models (lines)
    skip_test_files: bool = True  # Don't review test files with expensive models
    strip_patch_for_coverage: bool = True  # Coverage check doesn't need full patches
    skip_doc_files: bool = True  # Skip docs and markdown files

    # Model selection
    use_deepseek_only: bool = False  # Use DeepSeek for everything (no Ollama)
    use_haiku_for_simple: bool = False  # Use Claude Haiku for simple tasks

    # Caching
    enable_review_cache: bool = True  # Cache similar file reviews
    cache_ttl_seconds: int = 3600  # 1 hour
    max_review_agents: int = 3  # Limit review agents for debugging (1=perf,2=perf+security,3=+coverage)
    review_only: bool = False  # Skip fix tasks

    @classmethod
    def from_env(cls):
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

        print(f"🔧 Ollama Performance Settings:")
        print(f"   Threads: {self.ollama_num_threads} (lower = less CPU usage)")
        print(f"   Context: {self.ollama_context_size} tokens (lower = faster)")
        print(f"   GPU Layers: {self.ollama_num_gpu} (0 = CPU only)")
        print()
