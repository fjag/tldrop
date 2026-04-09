# Product Requirements Document: tldrop

## Overview

**tldrop** is a CLI tool that monitors a single trusted blog site, identifies new posts matching your topics of interest, and generates concise summaries with key takeaways.

## Problem Statement

Staying current with technical blogs is time-consuming. Engineers want to:
- Know when relevant content is published
- Quickly understand if a post is worth reading in full
- Track what they've already reviewed

Existing solutions (RSS readers, newsletters) either require manual triage or lack topic filtering.

## Target User

Individual engineers who:
- Follow specific technical domains (e.g., AWS ML/AI services)
- Prefer local-first tools over SaaS
- Value signal over noise

## Core Requirements

### Must Have (MVP)

| Requirement | Description |
|-------------|-------------|
| Single-site monitoring | Fetch RSS feeds from one configured blog site |
| Topic filtering | Surface only posts matching user-specified topics |
| Summaries | Generate structured summaries with TL;DR, key takeaways, and action items |
| Local output | Save summaries as Markdown files |
| Timeline control | Filter posts by recency (last N days) |
| Dry run | Preview what would be processed without LLM calls |

### Should Have

| Requirement | Description |
|-------------|-------------|
| HTML output | Styled HTML alongside Markdown |
| Git sync | Auto-commit and push summaries to a repo |
| State tracking | Remember processed posts across runs |

### Won't Have (v1)

- Web UI
- Multi-site in single run
- Email/Slack notifications
- Scheduled runs (use cron)

## Security Requirements

| Requirement | Rationale |
|-------------|-----------|
| Single-site allowlist | No fetching outside configured domain — one trust boundary |
| No secrets in logs | API keys never printed |
| Sanitized filenames | Prevent path traversal in output |

## User Interface

CLI with intuitive flags:

```
tldrop --topics "SageMaker,Bedrock" --days 7
tldrop --topics "Glue,Athena" --dry-run
tldrop --topics "Redshift" --format md,html --git-push
```

## Success Metrics

- Runs reliably without errors
- Produces useful summaries that save reading time
- Processes a week's posts in under 2 minutes

## Out of Scope

- Crawling/scraping (RSS only)
- Historical backfill beyond current feed
- Content translation
- Competitive analysis of multiple blogs
