# CrewAI PR Review Workflow (Language-Agnostic)

This scaffold implements a **sequential, language-agnostic PR review workflow** with **auto-splitting** when the diff exceeds **2000 LOC per review pass**.

## Features
- Auto-split PRs into sequential batches when total LOC > 2000
- DeepSeek Reasoner for performance, security, and coverage reviews
- Configurable implementer LLM (e.g., Gemini or local Ollama) for implementation passes
- Senior Developer gate with SOLID principle checks
- JSON artifacts for deterministic handoffs

## Project Structure
- `pr_workflow/main.py`: entrypoint
- `pr_workflow/triage.py`: diff triage and batch splitting
- `pr_workflow/agents.py`: CrewAI agent definitions
- `pr_workflow/tasks.py`: CrewAI task definitions
- `examples/pr_context.json`: sample input

## ⚡ Performance Optimization

**Ollama using too much CPU?** See [PERFORMANCE.md](PERFORMANCE.md) for detailed optimization guide.

**Quick fixes:**
```bash
# Option 1: Use DeepSeek for everything (fastest, no Ollama)
echo "USE_DEEPSEEK_ONLY=true" >> .env

# Option 2: Limit Ollama to 2 CPU threads
echo "OLLAMA_NUM_THREADS=2" >> .env

# Option 3: Use smaller model (3B instead of 7B)
ollama pull qwen2.5-coder:3b
```

## Setup
1. Create a virtual environment and install deps:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. Copy and edit environment variables:
   ```bash
   cp .env.example .env
   ```

3. Run with a local JSON:
   ```bash
   python3 -m pr_workflow.main examples/pr_context.json
   ```

   Or run with a GitHub PR URL:
   ```bash
   python -m pr_workflow.main <replace with PR link> --comment
   ```
  


## Notes
- This is **language-agnostic** and relies on diff metadata, not language-specific parsing.
- Adjust model identifiers in `.env` if your provider uses a different format.
- Review artifacts are written to `out/`.
- For private repos, set `GITHUB_TOKEN` in `.env`.
- Optional hooks: set `TEST_CMD` and `COVERAGE_CMD` to run CI commands after the workflow.
- The workflow writes a `risk_report.json` to prioritize high-risk files.
- GitHub PR ingestion uses the Pull Files API with pagination; large diffs are supported.
- Use `INCREMENTAL_COMMENTS=true` to post comments after each review task, and `POST_SUMMARY_COMMENT=true` to post a final summary review.
- Use `SKIP_DOC_REVIEWS=true` to exclude `.md`/`.mdx` files from automated review.
- Use `MAX_REVIEW_AGENTS=2` to run only performance + security reviews for debugging.
- Use `REVIEW_ONLY=true` to skip fix tasks and only run reviews.
- Use `DRY_RUN_COMMENTS=true` to write comment payloads without posting to GitHub.
