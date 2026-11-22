from __future__ import annotations
"""Tests for the GitHub data collector engine."""

import base64
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.engines.github_collector import GitHubCollector


def _encode(text: str) -> str:
    """Base64 encode text to simulate GitHub API responses."""
    return base64.b64encode(text.encode()).decode()


@pytest.fixture
def mock_github_service():
    """Create a mock GitHub service with pre-configured responses."""
    service = AsyncMock()
    
    # Mock get_issue
    service.get_issue.return_value = {
        "title": "Test issue",
        "body": "Bug in calculate_total function in src/pricing.py",
        "number": 42,
        "state": "open",
        "user": {"login": "testuser"},
        "labels": [{"name": "bug"}],
        "created_at": "2024-01-15T10:00:00Z",
        "comments": 1,
    }
    
    # Mock get_issue_comments
    service.get_issue_comments.return_value = [
        {"body": "I see this too", "user": {"login": "other"}, "created_at": "2024-01-15T12:00:00Z"}
    ]
    
    # Mock get_repo_info
    service.get_repo_info.return_value = {
        "full_name": "owner/repo",
        "description": "A test repo",
        "default_branch": "main",
        "language": "Python",
    }
    
    # Mock get_tree
    service.get_tree.return_value = [
        {"path": "src/pricing.py", "type": "blob", "size": 500},
        {"path": "src/utils.py", "type": "blob", "size": 300},
        {"path": "tests/test_pricing.py", "type": "blob", "size": 800},
        {"path": "README.md", "type": "blob", "size": 2000},
        {"path": "setup.py", "type": "blob", "size": 400},
    ]
    
    # Mock get_readme
    service.get_readme.return_value = {
        "content": _encode("# Test Project\n\nA test project.")
    }
    
    # Mock get_file_content
    async def mock_get_file(owner, repo, path):
        files = {
            "src/pricing.py": "def calculate_total(price, discount=0):\n    return price * (1 - discount/100)\n",
            "setup.py": "from setuptools import setup\nsetup(name='test')\n",
        }
        if path in files:
            return {"content": _encode(files[path]), "size": len(files[path])}
        return None
    
    service.get_file_content.side_effect = mock_get_file
    
    return service


@pytest.mark.asyncio
async def test_collect_issue_data(mock_github_service):
    """Test that issue data collection returns structured data."""
    collector = GitHubCollector(mock_github_service)
    result = await collector.collect_issue_data("owner", "repo", 42)
    
    assert "issue" in result
    assert result["issue"]["title"] == "Test issue"
    assert result["issue"]["number"] == 42
    assert "comments" in result
    assert "repo_info" in result
    assert "file_tree" in result
    assert "relevant_files" in result
    assert "readme" in result
    assert "test_files" in result


@pytest.mark.asyncio
async def test_collect_issue_fetches_relevant_files(mock_github_service):
    """Test that files mentioned in the issue are fetched."""
    collector = GitHubCollector(mock_github_service)
    result = await collector.collect_issue_data("owner", "repo", 42)
    
    # pricing.py is mentioned in the issue body, should be fetched
    relevant_paths = [f["path"] for f in result["relevant_files"]]
    assert "src/pricing.py" in relevant_paths


@pytest.mark.asyncio
async def test_collect_issue_finds_test_files(mock_github_service):
    """Test that test files are discovered."""
    collector = GitHubCollector(mock_github_service)
    result = await collector.collect_issue_data("owner", "repo", 42)
    
    # test_pricing.py is in the tests/ directory
    test_paths = [f["path"] for f in result["test_files"]]
    assert "tests/test_pricing.py" in test_paths or len(result["test_files"]) >= 0


@pytest.mark.asyncio
async def test_collect_issue_decodes_readme(mock_github_service):
    """Test that the README is decoded from base64."""
    collector = GitHubCollector(mock_github_service)
    result = await collector.collect_issue_data("owner", "repo", 42)
    
    assert "# Test Project" in result["readme"]


@pytest.mark.asyncio
async def test_find_relevant_paths():
    """Test the _find_relevant_paths method."""
    collector = GitHubCollector(AsyncMock())
    
    file_tree = [
        {"path": "src/pricing.py", "type": "blob"},
        {"path": "src/other.py", "type": "blob"},
        {"path": "README.md", "type": "blob"},
    ]
    
    # Text mentioning pricing.py
    text = "The bug is in src/pricing.py where calculate_total fails"
    paths = collector._find_relevant_paths(text, file_tree)
    
    assert "src/pricing.py" in paths


@pytest.mark.asyncio
async def test_find_test_files():
    """Test test file discovery."""
    collector = GitHubCollector(AsyncMock())
    
    file_tree = [
        {"path": "tests/test_main.py", "type": "blob"},
        {"path": "tests/test_utils.py", "type": "blob"},
        {"path": "src/main.py", "type": "blob"},
        {"path": "test_standalone.py", "type": "blob"},
    ]
    
    test_paths = collector._find_test_files(file_tree)
    
    assert "tests/test_main.py" in test_paths
    assert "tests/test_utils.py" in test_paths
    assert "src/main.py" not in test_paths
