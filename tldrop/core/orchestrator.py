"""Orchestrator - Coordinates the tldrop pipeline."""

import logging
from datetime import datetime
from pathlib import Path

from tldrop.agents.feed import FeedAgent
from tldrop.agents.output import OutputAgent
from tldrop.agents.summarizer import SummarizerAgent
from tldrop.config import Settings
from tldrop.core.fetcher import SiteFetcher
from tldrop.core.state import StateManager
from tldrop.models.post import Summary

logger = logging.getLogger(__name__)


class PipelineResult:
    """Result of a pipeline run."""

    def __init__(self):
        self.posts_found: int = 0
        self.posts_relevant: int = 0
        self.summaries_generated: int = 0
        self.files_written: list[Path] = []
        self.errors: list[str] = []

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    def __str__(self) -> str:
        status = "SUCCESS" if self.success else "COMPLETED WITH ERRORS"
        return (
            f"{status}: Found {self.posts_found} posts, "
            f"{self.posts_relevant} relevant, "
            f"{self.summaries_generated} summaries written"
        )


class Orchestrator:
    """
    Main pipeline coordinator for tldrop.

    Wires together all agents and manages the flow:
    FeedAgent -> SummarizerAgent -> OutputAgent
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state_manager = StateManager(settings)

    async def run(
        self,
        topics: list[str],
        since: datetime | None = None,
        formats: list[str] | None = None,
        git_push: bool = False,
        dry_run: bool = False,
    ) -> PipelineResult:
        """
        Execute the full pipeline.

        Args:
            topics: Topics of interest for filtering
            since: Only process posts after this time (overrides state)
            formats: Output formats (default: ["md"])
            git_push: Whether to push to git after writing
            dry_run: If True, skip LLM calls and file writes

        Returns:
            PipelineResult with statistics and any errors
        """
        result = PipelineResult()

        if formats is None:
            formats = ["md"]

        logger.info(f"Starting tldrop pipeline for site: {self.settings.site}")
        logger.info(f"Topics: {', '.join(topics)}")

        async with SiteFetcher(self.settings) as fetcher:
            # Phase 1: Fetch feeds and detect new posts
            feed_agent = FeedAgent(self.settings, fetcher, self.state_manager)

            try:
                posts = await feed_agent.run(since=since)
                result.posts_found = len(posts)
            except Exception as e:
                logger.error(f"Feed fetch failed: {e}")
                result.errors.append(f"Feed fetch failed: {e}")
                return result

            if not posts:
                logger.info("No new posts found")
                return result

            logger.info(f"Found {len(posts)} new posts")

            if dry_run:
                logger.info("DRY RUN - Skipping summarization and output")
                for post in posts:
                    logger.info(f"  Would process: {post.title}")
                result.posts_relevant = len(posts)  # Assume all relevant in dry run
                return result

            # Phase 2: Filter and summarize
            summarizer = SummarizerAgent(self.settings)

            try:
                summaries = await summarizer.run(posts, topics)
                result.posts_relevant = len(summaries)
                result.summaries_generated = len(summaries)
            except Exception as e:
                logger.error(f"Summarization failed: {e}")
                result.errors.append(f"Summarization failed: {e}")
                return result

            if not summaries:
                logger.info("No relevant posts after filtering")
                return result

            # Phase 3: Output
            output_agent = OutputAgent(self.settings)

            try:
                paths = await output_agent.run(
                    summaries,
                    formats=formats,
                    git_push=git_push,
                )
                result.files_written = paths
            except Exception as e:
                logger.error(f"Output failed: {e}")
                result.errors.append(f"Output failed: {e}")
                # Don't return - we still want to update state

            # Update state
            for summary in summaries:
                self.state_manager.mark_processed(summary.post.url)
            self.state_manager.set_last_run()
            self.state_manager.save()

        logger.info(str(result))
        return result
