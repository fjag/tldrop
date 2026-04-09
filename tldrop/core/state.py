"""State management for tracking processed posts."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tldrop.config import Settings

logger = logging.getLogger(__name__)

STATE_VERSION = 1
MAX_PROCESSED_URLS = 500


class StateManager:
    """Manages persistent state for tracking processed posts."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.state_dir = Path(settings.state_dir)
        self.state_file = self.state_dir / f"{settings.allowed_domain}.json"
        self._state: dict[str, Any] | None = None

    def _ensure_dir(self) -> None:
        """Ensure state directory exists."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

    def _default_state(self) -> dict[str, Any]:
        """Return default state for a new run."""
        return {
            "version": STATE_VERSION,
            "last_run": None,
            "processed_urls": [],
        }

    def load(self) -> dict[str, Any]:
        """Load state from disk or return default state."""
        if self._state is not None:
            return self._state

        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    self._state = json.load(f)
                logger.debug(f"Loaded state from {self.state_file}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load state: {e}, starting fresh")
                self._state = self._default_state()
        else:
            logger.debug("No existing state file, starting fresh")
            self._state = self._default_state()

        return self._state

    def save(self) -> None:
        """Save current state to disk."""
        if self._state is None:
            return

        self._ensure_dir()

        # Trim processed URLs to prevent unbounded growth
        if len(self._state["processed_urls"]) > MAX_PROCESSED_URLS:
            self._state["processed_urls"] = self._state["processed_urls"][-MAX_PROCESSED_URLS:]

        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2, default=str)

        logger.debug(f"Saved state to {self.state_file}")

    def get_last_run(self) -> datetime | None:
        """Get the timestamp of the last successful run."""
        state = self.load()
        last_run = state.get("last_run")
        if last_run:
            return datetime.fromisoformat(last_run)
        return None

    def set_last_run(self, timestamp: datetime | None = None) -> None:
        """Set the last run timestamp (defaults to now)."""
        state = self.load()
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)
        state["last_run"] = timestamp.isoformat()

    def is_processed(self, url: str) -> bool:
        """Check if a URL has already been processed."""
        state = self.load()
        return url in state["processed_urls"]

    def mark_processed(self, url: str) -> None:
        """Mark a URL as processed."""
        state = self.load()
        if url not in state["processed_urls"]:
            state["processed_urls"].append(url)

    def get_processed_count(self) -> int:
        """Get the number of processed URLs."""
        state = self.load()
        return len(state["processed_urls"])
