"""OutputAgent - Renders summaries to files and handles git operations."""

import logging
import re
import subprocess
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from tldrop.agents.base import BaseAgent
from tldrop.config import Settings
from tldrop.models.post import Summary

logger = logging.getLogger(__name__)


class OutputAgent(BaseAgent):
    """
    Agent responsible for rendering summaries and saving files.

    Handles Markdown/HTML output and optional git operations.
    """

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.output_dir = Path(settings.output_dir)
        self.env = Environment(
            loader=PackageLoader("tldrop", "templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and invalid chars."""
        # Remove any path components
        filename = Path(filename).name
        # Remove potentially dangerous characters
        filename = re.sub(r"[^\w\-.]", "", filename)
        # Prevent empty filename
        if not filename or filename.startswith("."):
            filename = "untitled" + filename
        return filename

    def _get_output_path(self, summary: Summary, ext: str = "md") -> Path:
        """Get the output path for a summary file."""
        # Site as top-level directory
        site_dir = self.output_dir / self.settings.allowed_domain
        site_dir.mkdir(parents=True, exist_ok=True)

        # Sanitized filename
        filename = self._sanitize_filename(summary.post.filename(ext))

        return site_dir / filename

    def render_markdown(self, summary: Summary) -> str:
        """Render a summary to Markdown format."""
        template = self.env.get_template("summary.md.j2")
        return template.render(summary=summary, post=summary.post)

    def render_html(self, summary: Summary) -> str:
        """Render a summary to HTML format."""
        template = self.env.get_template("summary.html.j2")
        return template.render(summary=summary, post=summary.post)

    def write_file(self, summary: Summary, formats: list[str]) -> list[Path]:
        """
        Write summary to file(s) in the specified formats.

        Args:
            summary: The summary to write
            formats: List of formats ("md", "html")

        Returns:
            List of paths to written files
        """
        written_paths = []

        for fmt in formats:
            if fmt == "md":
                content = self.render_markdown(summary)
            elif fmt == "html":
                content = self.render_html(summary)
            else:
                logger.warning(f"Unknown format: {fmt}")
                continue

            path = self._get_output_path(summary, fmt)
            path.write_text(content, encoding="utf-8")
            logger.info(f"Wrote: {path}")
            written_paths.append(path)

        return written_paths

    def git_commit(self, paths: list[Path], message: str) -> bool:
        """
        Stage and commit the given files.

        Returns True if successful, False otherwise.
        """
        if not paths:
            return True

        try:
            # Stage files
            subprocess.run(
                ["git", "add"] + [str(p) for p in paths],
                cwd=self.output_dir,
                check=True,
                capture_output=True,
            )

            # Commit
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.output_dir,
                check=True,
                capture_output=True,
            )

            logger.info(f"Committed {len(paths)} files")
            return True

        except subprocess.CalledProcessError as e:
            logger.warning(f"Git commit failed: {e.stderr.decode() if e.stderr else e}")
            return False

    def git_push(self) -> bool:
        """
        Push commits to remote.

        Returns True if successful, False otherwise.
        """
        try:
            subprocess.run(
                ["git", "push"],
                cwd=self.output_dir,
                check=True,
                capture_output=True,
            )
            logger.info("Pushed to remote")
            return True

        except subprocess.CalledProcessError as e:
            logger.warning(f"Git push failed: {e.stderr.decode() if e.stderr else e}")
            return False

    async def run(
        self,
        summaries: list[Summary],
        formats: list[str] | None = None,
        git_push: bool = False,
    ) -> list[tuple[Summary, list[Path]]]:
        """
        Write all summaries to files and optionally push to git.

        Returns a list of (summary, paths) pairs. `paths` is empty if that
        summary's write failed — the caller uses this to avoid marking a
        post as processed when it was never actually written to disk.
        """
        if formats is None:
            formats = ["md"]

        results: list[tuple[Summary, list[Path]]] = []

        for summary in summaries:
            try:
                paths = self.write_file(summary, formats)
                results.append((summary, paths))
            except Exception as e:
                logger.error(f"Failed to write output for '{summary.post.title}': {e}")
                results.append((summary, []))

        all_paths = [p for _, paths in results for p in paths]

        if git_push and all_paths:
            post_count = sum(1 for _, paths in results if paths)
            message = f"tldrop: Add {post_count} summary{'s' if post_count != 1 else ''}"
            if self.git_commit(all_paths, message):
                self.git_push()

        return results
