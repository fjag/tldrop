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

FILTER_PROMPT = """Given the following blog post title, categories, and excerpt, determine if it is relevant to the topics: {topics}

Title: {title}
Categories: {categories}
Excerpt: {excerpt}

Respond with only "YES" or "NO"."""


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

    async def is_relevant(self, post: Post, topics: list[str]) -> bool:
        """
        Check if a post is relevant to the given topics.

        Uses Claude Haiku for cheap, fast filtering.
        """
        # First, try simple keyword matching
        topics_lower = [t.lower() for t in topics]
        searchable = f"{post.title} {' '.join(post.categories)} {post.excerpt}".lower()

        for topic in topics_lower:
            if topic in searchable:
                logger.debug(f"Keyword match for '{topic}' in: {post.title}")
                return True

        # If no keyword match, use LLM for ambiguous cases
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
                max_tokens=10,
                messages=[{"role": "user", "content": prompt}],
            )
            answer = response.content[0].text.strip().upper()
            return answer == "YES"
        except Exception as e:
            logger.warning(f"LLM filter failed, including post: {e}")
            return True  # Include on error to avoid missing relevant posts

    async def summarize(self, post: Post, topics: list[str]) -> Summary:
        """
        Generate a detailed summary for a post.

        Uses Claude Sonnet for quality output.
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
            topics=", ".join(topics),
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
                topics_matched=topics,
            )

        except Exception as e:
            logger.error(f"Failed to summarize {post.title}: {e}")
            # Return a minimal summary on error
            return Summary(
                post=post,
                tldr=f"[Summary generation failed: {e}]",
                key_takeaways=[],
                topics_matched=topics,
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

        # Filter by relevance
        if skip_filter:
            relevant_posts = posts
        else:
            relevant_posts = []
            for post in posts:
                if await self.is_relevant(post, topics):
                    relevant_posts.append(post)
                else:
                    logger.info(f"Filtered out (not relevant): {post.title}")

        logger.info(f"Processing {len(relevant_posts)}/{len(posts)} relevant posts")

        # Generate summaries
        summaries = []
        for post in relevant_posts:
            summary = await self.summarize(post, topics)
            summaries.append(summary)

        return summaries
