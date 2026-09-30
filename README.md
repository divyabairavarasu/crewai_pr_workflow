# CrewAI PR Review Workflow v2.0

[![AI PR Review](https://github.com/divyabairavarasu/crewai_pr_workflow/actions/workflows/pr-review.yml/badge.svg)](https://github.com/divyabairavarasu/crewai_pr_workflow/actions/workflows/pr-review.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A **multi-agent AI code review system** powered by [CrewAI](https://crewai.com). Reviews PRs for performance, security, test coverage, and SOLID principles - language agnostic and provider flexible.

## Features

- **Multi-Agent Review**: Specialized AI agents for performance, security, coverage, and code quality
- **Language Agnostic**: Works with any programming language via diff analysis
- **Multi-Provider Support**: DeepSeek, OpenAI, Anthropic, Groq, or local Ollama models
- **GitHub Integration**: Post inline comments, create fix PRs, GitHub Actions workflow
- **Smart Batching**: Auto-splits large PRs (>2000 LOC) into reviewable chunks
- **Rich CLI**: Beautiful terminal output with progress bars and formatted results
- **Caching**: Disk-based caching to avoid redundant API calls
- **Complexity Analysis**: Cyclomatic complexity and maintainability metrics

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/divyabairavarasu/crewai_pr_workflow.git
cd crewai_pr_workflow

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install with all providers
pip install -e ".[all-providers]"

# Or install with specific provider
pip install -e ".[openai]"  # or anthropic, groq
```

### Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit with your API keys
nano .env
```

**Minimal `.env` configuration:**

```env
# Choose your reviewer model (see 'pr-review providers' for options)
REVIEWER_MODEL=deepseek-reasoner
REVIEWER_API_KEY=your_deepseek_key

# GitHub token for PR access
GITHUB_TOKEN=your_github_token
```

### Usage

```bash
# Review a GitHub PR and post comments
pr-review https://github.com/owner/repo/pull/123 --comment

# Dry run (no comments posted, results saved to out/)
pr-review https://github.com/owner/repo/pull/123 --dry-run

# Review from local context file
pr-review examples/pr_context.json

# Create a PR with AI-generated fixes
pr-review https://github.com/owner/repo/pull/123 --create-pr

# List available LLM providers
pr-review providers
```

## LLM Providers

The workflow supports multiple LLM providers. Use `pr-review providers` to see all options:

| Provider | Models | Best For |
|----------|--------|----------|
| **DeepSeek** | `deepseek-reasoner`, `deepseek-chat` | Complex reasoning, code review |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini`, `o1`, `o3-mini` | High quality, balanced |
| **Anthropic** | `claude-sonnet`, `claude-haiku` | Code generation, analysis |
| **Groq** | `llama-3.3-70b`, `llama-3.1-8b`, `mixtral-8x7b` | Free, fast inference |
| **Ollama** | `qwen2.5-coder`, `codellama`, `deepseek-coder-v2` | Local, private |

### Provider Configuration

```env
# Use different models for different tasks
REVIEWER_MODEL=deepseek-reasoner    # For review tasks (reasoning-heavy)
REVIEWER_API_KEY=sk-xxx

IMPLEMENTER_MODEL=gpt-4o-mini       # For fix generation (code-heavy)
IMPLEMENTER_API_KEY=sk-xxx

FAST_MODEL=llama-3.1-8b             # For triage/summaries (speed)
FAST_API_KEY=gsk-xxx
```

## GitHub Actions Integration

Add automated PR reviews to your repository:

1. **Copy the workflow file:**
   ```bash
   mkdir -p .github/workflows
   cp .github/workflows/pr-review.yml your-repo/.github/workflows/
   ```

2. **Add secrets to your repository:**
   - `REVIEWER_API_KEY`: Your LLM provider API key
   - `GITHUB_TOKEN`: Automatically provided by GitHub Actions

3. **Configure variables (optional):**
   - `REVIEWER_MODEL`: Model to use (default: `deepseek-reasoner`)
   - `MAX_LOC_PER_BATCH`: Max lines per batch (default: `2000`)

The workflow runs automatically on PR open/update and posts review comments.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    PR Review Workflow                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────┐    ┌──────────────┐    ┌──────────────────┐  │
│  │  GitHub  │───▶│ Diff Triage  │───▶│  Batch Splitter  │  │
│  │    PR    │    │    Agent     │    │   (≤2000 LOC)    │  │
│  └──────────┘    └──────────────┘    └──────────────────┘  │
│                                               │              │
│                         ┌─────────────────────┼──────────┐  │
│                         ▼                     ▼          ▼  │
│              ┌──────────────────┐  ┌──────────────┐  ┌─────┐│
│              │   Performance    │  │   Security   │  │Cover││
│              │    Engineer      │  │   Engineer   │  │Agent││
│              └────────┬─────────┘  └──────┬───────┘  └──┬──┘│
│                       │                   │             │   │
│                       ▼                   ▼             ▼   │
│              ┌──────────────────┐  ┌──────────────┐  ┌─────┐│
│              │  Implementer     │  │ Senior Dev   │  │Impl.││
│              │  (Perf Fixes)    │  │ (SOLID Gate) │  │     ││
│              └──────────────────┘  └──────────────┘  └─────┘│
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              GitHub Reviewer / PR Creator             │   │
│  │         (Post comments, create fix PRs)               │   │
│  └──────────────────────────────────────────────────────┘   │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Configuration Options

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REVIEWER_MODEL` | `deepseek-reasoner` | Model for review tasks |
| `REVIEWER_API_KEY` | - | API key for reviewer model |
| `IMPLEMENTER_MODEL` | `gpt-4o-mini` | Model for fix generation |
| `GITHUB_TOKEN` | - | GitHub token for PR access |
| `MAX_LOC_PER_BATCH` | `2000` | Max lines per review batch |
| `REVIEW_ONLY` | `false` | Skip fix generation |
| `SKIP_DOC_REVIEWS` | `true` | Skip .md/.mdx files |
| `ENABLE_CACHE` | `true` | Enable result caching |
| `CACHE_TTL` | `3600` | Cache TTL in seconds |

### CLI Options

```bash
pr-review --help

Options:
  -c, --comment      Post review comments on the PR
  -p, --create-pr    Create a new PR with AI-generated fixes
  -d, --dry-run      Run without posting comments
  -o, --output DIR   Output directory for artifacts [default: out]
  -l, --max-loc INT  Max LOC per batch [default: 2000]
  -r, --review-only  Skip fix generation
  -v, --verbose      Enable verbose output
```

## Project Structure

```
crewai_pr_workflow/
├── pr_workflow/
│   ├── __init__.py
│   ├── main.py           # Main workflow orchestration
│   ├── cli.py            # Rich CLI interface
│   ├── agents.py         # CrewAI agent definitions
│   ├── tasks.py          # CrewAI task definitions
│   ├── providers.py      # Multi-provider LLM support
│   ├── models.py         # Pydantic models for type safety
│   ├── triage.py         # Diff triage and batching
│   ├── github.py         # GitHub API client
│   ├── github_reviewer.py    # PR comment posting
│   ├── github_pr_creator.py  # Fix PR creation
│   ├── complexity.py     # Code complexity analysis
│   ├── cache.py          # Disk-based caching
│   ├── settings.py       # Configuration loading
│   └── performance_config.py # Performance tuning
├── .github/
│   └── workflows/
│       └── pr-review.yml # GitHub Actions workflow
├── examples/
│   └── pr_context.json   # Sample input
├── tests/
│   └── ...
├── pyproject.toml        # Modern Python packaging
├── requirements.txt      # Dependencies
└── README.md
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=pr_workflow

# Lint and format
ruff check pr_workflow
ruff format pr_workflow

# Type checking
mypy pr_workflow
```

## Performance Tips

1. **Use DeepSeek for reviews**: Best cost/quality ratio for reasoning tasks
2. **Use fast models for triage**: `gpt-4o-mini` or `llama-3.1-8b` for simple tasks
3. **Enable caching**: Reduces redundant API calls for similar code
4. **Skip test files**: Set `SKIP_TEST_REVIEWS=true` for faster reviews
5. **Limit batch size**: Smaller batches = faster individual reviews

## Troubleshooting

### "Rate limit exceeded"
- Reduce `MAX_REVIEW_AGENTS` to run fewer parallel reviews
- Enable caching with `ENABLE_CACHE=true`
- Use a provider with higher rate limits

### "Context length exceeded"
- Reduce `MAX_PATCH_SIZE` to truncate large diffs
- Reduce `MAX_LOC_PER_BATCH` for smaller batches

### "Permission denied" on GitHub
- Ensure `GITHUB_TOKEN` has `repo` and `pull_request` scopes
- For private repos, use a PAT with appropriate permissions

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- [CrewAI](https://crewai.com) for the multi-agent framework
- [DeepSeek](https://deepseek.com) for the reasoning model
- [Radon](https://radon.readthedocs.io/) for complexity analysis
