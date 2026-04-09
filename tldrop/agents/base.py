"""Base agent protocol for tldrop agents."""

from abc import ABC, abstractmethod
from typing import Any

from tldrop.config import Settings


class BaseAgent(ABC):
    """Abstract base class for all tldrop agents."""

    def __init__(self, settings: Settings):
        self.settings = settings

    @abstractmethod
    async def run(self, *args, **kwargs) -> Any:
        """Execute the agent's main task."""
        pass
