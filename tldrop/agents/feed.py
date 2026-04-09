"""FeedAgent - Parses RSS feeds and detects new posts."""

import logging
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser

from tldrop.agents.base import BaseAgent
from tldrop.config import Settings
from tldrop.core.fetcher import SiteFetcher
from tldrop.core.state import StateManager
from tldrop.models.post import Post

logger = logging.getLogger(__name__)


class FeedAgent(BaseAgent):
    """
    Agent responsible for fetching and parsing RSS feeds.

    Detects new posts based on publication date and processed URL history.
    """

    def __init__(
        self,
        settings: Settings,
        fetcher: SiteFetcher,
        state_manager: StateManager,
    ):
        super().__init__(settings)
        self.fetcher = fetcher
        self.state_manager = state_manager

    def _parse_date(self, entry: dict) -> datetime:
        """Parse publication date from feed entry."""
        # Try different date fields
        for field in ["published", "updated", "created"]:
            if field in entry:
                try:
                    return parsedate_to_datetime(entry[field])
                except (ValueError, TypeError):
                    pass

        # Try parsed versions
        for field in ["published_parsed", "updated_parsed", "created_parsed"]:
            if field in entry and entry[field]:
                try:
                    from time import mktime
                    return datetime.fromtimestamp(mktime(entry[field]), tz=timezone.utc)
                except (ValueError, TypeError, OverflowError):
                    pass

        # Fallback to now
        logger.warning(f"Could not parse date for entry, using current time")
        return datetime.now(timezone.utc)

    def _entry_to_post(self, entry: dict) -> Post:
        """Convert a feedparser entry to a Post object."""
        # Extract content - prefer content:encoded, fall back to summary
        content = ""
        if "content" in entry and entry["content"]:
            content = entry["content"][0].get("value", "")
        elif "summary" in entry:
            content = entry["summary"]

        # Extract categories/tags
        categories = []
        if "tags" in entry:
            categories = [tag.get("term", "") for tag in entry["tags"] if tag.get("term")]

        return Post(
            url=entry.get("link", ""),
            title=entry.get("title", "Untitled"),
            published=self._parse_date(entry),
            author=entry.get("author", ""),
            categories=categories,
            excerpt=entry.get("summary", "")[:500] if "summary" in entry else "",
            content=content,
        )

    async def fetch_feed(self, feed_url: str) -> list[Post]:
        """Fetch and parse a single RSS feed."""
        logger.info(f"Fetching feed: {feed_url}")

        try:
            feed_content = await self.fetcher.fetch(feed_url)
        except Exception as e:
            logger.error(f"Failed to fetch feed {feed_url}: {e}")
            return []

        feed = feedparser.parse(feed_content)

        if feed.bozo:
            logger.warning(f"Feed parse warning for {feed_url}: {feed.bozo_exception}")

        posts = []
        for entry in feed.entries:
            try:
                post = self._entry_to_post(entry)
                if post.url:  # Only include posts with valid URLs
                    posts.append(post)
            except Exception as e:
                logger.warning(f"Failed to parse entry: {e}")

        logger.info(f"Found {len(posts)} posts in feed")
        return posts

    def filter_new_posts(
        self,
        posts: list[Post],
        since: datetime | None = None,
    ) -> list[Post]:
        """
        Filter posts to only include new ones.

        A post is considered new if:
        1. It was published after `since` (or last_run if since is None)
        2. Its URL hasn't been processed before
        """
        # Get the cutoff time
        if since is None:
            since = self.state_manager.get_last_run()

        new_posts = []
        for post in posts:
            # Skip if already processed
            if self.state_manager.is_processed(post.url):
                logger.debug(f"Skipping already processed: {post.title}")
                continue

            # Skip if older than cutoff (if we have one)
            if since and post.published < since:
                logger.debug(f"Skipping old post: {post.title} ({post.published})")
                continue

            new_posts.append(post)

        logger.info(f"Filtered to {len(new_posts)} new posts")
        return new_posts

    def deduplicate(self, posts: list[Post]) -> list[Post]:
        """Remove duplicate posts based on URL."""
        seen_urls = set()
        unique_posts = []

        for post in posts:
            if post.url not in seen_urls:
                seen_urls.add(post.url)
                unique_posts.append(post)
            else:
                logger.debug(f"Deduplicating: {post.title}")

        if len(posts) != len(unique_posts):
            logger.info(f"Removed {len(posts) - len(unique_posts)} duplicate posts")

        return unique_posts

    async def run(
        self,
        feed_urls: list[str] | None = None,
        since: datetime | None = None,
    ) -> list[Post]:
        """
        Fetch all feeds and return new posts.

        Args:
            feed_urls: List of feed URLs to fetch (defaults to configured feeds)
            since: Only include posts published after this time

        Returns:
            List of new Post objects, deduplicated and sorted by date
        """
        if feed_urls is None:
            feed_urls = self.settings.get_feed_urls()

        all_posts = []
        for feed_url in feed_urls:
            posts = await self.fetch_feed(feed_url)
            all_posts.extend(posts)

        # Deduplicate posts that appear in multiple feeds
        unique_posts = self.deduplicate(all_posts)

        # Filter to only new posts
        new_posts = self.filter_new_posts(unique_posts, since=since)

        # Sort by publication date (newest first)
        new_posts.sort(key=lambda p: p.published, reverse=True)

        return new_posts
