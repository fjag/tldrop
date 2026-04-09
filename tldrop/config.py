"""Configuration management for tldrop."""

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from urllib.parse import urlparse


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_prefix="TLDROP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # API key (required for summarization, optional for dry-run)
    # Accepts both ANTHROPIC_API_KEY and TLDROP_ANTHROPIC_API_KEY
    anthropic_api_key: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "TLDROP_ANTHROPIC_API_KEY"),
    )

    # Site configuration
    site: str = "https://aws.amazon.com"
    feeds: list[str] = [
        "/blogs/machine-learning/feed/",
        "/blogs/big-data/feed/",
        "/blogs/aws/feed/",
    ]

    # Output configuration
    output_dir: str = "./output"
    state_dir: str = "./state"

    # Request configuration
    request_timeout: float = 30.0
    request_delay: float = 1.0
    max_retries: int = 3
    user_agent: str = "tldrop/0.1 (personal blog monitor)"

    # LLM configuration
    summarizer_model: str = "claude-sonnet-4-20250514"
    filter_model: str = "claude-haiku-4-20250514"

    @field_validator("site")
    @classmethod
    def validate_site(cls, v: str) -> str:
        """Ensure site is a valid URL with scheme."""
        parsed = urlparse(v)
        if not parsed.scheme:
            v = f"https://{v}"
            parsed = urlparse(v)
        if not parsed.netloc:
            raise ValueError(f"Invalid site URL: {v}")
        # Normalize: remove trailing slash
        return f"{parsed.scheme}://{parsed.netloc}"

    @property
    def allowed_domain(self) -> str:
        """Extract the allowed domain from site URL."""
        return urlparse(self.site).netloc

    def get_feed_urls(self) -> list[str]:
        """Get full URLs for all configured feeds."""
        return [f"{self.site}{feed}" for feed in self.feeds]
