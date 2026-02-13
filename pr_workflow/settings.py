import os
from dataclasses import dataclass


@dataclass
class Settings:
    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    implementer_api_key: str
    implementer_base_url: str
    implementer_model: str
    github_token: str
    incremental_comments: bool
    post_summary_comment: bool
    dry_run_comments: bool
    max_loc_per_batch: int
    out_dir: str
    test_cmd: str
    coverage_cmd: str
    use_deepseek_only: bool  # Performance: skip Ollama entirely


def load_settings() -> Settings:
    return Settings(
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-reasoner"),
        implementer_api_key=os.getenv("IMPLEMENTER_API_KEY", ""),
        implementer_base_url=os.getenv("IMPLEMENTER_BASE_URL", ""),
        implementer_model=os.getenv("IMPLEMENTER_MODEL", "gemini-2.5-pro"),
        github_token=os.getenv("GITHUB_TOKEN", ""),
        incremental_comments=os.getenv("INCREMENTAL_COMMENTS", "true").lower() == "true",
        post_summary_comment=os.getenv("POST_SUMMARY_COMMENT", "false").lower() == "true",
        dry_run_comments=os.getenv("DRY_RUN_COMMENTS", "false").lower() == "true",
        max_loc_per_batch=int(os.getenv("MAX_LOC_PER_BATCH", "2000")),
        out_dir=os.getenv("OUT_DIR", "out"),
        test_cmd=os.getenv("TEST_CMD", ""),
        coverage_cmd=os.getenv("COVERAGE_CMD", ""),
        use_deepseek_only=os.getenv("USE_DEEPSEEK_ONLY", "false").lower() == "true",
    )
