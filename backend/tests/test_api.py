from __future__ import annotations
"""Tests for the FastAPI API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock

from app.main import app
from app.config import reset_settings


@pytest.fixture(autouse=True)
def reset():
    """Reset settings before each test."""
    reset_settings()


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestHealthEndpoint:
    
    def test_health_returns_200(self, client):
        response = client.get("/api/health")
        assert response.status_code == 200
    
    def test_health_response_structure(self, client):
        response = client.get("/api/health")
        data = response.json()
        assert "status" in data
        assert "ai_available" in data
        assert "github_authenticated" in data
        assert data["status"] == "healthy"
    
    def test_health_reports_ai_unavailable(self, client):
        """AI should be reported as unavailable without API key."""
        response = client.get("/api/health")
        data = response.json()
        assert data["ai_available"] is False


class TestRootEndpoint:
    
    def test_root_returns_200(self, client):
        response = client.get("/")
        assert response.status_code == 200
    
    def test_root_contains_app_info(self, client):
        response = client.get("/")
        data = response.json()
        assert data["app"] == "IssueLens"
        assert "version" in data


class TestAnalyzeEndpoint:
    
    def test_invalid_url_returns_422(self, client):
        """Invalid URL should be rejected."""
        response = client.post(
            "/api/analyze/issue",
            json={"url": "not-a-url"},
        )
        assert response.status_code == 422
    
    def test_non_github_url_returns_422(self, client):
        """Non-GitHub URLs should be rejected."""
        response = client.post(
            "/api/analyze/issue",
            json={"url": "https://gitlab.com/owner/repo/issues/1"},
        )
        assert response.status_code == 422
    
    def test_pr_url_on_issue_endpoint_returns_400(self, client):
        """PR URL on issue endpoint should return 400."""
        # We need to mock the full pipeline to get past URL parsing
        response = client.post(
            "/api/analyze/issue",
            json={"url": "https://github.com/owner/repo/pull/1"},
        )
        assert response.status_code == 400
    
    def test_issue_url_on_pr_endpoint_returns_400(self, client):
        """Issue URL on PR endpoint should return 400."""
        response = client.post(
            "/api/analyze/pull-request",
            json={"url": "https://github.com/owner/repo/issues/1"},
        )
        assert response.status_code == 400


class TestHistoryEndpoint:
    
    def test_history_returns_200(self, client):
        response = client.get("/api/history")
        assert response.status_code == 200
    
    def test_history_response_structure(self, client):
        response = client.get("/api/history")
        data = response.json()
        assert "analyses" in data
        assert "total" in data
        assert isinstance(data["analyses"], list)


class TestStatsEndpoint:
    
    def test_stats_returns_200(self, client):
        response = client.get("/api/stats")
        assert response.status_code == 200
    
    def test_stats_response_structure(self, client):
        response = client.get("/api/stats")
        data = response.json()
        assert "total" in data
        assert "confirmed" in data
        assert "invalid" in data
        assert "cannot_reproduce" in data
