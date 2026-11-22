from __future__ import annotations
"""
IssueLens Configuration Management

Reads configuration from environment variables using pydantic-settings.
Secrets are NEVER hardcoded — they come from .env files or the system environment.
"""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.
    
    pydantic-settings automatically reads from a .env file if present,
    and validates types. Missing optional values get sensible defaults.
    """
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore unknown env vars
    )
    
    # --- AI Configuration ---
    gemini_api_key: str | None = None  # Optional: AI features degrade gracefully
    gemini_model: str = "gemini-3.8-flash"
    
    # --- GitHub Configuration ---
    github_token: str | None = None  # Optional: for higher rate limits
    github_api_base: str = "https://api.github.com"
    
    # --- Application ---
    app_env: str = "development"
    log_level: str = "INFO"
    
    # --- Database ---
    database_url: str = "sqlite+aiosqlite:///issueLens.db"
    
    @property
    def is_ai_available(self) -> bool:
        """Check if AI features can be used."""
        return self.gemini_api_key is not None and self.gemini_api_key != "your_gemini_api_key_here"
    
    @property
    def is_github_authenticated(self) -> bool:
        """Check if GitHub token is configured."""
        return self.github_token is not None and self.github_token != "your_github_token_here"


# Singleton instance — imported throughout the app
# This gets created once when the module is first imported
_settings: Settings | None = None


def get_settings() -> Settings:
    """Get the application settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings() -> None:
    """Reset settings singleton (useful for testing)."""
    global _settings
    _settings = None
