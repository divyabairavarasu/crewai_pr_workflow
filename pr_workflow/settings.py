"""
Application settings loaded from environment variables.
"""
import os
from dataclasses import dataclass


@dataclass
class Settings:
    """Application configuration settings."""
    
    # Reviewer LLM (for review tasks)
    reviewer_model: str
    reviewer_api_key: str
    reviewer_base_url: str
    
    # Implementer LLM (for fix generation)
    implementer_model: str
    implementer_api_key: str
    implementer_base_url: str
    
    # Fast LLM (for triage/summaries)
    fast_model: str
    fast_api_key: str
    fast_base_url: str
    
    # GitHub
    github_token: str
    
    # Workflow settings
    incremental_comments: bool
    post_summary_comment: bool
    dry_run_comments: bool
    max_loc_per_batch: int
    out_dir: str
    test_cmd: str
    coverage_cmd: str
    
    # Performance
    use_deepseek_only: bool
    enable_cache: bool
    cache_ttl: int
    
    # Legacy compatibility (maps to reviewer settings)
    @property
    def deepseek_api_key(self) -> str:
        return self.reviewer_api_key
    
    @property
    def deepseek_base_url(self) -> str:
        return self.reviewer_base_url
    
    @property
    def deepseek_model(self) -> str:
        return self.reviewer_model


def load_settings() -> Settings:
    """Load settings from environment variables."""
    return Settings(
        # Reviewer LLM
        reviewer_model=os.getenv("REVIEWER_MODEL", os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner")),
        reviewer_api_key=os.getenv("REVIEWER_API_KEY", os.getenv("DEEPSEEK_API_KEY", "")),
        reviewer_base_url=os.getenv("REVIEWER_BASE_URL", os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")),
        
        # Implementer LLM
        implementer_model=os.getenv("IMPLEMENTER_MODEL", "gpt-4o-mini"),
        implementer_api_key=os.getenv("IMPLEMENTER_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        implementer_base_url=os.getenv("IMPLEMENTER_BASE_URL", ""),
        
        # Fast LLM
        fast_model=os.getenv("FAST_MODEL", "gpt-4o-mini"),
        fast_api_key=os.getenv("FAST_API_KEY", os.getenv("OPENAI_API_KEY", "")),
        fast_base_url=os.getenv("FAST_BASE_URL", ""),
        
        # GitHub
        github_token=os.getenv("GITHUB_TOKEN", ""),
        
        # Workflow
        incremental_comments=os.getenv("INCREMENTAL_COMMENTS", "false").lower() == "true",
        post_summary_comment=os.getenv("POST_SUMMARY_COMMENT", "true").lower() == "true",
        dry_run_comments=os.getenv("DRY_RUN_COMMENTS", "false").lower() == "true",
        max_loc_per_batch=int(os.getenv("MAX_LOC_PER_BATCH", "2000")),
        out_dir=os.getenv("OUT_DIR", "out"),
        test_cmd=os.getenv("TEST_CMD", ""),
        coverage_cmd=os.getenv("COVERAGE_CMD", ""),
        
        # Performance
        use_deepseek_only=os.getenv("USE_DEEPSEEK_ONLY", "false").lower() == "true",
        enable_cache=os.getenv("ENABLE_CACHE", "true").lower() == "true",
        cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
    )
