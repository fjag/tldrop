"""Tests for SiteFetcher - the security-critical URL validation layer."""

import pytest

from tldrop.config import Settings
from tldrop.core.fetcher import DomainViolationError, SiteFetcher


@pytest.fixture
def settings():
    """Create test settings with AWS as allowed domain."""
    return Settings(
        site="https://aws.amazon.com",
        anthropic_api_key=None,  # Not needed for fetcher tests
    )


@pytest.fixture
def fetcher(settings):
    """Create a SiteFetcher instance."""
    return SiteFetcher(settings)


class TestURLValidation:
    """Test URL validation against allowed domain."""

    def test_allows_exact_domain(self, fetcher):
        """URLs on the exact allowed domain should pass."""
        url = fetcher._validate_url("https://aws.amazon.com/blogs/ml/")
        assert url == "https://aws.amazon.com/blogs/ml/"

    def test_allows_relative_urls(self, fetcher):
        """Relative URLs should be resolved to the allowed domain."""
        url = fetcher._validate_url("/blogs/machine-learning/feed/")
        assert url == "https://aws.amazon.com/blogs/machine-learning/feed/"

    def test_upgrades_http_to_https(self, fetcher):
        """HTTP URLs should be upgraded to HTTPS."""
        url = fetcher._validate_url("http://aws.amazon.com/blogs/")
        assert url == "https://aws.amazon.com/blogs/"

    def test_blocks_different_domain(self, fetcher):
        """URLs on different domains should raise DomainViolationError."""
        with pytest.raises(DomainViolationError) as exc_info:
            fetcher._validate_url("https://example.com/")
        assert "outside allowed domain" in str(exc_info.value)
        assert "aws.amazon.com" in str(exc_info.value)

    def test_blocks_subdomain(self, fetcher):
        """Subdomains of allowed domain should be blocked (strict match)."""
        with pytest.raises(DomainViolationError):
            fetcher._validate_url("https://docs.aws.amazon.com/")

    def test_blocks_similar_looking_domain(self, fetcher):
        """Domains that look similar should be blocked."""
        malicious_urls = [
            "https://aws-amazon.com/blogs/",
            "https://aws.amazon.com.evil.com/",
            "https://awsamazon.com/",
            "https://aws.amazon.org/",
        ]
        for url in malicious_urls:
            with pytest.raises(DomainViolationError):
                fetcher._validate_url(url)

    def test_blocks_url_with_credentials(self, fetcher):
        """URLs with embedded credentials should be blocked."""
        with pytest.raises(DomainViolationError):
            fetcher._validate_url("https://user:pass@evil.com@aws.amazon.com/")

    def test_blocks_javascript_url(self, fetcher):
        """JavaScript URLs should be blocked."""
        with pytest.raises(DomainViolationError):
            fetcher._validate_url("javascript:alert(1)")

    def test_blocks_data_url(self, fetcher):
        """Data URLs should be blocked."""
        with pytest.raises(DomainViolationError):
            fetcher._validate_url("data:text/html,<script>alert(1)</script>")


class TestDomainConfiguration:
    """Test different domain configurations."""

    def test_custom_domain(self):
        """SiteFetcher should work with custom domains."""
        settings = Settings(
            site="https://engineering.example.com",
            anthropic_api_key=None,
        )
        fetcher = SiteFetcher(settings)

        # Should allow the configured domain
        url = fetcher._validate_url("https://engineering.example.com/blog/")
        assert url == "https://engineering.example.com/blog/"

        # Should block aws.amazon.com
        with pytest.raises(DomainViolationError):
            fetcher._validate_url("https://aws.amazon.com/blogs/")

    def test_domain_without_scheme(self):
        """Site configured without scheme should get https:// added."""
        settings = Settings(
            site="aws.amazon.com",
            anthropic_api_key=None,
        )
        assert settings.site == "https://aws.amazon.com"
        assert settings.allowed_domain == "aws.amazon.com"
