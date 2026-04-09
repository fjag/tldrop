# tldrop

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
