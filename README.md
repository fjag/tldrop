# tldrop

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Powered by Claude](https://img.shields.io/badge/Powered%20by-Claude-blueviolet.svg)](https://www.anthropic.com/claude)
[![CLI](https://img.shields.io/badge/interface-CLI-orange.svg)](#usage)
[![Experimental](https://img.shields.io/badge/status-experimental-red.svg)](#)

Agentic blog monitor that surfaces new posts and generates summaries.

> **EXPERIMENTAL TOOL:** tldrop is a personal productivity tool designed to assist — not replace — reading original content. Summaries are AI-generated and may contain inaccuracies. Always verify important information against the source. Provided without warranty or support commitments.

## Documentation

- [Product Requirements](docs/PRD.md) — what tldrop does and why
- [Technical Specification](docs/TECHNICAL_SPEC.md) — architecture and implementation details

## Quick Start

```bash
# Install
pip install -e .

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run
tldrop --topics "SageMaker,Bedrock,Glue"
```

## Usage

```bash
# Basic usage (defaults to AWS blogs)
tldrop --topics "SageMaker,Bedrock,Glue"

# Only posts from the last 7 days
tldrop --topics "SageMaker,Bedrock" --days 7

# Point to any blog site (requires RSS feeds)
tldrop --topics "python" --site https://engineering.example.com --feeds /feed/

# Multiple output formats
tldrop --topics "SageMaker" --format md,html

# Dry run (preview without LLM calls)
tldrop --topics "SageMaker" --dry-run

# Auto-commit and push summaries to your git repo
tldrop --topics "SageMaker" --git-push
```

## Configuration

Set `ANTHROPIC_API_KEY` in your environment or in a `.env` file. See [.env.example](.env.example) for all options.

## Cost & Models

**Default models:**
- **Summarizer**: Claude Sonnet 4 — quality summaries
- **Filter**: Claude Haiku 4 — cheap relevance checks

**Estimated cost for 10 typical AWS blog posts:**

| Stage | Tokens | Cost |
|-------|--------|------|
| Filter (Haiku) | ~5K input | ~$0.001 |
| Summarizer (Sonnet) input | ~50K | ~$0.15 |
| Summarizer (Sonnet) output | ~15K | ~$0.23 |
| **Total** | | **~$0.38** |

Override models via environment variables:
```bash
export TLDROP_SUMMARIZER_MODEL=claude-sonnet-4-20250514
export TLDROP_FILTER_MODEL=claude-haiku-4-20250514
```
