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

# Point to any blog site with RSS feeds
tldrop --topics "python" --site https://engineering.example.com --feeds /feed/,/blog/rss/

# Multiple output formats
tldrop --topics "SageMaker" --format md,html

# Dry run (preview without LLM calls)
tldrop --topics "SageMaker" --dry-run

# Auto-commit and push summaries to your git repo
tldrop --topics "SageMaker" --git-push
```

## Configuration

Set `ANTHROPIC_API_KEY` in your environment or in a `.env` file. See [.env.example](.env.example) for all options.
