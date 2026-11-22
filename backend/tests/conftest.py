from __future__ import annotations
"""
Shared test fixtures and configuration.

All tests run WITHOUT external API keys.
GitHub and Gemini responses are mocked.
"""

import os
import pytest
import sys

# Ensure the app module is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Clear any real API keys from the test environment
# Tests must NEVER call real external APIs
os.environ.pop("GEMINI_API_KEY", None)
os.environ.pop("GITHUB_TOKEN", None)


@pytest.fixture
def sample_issue_data():
    """Sample GitHub issue data for testing."""
    return {
        "title": "Bug: calculate_total returns wrong value when discount is negative",
        "body": (
            "## Description\n\n"
            "The `calculate_total` function in `src/pricing.py` returns incorrect results "
            "when a negative discount is passed. Instead of raising an error, it increases "
            "the total price.\n\n"
            "## Steps to Reproduce\n\n"
            "1. Call `calculate_total(100, discount=-10)`\n"
            "2. Expected: Error or total of 100\n"
            "3. Actual: Returns 110\n\n"
            "## Environment\n"
            "- Python 3.11\n"
            "- Version 2.3.1"
        ),
        "number": 42,
        "state": "open",
        "user": {"login": "testuser"},
        "labels": [{"name": "bug"}],
        "created_at": "2024-01-15T10:30:00Z",
        "comments": 2,
    }


@pytest.fixture
def sample_pr_data():
    """Sample GitHub PR data for testing."""
    return {
        "title": "Fix: Add validation for negative discounts",
        "body": (
            "## Changes\n\n"
            "This PR adds validation to `calculate_total` to reject negative discounts.\n\n"
            "- Added `ValueError` for negative discount values\n"
            "- Added unit tests\n"
            "- Updated documentation"
        ),
        "number": 43,
        "state": "open",
        "user": {"login": "contributor"},
        "labels": [],
        "created_at": "2024-01-16T14:00:00Z",
        "comments": 0,
    }


@pytest.fixture
def sample_comments():
    """Sample issue comments."""
    return [
        {
            "body": "I can confirm this bug. It also happens with zero discount.",
            "user": {"login": "otheruser"},
            "created_at": "2024-01-15T12:00:00Z",
        }
    ]


@pytest.fixture
def sample_file_tree():
    """Sample repository file tree."""
    return [
        {"path": "src/pricing.py", "type": "blob", "size": 1500},
        {"path": "src/utils.py", "type": "blob", "size": 800},
        {"path": "src/__init__.py", "type": "blob", "size": 50},
        {"path": "tests/test_pricing.py", "type": "blob", "size": 2000},
        {"path": "tests/__init__.py", "type": "blob", "size": 0},
        {"path": "README.md", "type": "blob", "size": 3000},
        {"path": "setup.py", "type": "blob", "size": 500},
        {"path": "requirements.txt", "type": "blob", "size": 100},
    ]


@pytest.fixture
def sample_source_files():
    """Sample source file contents."""
    return [
        {
            "path": "src/pricing.py",
            "content": (
                "\"\"\"Pricing module for the application.\"\"\"\n\n\n"
                "def calculate_total(price: float, discount: float = 0) -> float:\n"
                "    \"\"\"Calculate the total price after discount.\n\n"
                "    Args:\n"
                "        price: Base price\n"
                "        discount: Discount percentage (0-100)\n\n"
                "    Returns:\n"
                "        Final price after discount\n"
                "    \"\"\"\n"
                "    return price * (1 - discount / 100)\n"
            ),
        },
        {
            "path": "src/utils.py",
            "content": (
                "\"\"\"Utility functions.\"\"\"\n\n\n"
                "def format_currency(amount: float) -> str:\n"
                "    return f'${amount:.2f}'\n"
            ),
        },
    ]


@pytest.fixture
def sample_test_files():
    """Sample test file contents."""
    return [
        {
            "path": "tests/test_pricing.py",
            "content": (
                "import pytest\n"
                "from src.pricing import calculate_total\n\n\n"
                "def test_calculate_total_basic():\n"
                "    assert calculate_total(100, 10) == 90.0\n\n\n"
                "def test_calculate_total_no_discount():\n"
                "    assert calculate_total(100) == 100.0\n\n\n"
                "def test_calculate_total_full_discount():\n"
                "    assert calculate_total(100, 100) == 0.0\n"
            ),
        }
    ]


@pytest.fixture
def sample_readme():
    """Sample README content."""
    return (
        "# Sample Project\n\n"
        "A pricing calculation library.\n\n"
        "## Installation\n\n"
        "```bash\npip install sample-project\n```\n\n"
        "## Usage\n\n"
        "```python\nfrom src.pricing import calculate_total\n"
        "total = calculate_total(100, discount=10)\n```\n"
    )
