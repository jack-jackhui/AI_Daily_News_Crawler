# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AI News Crawler - An automated pipeline that fetches AI/tech news from RSS feeds, uses Azure OpenAI to re-rank and summarize articles, then distributes the digest to multiple platforms (Telegram, WeChat, WordPress, Twitter/X, Threads).

## Commands

### Run the Pipeline
```bash
# From project root with virtual environment
cd src && python main.py

# Or use the shell script (expects venv/ directory)
./run_ai_news_crawler.sh
```

### Development Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Linting
```bash
flake8 src/ --max-line-length=120 --ignore=E501,E303,E302
```

### Run Individual Processors (for testing)
```bash
cd src
python -m processors.summarizer  # Has example test data
```

## Architecture

The pipeline flows through these stages:

```
RSS Feeds → Fetcher → LLM Re-ranker → Formatter → Multiple Outputs
```

### Core Components

**`src/main.py`** - Pipeline orchestrator. Runs the full flow: fetch → re-rank → format → distribute to all platforms.

**`src/fetchers/rss_fetcher.py`** - Fetches articles from RSS feeds configured in `config.py`. Uses `newspaper3k` for full-text extraction, `textstat` for readability scoring, and `tranco` for domain ranking. Filters to last 24 hours and scores articles by keyword relevance (AI keywords weighted 4x, crypto 1x).

**`src/processors/llm_reranker.py`** - Uses Azure OpenAI to group similar articles, select representatives, and generate summaries. Returns JSON with icon, title, summary, url. Includes JSON repair logic for malformed responses.

**`src/processors/formatter.py`** - Formats the summarized articles into a text digest with header and footer.

**`src/outputs/`** - Platform-specific publishers:
- `telegram_sender.py` - Async Telegram bot using `python-telegram-bot`
- `wechat_sender.py` - WeChat distribution
- `wordpress_publisher.py` - WordPress REST API publishing
- `twitter_publisher.py` - Uses `tweepy` for Twitter/X, generates tweet content via LLM
- `threads_publisher.py` - Meta Threads publishing

### Configuration

**`src/config.py`** - RSS feed URLs list (`SITES_CONFIG`) and Azure OpenAI placeholders.

**`.env`** (required, not committed) - Environment variables:
- `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_MODEL`, `AZURE_OPENAI_API_VERSION`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `WORDPRESS_SITE`, `WORDPRESS_USERNAME`, `WORDPRESS_APP_PASSWORD`
- `TWITTER_API_KEY`, `TWITTER_API_SECRET_KEY`, `TWITTER_ACCESS_TOKEN`, `TWITTER_ACCESS_TOKEN_SECRET`, `TWITTER_BEARER_TOKEN`
- `THREADS_USER_ID`, `THREADS_ACCESS_TOKEN` (auto-refreshed if expiring within 7 days)

### Data Flow

1. `fetch_rss_feeds()` returns `list[dict]` with keys: `title`, `content`, `url`, `published`, `status`, `total_score`
2. `re_rank_and_summarize_with_llm()` returns `list[dict]` with keys: `icon`, `title`, `summary`, `url`
3. `format_summary()` returns formatted string for distribution
4. Output functions send to respective platforms

### Key Dependencies

- `feedparser` - RSS parsing
- `newspaper3k` - Article full-text extraction
- `openai` - Azure OpenAI client (AzureOpenAI class)
- `python-telegram-bot` - Telegram async bot
- `tweepy` - Twitter/X API v2
- `tranco` - Domain ranking list (cached in `src/.tranco/`)

## Production Server

- **SSH Access**: `ssh Oracle-2`
- **App Directory**: `/home/ubuntu/AI_Daily_News_Crawler`

## CI/CD

GitHub Actions workflow (`.github/workflows/main.yml`):
- Lints with flake8 on push/PR to main
- Deploys to Oracle Cloud VM via SSH
- Sends Telegram notifications on success/failure

## Important Rules

### Git Commits
- Do NOT include "Claude" or "AI" in commit messages
- Do NOT commit secrets (`.env` files, API keys, tokens)
- Do NOT commit database files (`*.pickle`, `*.db`)

### Package Installation
Always activate the virtual environment before installing packages:
```bash
source venv/bin/activate
pip install <package>
```
