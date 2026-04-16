"""SummarizerAgent - Generates summaries using Claude API."""

import logging
import re

from anthropic import Anthropic

from tldrop.agents.base import BaseAgent
from tldrop.config import Settings
from tldrop.models.post import Post, Summary

logger = logging.getLogger(__name__)

SUMMARY_PROMPT = """You are summarizing a technical blog post for a busy engineer.

Post Title: {title}
Post Date: {date}
Categories: {categories}
Topics of Interest: {topics}

Content:
{content}

Provide a summary in the following format (use these exact headers):

## TL;DR
2-3 sentences: What is this post about and why does it matter?

## Key Takeaways
- Bullet point 1
- Bullet point 2
- Bullet point 3
(3-5 bullets of the most important points)

## What's New
If applicable, describe new features, services, or capabilities announced. If this isn't an announcement post, write "N/A".

## Relevance
One sentence: How this relates to {topics}.

## Action Items
- Things the reader might want to try or investigate
(If none, write "None")

Keep the summary concise but complete. Use technical terms appropriately."""

FILTER_PROMPT = """You decide whether a blog post is substantively about any of these topics: {topics}

A post is substantively about a topic only if the topic is a primary subject — not a tangential mention, analogy, or "could also apply to" remark.

Title: {title}
Categories: {categories}
Excerpt: {excerpt}

Respond with ONLY a comma-separated list of matching topics from {topics}, using their exact spelling. If none match, respond with exactly: NONE"""


class SummarizerAgent(BaseAgent):
    """
    Agent responsible for filtering and summarizing posts using Claude.

    Uses Haiku for cheap topic filtering, Sonnet for quality summaries.
    """

    def __init__(self, settings: Settings):
        super().__init__(settings)
        if settings.anthropic_api_key is None:
            raise ValueError(
                "ANTHROPIC_API_KEY is required for summarization. "
                "Set it in your environment or .env file."
            )
        self.client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())

    def _extract_section(self, text: str, header: str) -> str:
        """Extract content under a markdown header."""
        pattern = rf"##\s*{header}\s*\n(.*?)(?=\n##|\Z)"
        match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_bullets(self, text: str) -> list[str]:
        """Extract bullet points from text."""
        bullets = []
        for line in text.split("\n"):
            line = line.strip()
            if line.startswith(("- ", "* ", "• ")):
                bullets.append(line[2:].strip())
        return bullets

    async def match_topics(self, post: Post, topics: list[str]) -> list[str]:
        """
        Return the subset of `topics` that the post is substantively about.

        Uses keyword matching first (title/categories only — the excerpt is
        too noisy for substring matching), then falls back to Claude Haiku
        for ambiguous cases. Fails closed: on LLM error, returns [].
        """
        searchable = f"{post.title} {' '.join(post.categories)}".lower()
        keyword_matches = [t for t in topics if t.lower() in searchable]
        if keyword_matches:
            logger.debug(f"Keyword match {keyword_matches} in: {post.title}")
            return keyword_matches

        logger.debug(f"No keyword match, using LLM filter for: {post.title}")

        prompt = FILTER_PROMPT.format(
            topics=", ".join(topics),
            title=post.title,
            categories=", ".join(post.categories) or "None",
            excerpt=post.excerpt[:500],
        )

        try:
            response = self.client.messages.create(
                model=self.settings.filter_model,
                max_tokens=100,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response.content[0].text.strip()
        except Exception as e:
            logger.error(f"LLM filter failed, skipping post '{post.title}': {e}")
            return []

        if answer.upper() == "NONE":
            return []

        topics_by_lower = {t.lower(): t for t in topics}
        matched: list[str] = []
        for raw in answer.split(","):
            key = raw.strip().lower()
            if key in topics_by_lower and topics_by_lower[key] not in matched:
                matched.append(topics_by_lower[key])
        return matched

    async def summarize(self, post: Post, matched_topics: list[str]) -> Summary:
        """
        Generate a detailed summary for a post.

        `matched_topics` is the subset of user topics the post is actually
        about — used both to focus the prompt and to populate
        `Summary.topics_matched` in the rendered output.
        """
        logger.info(f"Summarizing: {post.title}")

        # Truncate content if too long (rough token estimate: 4 chars per token)
        content = post.content
        max_content_chars = 50000  # ~12.5k tokens, leave room for prompt/response
        if len(content) > max_content_chars:
            content = content[:max_content_chars] + "\n\n[Content truncated...]"

        prompt = SUMMARY_PROMPT.format(
            title=post.title,
            date=post.published.strftime("%Y-%m-%d"),
            categories=", ".join(post.categories) or "None",
            topics=", ".join(matched_topics),
            content=content,
        )

        try:
            response = self.client.messages.create(
                model=self.settings.summarizer_model,
                max_tokens=1500,
                messages=[{"role": "user", "content": prompt}],
            )
            summary_text = response.content[0].text

            # Parse the structured response
            return Summary(
                post=post,
                tldr=self._extract_section(summary_text, "TL;DR"),
                key_takeaways=self._extract_bullets(
                    self._extract_section(summary_text, "Key Takeaways")
                ),
                whats_new=self._extract_section(summary_text, "What's New"),
                relevance=self._extract_section(summary_text, "Relevance"),
                action_items=self._extract_bullets(
                    self._extract_section(summary_text, "Action Items")
                ),
                topics_matched=matched_topics,
            )

        except Exception as e:
            logger.error(f"Failed to summarize {post.title}: {e}")
            # Return a minimal summary on error
            return Summary(
                post=post,
                tldr=f"[Summary generation failed: {e}]",
                key_takeaways=[],
                topics_matched=matched_topics,
            )

    async def run(
        self,
        posts: list[Post],
        topics: list[str],
        skip_filter: bool = False,
    ) -> list[Summary]:
        """
        Filter posts by relevance and generate summaries.

        Args:
            posts: List of posts to process
            topics: Topics of interest for filtering
            skip_filter: If True, skip relevance filtering

        Returns:
            List of Summary objects for relevant posts
        """
        if not posts:
            logger.info("No posts to summarize")
            return []

        # Filter by relevance; track which topics matched for each kept post.
        relevant: list[tuple[Post, list[str]]] = []
        if skip_filter:
            relevant = [(post, topics) for post in posts]
        else:
            for post in posts:
                matched = await self.match_topics(post, topics)
                if matched:
                    relevant.append((post, matched))
                else:
                    logger.info(f"Filtered out (not relevant): {post.title}")

        logger.info(f"Processing {len(relevant)}/{len(posts)} relevant posts")

        summaries = []
        for post, matched in relevant:
            summary = await self.summarize(post, matched)
            summaries.append(summary)

        return summaries
