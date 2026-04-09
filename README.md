# tldrop

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Powered by Claude](https://img.shields.io/badge/Powered%20by-Claude-blueviolet.svg)](https://www.anthropic.com/claude)
[![CLI](https://img.shields.io/badge/interface-CLI-orange.svg)](#usage)
[![RSS](https://img.shields.io/badge/data-RSS%20feeds-yellow.svg)](#)

Agentic blog monitor that surfaces new posts and generates summaries.

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
# Basic usage
tldrop --topics "SageMaker,Bedrock,Glue"

# Override site and feeds
tldrop --topics "Bedrock" --site https://aws.amazon.com --feeds /blogs/machine-learning/feed/

# Multiple output formats
tldrop --topics "SageMaker" --format md,html

# Dry run (preview without LLM calls)
tldrop --topics "SageMaker" --dry-run

# Git sync
tldrop --topics "SageMaker" --git-push
```

## Configuration

Environment variables (or `.env` file):

- `ANTHROPIC_API_KEY` - Required. Your Claude API key.
- `TLDROP_SITE` - Blog site URL (default: https://aws.amazon.com)
- `TLDROP_OUTPUT_DIR` - Output directory (default: ./output)
- `TLDROP_STATE_DIR` - State directory (default: ./state)
