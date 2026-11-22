from __future__ import annotations
"""Tests for configuration management."""

import os
import pytest
from app.config import Settings, reset_settings


class TestSettings:
    """Test the Settings configuration class."""
    
    def setup_method(self):
        """Reset settings singleton before each test."""
        reset_settings()
    
    def test_default_settings(self):
        """Settings should have sensible defaults."""
        settings = Settings(
            _env_file=None,  # Don't load .env file in tests
        )
        assert settings.gemini_api_key is None
        assert settings.gemini_model == "gemini-3.8-flash"
        assert settings.github_token is None
        assert settings.app_env == "development"
        assert settings.log_level == "INFO"
    
    def test_ai_unavailable_without_key(self):
        """AI should be marked unavailable when no key is set."""
        settings = Settings(_env_file=None)
        assert settings.is_ai_available is False
    
    def test_ai_unavailable_with_placeholder(self):
        """AI should be unavailable with the placeholder value."""
        settings = Settings(
            gemini_api_key="your_gemini_api_key_here",
            _env_file=None,
        )
        assert settings.is_ai_available is False
    
    def test_ai_available_with_real_key(self):
        """AI should be available when a real key is set."""
        settings = Settings(
            gemini_api_key="test-key-12345",
            _env_file=None,
        )
        assert settings.is_ai_available is True
    
    def test_github_unauthenticated_without_token(self):
        """GitHub should be unauthenticated without a token."""
        settings = Settings(_env_file=None)
        assert settings.is_github_authenticated is False
    
    def test_github_authenticated_with_token(self):
        """GitHub should be authenticated with a real token."""
        settings = Settings(
            github_token="ghp_test12345",
            _env_file=None,
        )
        assert settings.is_github_authenticated is True
    
    def test_github_unauthenticated_with_placeholder(self):
        """GitHub should be unauthenticated with the placeholder."""
        settings = Settings(
            github_token="your_github_token_here",
            _env_file=None,
        )
        assert settings.is_github_authenticated is False
