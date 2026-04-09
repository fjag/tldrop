"""SiteFetcher - The single point of network egress with domain enforcement."""

import asyncio
import logging
from urllib.parse import urlparse, urljoin

import httpx

from tldrop.config import Settings

logger = logging.getLogger(__name__)


class DomainViolationError(Exception):
    """Raised when a URL violates the allowed domain constraint."""

    pass


class FetchError(Exception):
    """Raised when a fetch operation fails after retries."""

    pass


class SiteFetcher:
    """
    Security-critical HTTP client that enforces single-site access.

    ALL network requests in tldrop MUST go through this class.
    No component should import httpx directly or make network calls
    without using SiteFetcher.
    """

    def __init__(self, settings: Settings):
        self.settings = settings
        self.allowed_domain = settings.allowed_domain
        self._client: httpx.AsyncClient | None = None

    def _validate_url(self, url: str) -> str:
        """
        Validate that URL is within the allowed domain.

        Raises DomainViolationError if URL would access a different domain.
        Returns the normalized URL.
        """
        parsed = urlparse(url)

        # Handle relative URLs by joining with site base
        if not parsed.netloc:
            url = urljoin(self.settings.site, url)
            parsed = urlparse(url)

        # Strict domain check
        if parsed.netloc != self.allowed_domain:
            raise DomainViolationError(
                f"URL '{url}' is outside allowed domain '{self.allowed_domain}'. "
                f"tldrop only fetches from the configured site."
            )

        # Ensure HTTPS
        if parsed.scheme != "https":
            url = url.replace(f"{parsed.scheme}://", "https://", 1)

        return url

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.settings.request_timeout),
                headers={"User-Agent": self.settings.user_agent},
                follow_redirects=True,
            )
        return self._client

    async def fetch(self, url: str) -> str:
        """
        Fetch content from a URL within the allowed domain.

        Args:
            url: The URL to fetch (can be relative or absolute)

        Returns:
            The response body as text

        Raises:
            DomainViolationError: If URL is outside allowed domain
            FetchError: If fetch fails after retries
        """
        # CRITICAL: Validate URL before any network access
        validated_url = self._validate_url(url)

        client = await self._get_client()
        last_error: Exception | None = None

        for attempt in range(self.settings.max_retries):
            try:
                if attempt > 0:
                    # Exponential backoff
                    delay = self.settings.request_delay * (2**attempt)
                    logger.debug(f"Retry {attempt + 1}, waiting {delay}s")
                    await asyncio.sleep(delay)

                response = await client.get(validated_url)
                response.raise_for_status()

                # Rate limiting: delay before next request
                await asyncio.sleep(self.settings.request_delay)

                return response.text

            except httpx.HTTPStatusError as e:
                last_error = e
                if e.response.status_code == 429:  # Too Many Requests
                    retry_after = int(e.response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                elif e.response.status_code >= 500:
                    logger.warning(f"Server error {e.response.status_code}, retrying")
                else:
                    # Client error (4xx except 429), don't retry
                    raise FetchError(f"HTTP {e.response.status_code} for {validated_url}") from e

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"Request error: {e}")

        raise FetchError(
            f"Failed to fetch {validated_url} after {self.settings.max_retries} attempts"
        ) from last_error

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "SiteFetcher":
        return self

    async def __aexit__(self, *args) -> None:
        await self.close()
