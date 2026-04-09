# Technical Specification: tldrop

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI (cli.py)                         │
│                 Parse args, configure, run                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                   Orchestrator (orchestrator.py)             │
│              Coordinate agents, manage state                 │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
   │  FeedAgent  │    │ Summarizer  │    │ OutputAgent │
   │             │    │   Agent     │    │             │
   │ • RSS fetch │    │ • Filter    │    │ • Render    │
   │ • Parse     │    │ • Summarize │    │ • Write     │
   │ • Detect    │    │             │    │ • Git ops   │
   └─────────────┘    └─────────────┘    └─────────────┘
          │                   │
          └─────────┬─────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                 SiteFetcher (fetcher.py)                     │
│           ALL network requests go through here               │
│                 Domain validation enforced                   │
└─────────────────────────────────────────────────────────────┘
```

## Security Model

### Single-Site Enforcement

`SiteFetcher` is the **only** component that makes HTTP requests. It validates every URL against the configured domain before fetching.

```python
def _validate_url(self, url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc != self.allowed_domain:
        raise DomainViolationError(...)
```

**Blocked patterns:**
- Different domains (`example.com`)
- Subdomains (`docs.aws.amazon.com`)
- Similar-looking domains (`aws-amazon.com`)
- Protocol handlers (`javascript:`, `data:`)

### Secret Handling

- API keys loaded via `pydantic.SecretStr`
- Never logged or printed
- Loaded from environment or `.env` file

## Data Flow

```
1. CLI parses args
2. Orchestrator starts pipeline
3. FeedAgent:
   - Fetches RSS feeds via SiteFetcher
   - Parses with feedparser
   - Filters by timestamp (--days or --since)
   - Deduplicates by URL
4. SummarizerAgent:
   - Keyword filter (cheap, local)
   - LLM filter for ambiguous posts (Haiku)
   - Generate summaries (Sonnet)
5. OutputAgent:
   - Render Jinja2 templates
   - Write to output/{domain}/
   - Optional: git commit & push
6. State saved to state/{domain}.json
```

## Data Models

```python
@dataclass
class Post:
    url: str
    title: str
    published: datetime
    author: str
    categories: list[str]
    excerpt: str
    content: str

@dataclass
class Summary:
    post: Post
    tldr: str
    key_takeaways: list[str]
    whats_new: str
    relevance: str
    action_items: list[str]
```

## State Management

Per-domain JSON file (`state/{domain}.json`):

```json
{
  "version": 1,
  "last_run": "2026-04-09T12:00:00Z",
  "processed_urls": ["https://...", "https://..."]
}
```

- `last_run`: Default cutoff for new post detection
- `processed_urls`: Deduplication (max 500, FIFO)

## Configuration

| Setting | Env Var | Default |
|---------|---------|---------|
| API Key | `ANTHROPIC_API_KEY` | (required) |
| Site | `TLDROP_SITE` | `https://aws.amazon.com` |
| Feeds | `TLDROP_FEEDS` | ML, Big Data, AWS feeds |
| Output | `TLDROP_OUTPUT_DIR` | `./output` |
| State | `TLDROP_STATE_DIR` | `./state` |

## Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `httpx` | Async HTTP client |
| `feedparser` | RSS parsing |
| `beautifulsoup4` | HTML parsing |
| `anthropic` | Claude API |
| `jinja2` | Template rendering |
| `pydantic` | Config validation |

## File Structure

```
tldrop/
├── cli.py                 # Entry point
├── config.py              # Settings
├── core/
│   ├── fetcher.py         # SiteFetcher (security layer)
│   ├── state.py           # State persistence
│   └── orchestrator.py    # Pipeline coordination
├── agents/
│   ├── feed.py            # RSS fetching
│   ├── summarizer.py      # LLM summarization
│   └── output.py          # File writing
├── models/
│   └── post.py            # Data classes
└── templates/
    ├── summary.md.j2
    └── summary.html.j2
```

## Error Handling

| Error | Behavior |
|-------|----------|
| Network timeout | Retry 3x with backoff, skip post |
| Invalid domain | Raise immediately, abort run |
| LLM API error | Retry 3x, skip post with warning |
| Git push fail | Log warning, continue |

## Testing

Security-critical tests in `tests/test_fetcher.py`:
- Domain validation (exact match only)
- Subdomain blocking
- Malicious URL patterns
- Protocol handlers

## Future Considerations

- **Multiple sites**: Run separately, output namespaced by domain
- **Caching**: Local cache of fetched content
- **Notifications**: Webhook on new summaries
