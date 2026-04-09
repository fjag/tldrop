# tldrop — Implementation Plan

## Overview

**tldrop** is an agentic system that monitors a single trusted blog site, identifies new posts matching your topics of interest, generates detailed summaries, and outputs them as Markdown/HTML files with optional GitHub sync.

**First target**: AWS blogs (https://aws.amazon.com/blogs/) focusing on ML/AI and Data services.

---

## Architecture

### Core Principle: Single-Site Enforcement

All HTTP requests flow through a single `SiteFetcher` class that validates URLs against the configured domain allowlist before any fetch. No component can bypass this layer.

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLI Entry Point                          │
│                    (tldrop/cli.py)                              │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Orchestrator Agent                          │
│  Coordinates the pipeline, manages state, handles errors        │
└─────────────────────────────────────────────────────────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        ▼                       ▼                       ▼
┌───────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  Feed Agent   │     │ Summarizer Agent│     │  Output Agent   │
│               │     │                 │     │                 │
│ • Parse RSS   │     │ • Filter by     │     │ • Render MD/HTML│
│ • Detect new  │     │   topic         │     │ • Save locally  │
│ • Fetch full  │     │ • Generate      │     │ • Git commit    │
│   content     │     │   summaries     │     │   & push        │
└───────────────┘     └─────────────────┘     └─────────────────┘
        │                       │
        ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SiteFetcher (Security Layer)                  │
│  • URL validation against allowlist                              │
│  • Domain enforcement (SINGLE point of network egress)           │
│  • Rate limiting, retries, timeout handling                      │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
   [Configured Blog Site Only]
```

### Agent Responsibilities

| Agent | Responsibility | Inputs | Outputs |
|-------|---------------|--------|---------|
| **Orchestrator** | Pipeline coordination, state management, error handling | CLI args, config | Final status, logs |
| **Feed Agent** | RSS parsing, new post detection, content fetching | Feed URLs, last-run state | List of new posts with full content |
| **Summarizer Agent** | Topic filtering, LLM-based summarization | Posts, topic keywords | Summaries with key takeaways |
| **Output Agent** | Render templates, save files, git operations | Summaries | MD/HTML files, git commits |

### Why This Agent Structure?

1. **Modularity**: Each agent has a single concern, easy to test and replace
2. **Extensibility**: Add agents for new capabilities (e.g., NotificationAgent, AnalyticsAgent)
3. **Failure isolation**: One agent's failure doesn't crash the pipeline
4. **Token efficiency**: Only the Summarizer needs LLM calls; others are pure Python

---

## Tech Stack

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.11+ | Your constraint, excellent ecosystem |
| **CLI** | `click` | Simple, composable, good defaults |
| **HTTP** | `httpx` | Modern async support, better than requests |
| **RSS parsing** | `feedparser` | Battle-tested, handles malformed feeds |
| **HTML parsing** | `beautifulsoup4` + `lxml` | Extract article content from full pages |
| **LLM** | `anthropic` SDK | Direct Claude API as you specified |
| **Templating** | `jinja2` | For MD/HTML output rendering |
| **Config** | `pydantic` | Validation, env var loading, type safety |
| **State storage** | JSON file | Simple, no DB dependency, human-readable |
| **Git** | subprocess calls | You have git configured locally |

**Total dependencies**: ~8 packages (plus their transitive deps)

---

## Project Structure

```
tldrop/
├── pyproject.toml              # Project metadata, dependencies
├── README.md                   # Usage documentation
├── .env.example                # Template for secrets
├── .gitignore
│
├── tldrop/
│   ├── __init__.py
│   ├── cli.py                  # Click CLI entry point
│   ├── config.py               # Pydantic settings, validation
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── orchestrator.py     # Main pipeline coordination
│   │   ├── state.py            # Last-run tracking, persistence
│   │   └── fetcher.py          # SiteFetcher - THE security layer
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py             # BaseAgent protocol/ABC
│   │   ├── feed.py             # FeedAgent - RSS + content fetch
│   │   ├── summarizer.py       # SummarizerAgent - LLM calls
│   │   └── output.py           # OutputAgent - render + git
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   └── post.py             # Post, Summary dataclasses
│   │
│   └── templates/
│       ├── summary.md.j2       # Markdown template
│       └── summary.html.j2     # HTML template
│
├── output/                     # Default output directory
│   └── .gitkeep
│
├── tests/
│   ├── __init__.py
│   ├── test_fetcher.py         # Critical: URL validation tests
│   ├── test_feed_agent.py
│   ├── test_summarizer.py
│   └── fixtures/
│       └── sample_feed.xml
│
└── state/
    └── .gitkeep                # last_run.json stored here
```

---

## Edge Cases & Design Decisions

### 1. URL Structure & Feed Discovery

**Challenge**: AWS has multiple blog categories, each with its own feed.

**Decision**: Support multiple feed URLs within the same allowed domain.

```yaml
# config.yaml or CLI
site: https://aws.amazon.com
feeds:
  - /blogs/machine-learning/feed/
  - /blogs/big-data/feed/
  - /blogs/aws/feed/
```

**Validation**: All feed paths are validated to be under the configured `site` domain.

### 2. Topic Filtering

**Challenge**: Posts may not have clean topic tags; keyword matching can be noisy.

**Decision**: Two-stage filtering:
1. **Pre-filter** (cheap): Keyword match in title/categories/excerpt
2. **LLM filter** (if ambiguous): Ask Claude "Is this post about {topics}?" with just the title+excerpt

This minimizes token usage while catching edge cases.

### 3. Pagination / Feed Limits

**Challenge**: RSS feeds typically show only recent posts (10-20 items).

**Decision**: This is fine for MVP. The time-based approach means:
- First run: Process all posts in current feed
- Subsequent runs: Only posts newer than `last_run` timestamp
- If you miss a run for weeks, you might miss posts that aged out of the feed

**Future enhancement**: Scrape the HTML blog listing for historical backfill.

### 4. Full Content Extraction

**Challenge**: RSS `content:encoded` has full HTML, but it may have ads, nav, etc.

**Decision**:
- Prefer `content:encoded` from RSS (usually clean on AWS)
- If truncated, fetch the full page via `SiteFetcher` and extract article body
- Use `readability-lxml` or manual BeautifulSoup selectors for the AWS blog structure

### 5. Rate Limiting & Politeness

**Challenge**: Don't hammer the blog.

**Decision**:
- 1-second delay between requests
- Respect `Retry-After` headers
- User-Agent identifying the tool: `tldrop/0.1 (personal blog monitor)`

### 6. Duplicate Detection

**Challenge**: Same post might appear in multiple feeds (e.g., cross-posted).

**Decision**: Deduplicate by post URL before summarization.

### 7. LLM Cost Control

**Challenge**: Summarizing many posts gets expensive.

**Decision**:
- Process posts in batches
- Use Claude Haiku for topic filtering (cheap)
- Use Claude Sonnet for summaries (better quality, reasonable cost)
- Show estimated token count before proceeding (with `--yes` flag to skip confirmation)

### 8. Error Handling

**Principle**: Fail loud, recover gracefully.

| Error | Handling |
|-------|----------|
| Network timeout | Retry 3x with backoff, then skip post with warning |
| RSS parse failure | Log error, abort run (feed structure changed?) |
| LLM API error | Retry 3x, then skip post with warning |
| Invalid URL (security) | Raise exception immediately, abort run |
| Git push failure | Log warning, don't fail the whole run |

### 9. State Persistence

**Decision**: Simple JSON file:

```json
{
  "last_run": "2026-04-09T10:30:00Z",
  "processed_urls": [
    "https://aws.amazon.com/blogs/machine-learning/post-1/",
    "https://aws.amazon.com/blogs/machine-learning/post-2/"
  ],
  "version": 1
}
```

Keep last N processed URLs (e.g., 500) to detect duplicates even if timestamps are unreliable.

### 10. Security Considerations

| Concern | Mitigation |
|---------|------------|
| URL injection | `SiteFetcher` validates all URLs against allowlist using `urllib.parse` |
| Secrets in logs | Never log API keys; use `pydantic.SecretStr` |
| Content injection | Don't execute any code from fetched content; treat as untrusted text |
| Path traversal | Sanitize output filenames; don't allow `../` |

---

## Recommended Improvements

### Features You Didn't Ask For (But Might Want)

1. **Digest Mode**: Instead of one file per post, generate a weekly/daily digest combining all summaries

2. **Relevance Scoring**: Have the LLM rate each post's relevance (1-5) so you can filter to only "highly relevant"

3. **Diff Detection**: For posts you've seen before, detect if they've been updated

4. **Reading Time Estimate**: Include estimated reading time for the original post

5. **Link Extraction**: Pull out key links mentioned in the post (GitHub repos, docs, etc.) — still validated against allowlist

6. **Dry Run Mode**: `--dry-run` to show what would be processed without actually calling the LLM or writing files

7. **JSON Output**: In addition to MD/HTML, output structured JSON for programmatic consumption

8. **Watch Mode**: Daemon mode that runs every N hours (though a simple cron job works too)

---

## Phased Implementation Plan

### Phase 1: MVP (Core Loop)

**Goal**: End-to-end working pipeline for a single feed

| Step | Task | Details |
|------|------|---------|
| 1.1 | Project setup | `pyproject.toml`, dependencies, directory structure |
| 1.2 | Config & CLI skeleton | Pydantic settings, Click CLI with `--topics`, `--site` |
| 1.3 | SiteFetcher | URL validation, httpx client, rate limiting |
| 1.4 | FeedAgent | Parse RSS, extract posts, detect new via timestamp |
| 1.5 | State management | JSON read/write, last_run tracking |
| 1.6 | SummarizerAgent | Claude API integration, basic summarization prompt |
| 1.7 | OutputAgent | Jinja2 templates, write MD files |
| 1.8 | Orchestrator | Wire agents together, basic error handling |
| 1.9 | Manual testing | Run against AWS ML feed, verify outputs |

**MVP Deliverable**: `tldrop --topics "SageMaker,Bedrock" --site https://aws.amazon.com` produces summaries.

---

### Phase 2: Robustness

**Goal**: Handle real-world messiness

| Step | Task | Details |
|------|------|---------|
| 2.1 | Multiple feeds | Support list of feed paths |
| 2.2 | Deduplication | URL-based dedup across feeds |
| 2.3 | Full content extraction | Fetch article page if RSS content is truncated |
| 2.4 | Better error handling | Retries, partial failures, detailed logging |
| 2.5 | HTML output | Add HTML template with styling |
| 2.6 | Dry run mode | `--dry-run` flag |
| 2.7 | Unit tests | Cover SiteFetcher, FeedAgent, state management |

---

### Phase 3: Polish & GitHub Sync

**Goal**: Production-ready for personal use

| Step | Task | Details |
|------|------|---------|
| 3.1 | Git integration | Auto-commit and push to configured repo |
| 3.2 | Digest mode | Combine multiple posts into single digest file |
| 3.3 | Cost estimation | Show token estimate, `--yes` to skip confirmation |
| 3.4 | Relevance scoring | LLM rates posts 1-5, filter threshold |
| 3.5 | Better prompts | Iterate on summary quality, add key takeaways |
| 3.6 | Documentation | README with setup, usage, examples |

---

### Phase 4: Future Enhancements (Optional)

| Feature | Description |
|---------|-------------|
| Historical backfill | Scrape HTML listings for older posts |
| Notification hooks | Send to Slack, email, etc. |
| Multiple sites | Support N sites (still each explicitly configured) |
| Web UI | Simple Flask/FastAPI dashboard to view summaries |
| Caching | Local cache of fetched content to avoid re-fetching |

---

## CLI Interface (Proposed)

```bash
# Basic usage - process new posts on configured topics
tldrop --topics "SageMaker,Bedrock,Glue"

# Specify site explicitly (default: from config)
tldrop --topics "SageMaker" --site https://aws.amazon.com

# Override feeds
tldrop --topics "Bedrock" --feeds /blogs/machine-learning/feed/,/blogs/aws/feed/

# Output options
tldrop --topics "SageMaker" --output ./my-summaries --format md,html

# Git sync
tldrop --topics "SageMaker" --git-push

# Control behavior
tldrop --topics "SageMaker" --dry-run          # Preview without executing
tldrop --topics "SageMaker" --yes              # Skip confirmation prompts
tldrop --topics "SageMaker" --since 2026-04-01 # Override time filter

# Digest mode
tldrop --topics "SageMaker" --digest           # Single file with all posts
```

---

## Summary Prompt Design (Draft)

```
You are summarizing a technical blog post for a busy engineer.

Post Title: {title}
Post Date: {date}
Categories: {categories}
Topics of Interest: {topics}

Content:
{content}

Provide:
1. **TL;DR** (2-3 sentences): What is this post about and why does it matter?
2. **Key Takeaways** (3-5 bullets): The most important points
3. **What's New** (if applicable): New features, services, or capabilities announced
4. **Relevance to {topics}** (1 sentence): How this relates to the reader's interests
5. **Action Items** (if any): Things the reader might want to try or investigate

Keep the summary concise but complete. Use technical terms appropriately.
```

---

## Design Decisions (Resolved)

### Output File Naming

**Decision**: Flat files with date prefix, site domain as top-level directory.

```
output/
├── aws.amazon.com/
│   ├── 2026-04-09-customize-amazon-nova-models.md
│   ├── 2026-04-09-human-in-the-loop-healthcare.md
│   └── 2026-04-08-intelligent-audio-search.md
│
└── engineering.example.com/         # Future: other blogs
    └── 2026-04-07-scaling-postgres.md
```

**Rationale**:
- **Site as namespace** — clean separation for future multi-site support
- **Date prefix** — sortable, universal (every post has a date)
- **Slug from title** — no dependency on site-specific category structures
- **Metadata in frontmatter** — categories, tags, author preserved inside the file, not filename

### Feed Selection (MVP Default)

**Decision**: All three AWS feeds by default: `machine-learning`, `big-data`, `aws`.

These cover SageMaker, Bedrock, Glue, Athena, Redshift topics. Overridable via `--feeds` flag.

### Summary Length

**Decision**: Concise (200-300 words) by default. Enough to capture key points without overwhelming.

---

## Configuration Choices (From Requirements)

| Setting | Choice | Notes |
|---------|--------|-------|
| Topic definition | CLI flags per run | `--topics "SageMaker,Bedrock,Glue"` |
| New post detection | Time-based | Track `last_run` timestamp |
| LLM provider | Claude API directly | Anthropic SDK, you manage API key |
| GitHub sync | Git CLI | Shell out to git commands |

---

## Next Steps

Once you approve this plan, I'll begin Phase 1 implementation starting with project setup and the security-critical `SiteFetcher` component.
