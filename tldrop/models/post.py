"""Data models for blog posts and summaries."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Post:
    """Represents a blog post fetched from RSS."""

    url: str
    title: str
    published: datetime
    author: str = ""
    categories: list[str] = field(default_factory=list)
    excerpt: str = ""
    content: str = ""

    def slug(self) -> str:
        """Generate a URL-safe slug from the title."""
        import re

        slug = self.title.lower()
        slug = re.sub(r"[^a-z0-9\s-]", "", slug)
        slug = re.sub(r"[\s_]+", "-", slug)
        slug = re.sub(r"-+", "-", slug)
        return slug.strip("-")[:80]

    def filename(self, ext: str = "md") -> str:
        """Generate filename: YYYY-MM-DD-slug.ext"""
        date_prefix = self.published.strftime("%Y-%m-%d")
        return f"{date_prefix}-{self.slug()}.{ext}"


@dataclass
class Summary:
    """Represents a generated summary for a post."""

    post: Post
    tldr: str
    key_takeaways: list[str]
    whats_new: str = ""
    relevance: str = ""
    action_items: list[str] = field(default_factory=list)
    topics_matched: list[str] = field(default_factory=list)
