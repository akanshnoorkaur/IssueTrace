from __future__ import annotations
"""
API Request and Response Schemas

These Pydantic models define the shape of data flowing in and out of the API.
FastAPI uses them for automatic validation, serialization, and documentation.
"""

from pydantic import BaseModel, Field, field_validator
import re


class AnalyzeRequest(BaseModel):
    """Request body for analysis endpoints.
    
    The user submits a GitHub URL — we validate it and extract the parts.
    """
    url: str = Field(
        ...,
        description="GitHub issue or pull request URL",
        examples=["https://github.com/owner/repo/issues/123"],
    )
    
    @field_validator("url")
    @classmethod
    def validate_github_url(cls, v: str) -> str:
        """Ensure the URL looks like a valid GitHub issue or PR URL."""
        pattern = r"^https?://github\.com/[\w\-\.]+/[\w\-\.]+/(issues|pull)/\d+/?$"
        if not re.match(pattern, v.strip()):
            raise ValueError(
                "Invalid GitHub URL. Expected format: "
                "https://github.com/owner/repo/issues/123 or "
                "https://github.com/owner/repo/pull/456"
            )
        return v.strip().rstrip("/")


class AnalyzeResponse(BaseModel):
    """Response after submitting an analysis request."""
    analysis_id: str
    status: str = "completed"
    message: str = "Analysis completed successfully"
    report: dict  # Full TriageReport as dict


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    ai_available: bool
    github_authenticated: bool
    version: str = "0.1.0"


class HistoryItem(BaseModel):
    """Summary of a past analysis for the history list."""
    id: str
    github_url: str
    repo_owner: str
    repo_name: str
    issue_number: int
    issue_type: str
    issue_title: str
    overall_assessment: str | None
    overall_confidence: float | None
    created_at: str


class HistoryResponse(BaseModel):
    """Response for the history endpoint."""
    analyses: list[HistoryItem]
    total: int


class StatsResponse(BaseModel):
    """Dashboard statistics."""
    total: int
    confirmed: int
    invalid: int
    cannot_reproduce: int


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: str | None = None


def parse_github_url(url: str) -> dict:
    """Parse a GitHub URL into its components.
    
    Args:
        url: A validated GitHub issue or PR URL
        
    Returns:
        Dict with owner, repo, number, and type
        
    Raises:
        ValueError: If URL cannot be parsed
        
    Examples:
        >>> parse_github_url("https://github.com/facebook/react/issues/123")
        {"owner": "facebook", "repo": "react", "number": 123, "type": "issue"}
    """
    url = url.strip().rstrip("/")
    pattern = r"https?://github\.com/([\w\-\.]+)/([\w\-\.]+)/(issues|pull)/(\d+)"
    match = re.match(pattern, url)
    if not match:
        raise ValueError(f"Cannot parse GitHub URL: {url}")
    
    owner, repo, url_type, number = match.groups()
    return {
        "owner": owner,
        "repo": repo,
        "number": int(number),
        "type": "issue" if url_type == "issues" else "pull_request",
    }
