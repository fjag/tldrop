"""CLI entry point for tldrop."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta, timezone

import click

from tldrop.config import Settings
from tldrop.core.orchestrator import Orchestrator


def setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


@click.command()
@click.option(
    "--topics",
    "-t",
    required=True,
    help="Comma-separated topics of interest (e.g., 'SageMaker,Bedrock,Glue')",
)
@click.option(
    "--site",
    "-s",
    default=None,
    help="Blog site URL (default: https://aws.amazon.com)",
)
@click.option(
    "--feeds",
    "-f",
    default=None,
    help="Comma-separated feed paths (e.g., '/blogs/ml/feed/,/blogs/aws/feed/')",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output directory (default: ./output)",
)
@click.option(
    "--format",
    "formats",
    default="md",
    help="Output formats, comma-separated: md,html (default: md)",
)
@click.option(
    "--since",
    default=None,
    help="Only process posts after this date (YYYY-MM-DD)",
)
@click.option(
    "--days",
    "-d",
    type=int,
    default=None,
    help="Only process posts from the last N days",
)
@click.option(
    "--git-push",
    is_flag=True,
    help="Commit and push output files to git",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be processed without making LLM calls or writing files",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose logging",
)
def main(
    topics: str,
    site: str | None,
    feeds: str | None,
    output: str | None,
    formats: str,
    since: str | None,
    days: int | None,
    git_push: bool,
    dry_run: bool,
    verbose: bool,
) -> None:
    """
    tldrop - Surface new blog posts and generate summaries.

    Monitor a trusted blog site for new posts matching your topics of interest,
    then generate detailed summaries with key takeaways.

    Example:

        tldrop --topics "SageMaker,Bedrock,Glue"
    """
    setup_logging(verbose)
    logger = logging.getLogger(__name__)

    # Parse topics
    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    if not topic_list:
        click.echo("Error: At least one topic is required", err=True)
        sys.exit(1)

    # Parse formats
    format_list = [f.strip() for f in formats.split(",") if f.strip()]

    # Parse timeline filter (--days takes precedence over --since)
    since_dt = None
    if days is not None:
        if days < 1:
            click.echo("Error: --days must be at least 1", err=True)
            sys.exit(1)
        since_dt = datetime.now(timezone.utc) - timedelta(days=days)
    elif since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            click.echo(f"Error: Invalid date format '{since}'. Use YYYY-MM-DD", err=True)
            sys.exit(1)

    # Build settings with overrides
    try:
        settings_kwargs = {}
        if site:
            settings_kwargs["site"] = site
        if feeds:
            settings_kwargs["feeds"] = [f.strip() for f in feeds.split(",")]
        if output:
            settings_kwargs["output_dir"] = output

        settings = Settings(**settings_kwargs)
    except Exception as e:
        click.echo(f"Error: Configuration failed: {e}", err=True)
        sys.exit(1)

    # Run the pipeline
    logger.info(f"tldrop starting - site: {settings.site}")

    orchestrator = Orchestrator(settings)

    try:
        result = asyncio.run(
            orchestrator.run(
                topics=topic_list,
                since=since_dt,
                formats=format_list,
                git_push=git_push,
                dry_run=dry_run,
            )
        )
    except KeyboardInterrupt:
        click.echo("\nInterrupted")
        sys.exit(130)
    except Exception as e:
        logger.exception("Pipeline failed")
        click.echo(f"Error: {e}", err=True)
        sys.exit(1)

    # Report results
    click.echo()
    click.echo(str(result))

    if result.files_written:
        click.echo()
        click.echo("Files written:")
        for path in result.files_written:
            click.echo(f"  {path}")

    if result.errors:
        click.echo()
        click.echo("Errors:")
        for error in result.errors:
            click.echo(f"  {error}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
