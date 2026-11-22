from __future__ import annotations
"""
GitHub API Service

Handles all communication with the GitHub REST API.
Uses httpx for async HTTP requests, which pairs well with FastAPI.

Key design decisions:
- Uses httpx (not PyGithub) for native async support
- Optional authentication via GITHUB_TOKEN env var
- Rate-limit aware with proper error handling
- Read-only: never modifies repositories
"""

import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# Max size of file content we'll fetch (100 KB)
MAX_FILE_SIZE = 100_000


class GitHubServiceError(Exception):
    """Base exception for GitHub service errors."""
    pass


class GitHubRateLimitError(GitHubServiceError):
    """Raised when we hit GitHub API rate limits."""
    pass


class GitHubNotFoundError(GitHubServiceError):
    """Raised when a resource is not found (404)."""
    pass


class GitHubService:
    """Async GitHub API client.
    
    Usage:
        async with GitHubService(token="optional") as gh:
            issue = await gh.get_issue("facebook", "react", 123)
    """
    
    def __init__(self, token: str | None = None, base_url: str = "https://api.github.com"):
        self.base_url = base_url
        self._headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "IssueLens/0.1.0",
        }
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        
        self._client: httpx.AsyncClient | None = None
    
    async def __aenter__(self) -> "GitHubService":
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            headers=self._headers,
            timeout=30.0,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._client:
            await self._client.aclose()
    
    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            raise RuntimeError("GitHubService must be used as async context manager")
        return self._client
    
    async def _request(self, method: str, path: str, **kwargs) -> Any:
        """Make a GitHub API request with error handling."""
        response = await self.client.request(method, path, **kwargs)
        
        # Check rate limits
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None and int(remaining) < 5:
            logger.warning("GitHub API rate limit nearly exhausted: %s remaining", remaining)
        
        if response.status_code == 404:
            raise GitHubNotFoundError(f"Resource not found: {path}")
        
        if response.status_code == 403:
            if "rate limit" in response.text.lower():
                raise GitHubRateLimitError(
                    "GitHub API rate limit exceeded. Set GITHUB_TOKEN in .env for higher limits."
                )
            raise GitHubServiceError(f"Access denied: {path}")
        
        if response.status_code == 422:
            raise GitHubServiceError(f"Validation error from GitHub: {response.text}")
        
        response.raise_for_status()
        return response.json()
    
    async def get_issue(self, owner: str, repo: str, number: int) -> dict:
        """Fetch a GitHub issue by number.
        
        Returns the full issue object including title, body, labels, etc.
        """
        return await self._request("GET", f"/repos/{owner}/{repo}/issues/{number}")
    
    async def get_pull_request(self, owner: str, repo: str, number: int) -> dict:
        """Fetch a GitHub pull request by number."""
        return await self._request("GET", f"/repos/{owner}/{repo}/pulls/{number}")
    
    async def get_issue_comments(
        self, owner: str, repo: str, number: int, max_comments: int = 20
    ) -> list[dict]:
        """Fetch comments on an issue or PR.
        
        Limited to prevent fetching thousands of comments on popular issues.
        """
        return await self._request(
            "GET",
            f"/repos/{owner}/{repo}/issues/{number}/comments",
            params={"per_page": min(max_comments, 100)},
        )
    
    async def get_repo_info(self, owner: str, repo: str) -> dict:
        """Fetch repository metadata."""
        return await self._request("GET", f"/repos/{owner}/{repo}")
    
    async def get_file_content(self, owner: str, repo: str, path: str) -> dict | None:
        """Fetch a single file's content from the repository.
        
        Returns None if the file doesn't exist or is too large.
        Uses the GitHub Contents API which returns base64-encoded content.
        """
        try:
            result = await self._request(
                "GET", f"/repos/{owner}/{repo}/contents/{path}"
            )
            # Skip files that are too large
            if result.get("size", 0) > MAX_FILE_SIZE:
                logger.info("Skipping large file: %s (%d bytes)", path, result["size"])
                return None
            return result
        except GitHubNotFoundError:
            return None
    
    async def get_directory_contents(
        self, owner: str, repo: str, path: str = ""
    ) -> list[dict]:
        """List files in a repository directory."""
        try:
            result = await self._request(
                "GET", f"/repos/{owner}/{repo}/contents/{path}"
            )
            if isinstance(result, list):
                return result
            return [result]
        except GitHubNotFoundError:
            return []
    
    async def search_code(
        self, owner: str, repo: str, query: str, max_results: int = 10
    ) -> list[dict]:
        """Search for code in a repository.
        
        Uses GitHub's code search API. Note: this only works for
        indexed repositories and has additional rate limits.
        """
        try:
            result = await self._request(
                "GET",
                "/search/code",
                params={
                    "q": f"{query} repo:{owner}/{repo}",
                    "per_page": min(max_results, 30),
                },
            )
            return result.get("items", [])
        except GitHubServiceError as e:
            logger.warning("Code search failed: %s", e)
            return []
    
    async def get_readme(self, owner: str, repo: str) -> dict | None:
        """Fetch the repository README."""
        try:
            return await self._request("GET", f"/repos/{owner}/{repo}/readme")
        except GitHubNotFoundError:
            return None
    
    async def get_recent_commits(
        self, owner: str, repo: str, path: str | None = None, max_commits: int = 10
    ) -> list[dict]:
        """Fetch recent commits, optionally filtered by file path."""
        params: dict[str, Any] = {"per_page": min(max_commits, 30)}
        if path:
            params["path"] = path
        try:
            return await self._request(
                "GET", f"/repos/{owner}/{repo}/commits", params=params
            )
        except GitHubServiceError as e:
            logger.warning("Failed to fetch commits: %s", e)
            return []
    
    async def get_tree(
        self, owner: str, repo: str, sha: str = "HEAD", recursive: bool = True
    ) -> list[dict]:
        """Fetch the repository file tree.
        
        This gives us a full listing of all files, which is useful for
        finding test files, documentation, and relevant source code.
        """
        try:
            # First get the default branch's latest commit
            repo_info = await self.get_repo_info(owner, repo)
            default_branch = repo_info.get("default_branch", "main")
            
            # Get the tree
            params = {"recursive": "1"} if recursive else {}
            result = await self._request(
                "GET",
                f"/repos/{owner}/{repo}/git/trees/{default_branch}",
                params=params,
            )
            return result.get("tree", [])
        except GitHubServiceError as e:
            logger.warning("Failed to fetch tree: %s", e)
            return []
    
    async def get_pr_files(
        self, owner: str, repo: str, number: int
    ) -> list[dict]:
        """Fetch the list of files changed in a pull request."""
        try:
            return await self._request(
                "GET",
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": 100},
            )
        except GitHubServiceError as e:
            logger.warning("Failed to fetch PR files: %s", e)
            return []
