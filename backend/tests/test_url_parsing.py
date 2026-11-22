from __future__ import annotations
"""Tests for GitHub URL parsing and validation."""

import pytest
from pydantic import ValidationError
from app.models.schemas import AnalyzeRequest, parse_github_url


class TestParseGitHubUrl:
    """Test the parse_github_url function."""
    
    def test_valid_issue_url(self):
        result = parse_github_url("https://github.com/facebook/react/issues/123")
        assert result == {
            "owner": "facebook",
            "repo": "react",
            "number": 123,
            "type": "issue",
        }
    
    def test_valid_pr_url(self):
        result = parse_github_url("https://github.com/owner/repo/pull/456")
        assert result == {
            "owner": "owner",
            "repo": "repo",
            "number": 456,
            "type": "pull_request",
        }
    
    def test_url_with_trailing_slash(self):
        result = parse_github_url("https://github.com/owner/repo/issues/789/")
        assert result["number"] == 789
        assert result["type"] == "issue"
    
    def test_url_with_whitespace(self):
        result = parse_github_url("  https://github.com/owner/repo/issues/1  ")
        assert result["number"] == 1
    
    def test_url_with_hyphens_and_dots(self):
        result = parse_github_url("https://github.com/my-org/my.repo/issues/42")
        assert result["owner"] == "my-org"
        assert result["repo"] == "my.repo"
    
    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_github_url("https://github.com/invalid")
    
    def test_non_github_url_raises(self):
        with pytest.raises(ValueError, match="Cannot parse"):
            parse_github_url("https://gitlab.com/owner/repo/issues/1")
    
    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_github_url("")


class TestAnalyzeRequest:
    """Test the AnalyzeRequest Pydantic model validation."""
    
    def test_valid_issue_url(self):
        req = AnalyzeRequest(url="https://github.com/owner/repo/issues/1")
        assert req.url == "https://github.com/owner/repo/issues/1"
    
    def test_valid_pr_url(self):
        req = AnalyzeRequest(url="https://github.com/owner/repo/pull/42")
        assert req.url == "https://github.com/owner/repo/pull/42"
    
    def test_invalid_url_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(url="not-a-url")
    
    def test_non_github_url_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(url="https://gitlab.com/owner/repo/issues/1")
    
    def test_missing_number_rejected(self):
        with pytest.raises(ValidationError):
            AnalyzeRequest(url="https://github.com/owner/repo/issues/")
    
    def test_url_trimmed(self):
        req = AnalyzeRequest(url="  https://github.com/owner/repo/issues/1  ")
        assert req.url == "https://github.com/owner/repo/issues/1"
    
    def test_trailing_slash_removed(self):
        req = AnalyzeRequest(url="https://github.com/owner/repo/issues/1/")
        assert not req.url.endswith("/")
    
    def test_http_url_accepted(self):
        req = AnalyzeRequest(url="http://github.com/owner/repo/issues/1")
        assert req.url.startswith("http://")
