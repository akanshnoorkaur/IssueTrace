from __future__ import annotations
"""
GitHub Data Collector Engine

Orchestrates all GitHub data retrieval for a given issue or PR.
Collects the submission, comments, repository metadata, relevant files,
documentation, tests, and recent commits.

This is the first step in the analysis pipeline.
"""

import base64
import logging
from typing import Any

from app.services.github_service import GitHubService, GitHubNotFoundError

logger = logging.getLogger(__name__)

# File extensions we consider relevant source code
SOURCE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".rb", ".php", ".c", ".cpp", ".h", ".hpp", ".cs", ".swift",
    ".kt", ".scala", ".r", ".jl",
}

# Directories that commonly contain tests
TEST_DIRS = {"tests", "test", "__tests__", "spec", "specs", "testing"}

# Directories that commonly contain documentation
DOC_DIRS = {"docs", "doc", "documentation", "wiki"}

# Config file patterns
CONFIG_FILES = {
    "setup.py", "setup.cfg", "pyproject.toml", "package.json",
    "tsconfig.json", "Cargo.toml", "go.mod", "Makefile",
    "Dockerfile", "docker-compose.yml", ".github",
    "requirements.txt", "Pipfile", "tox.ini", "pytest.ini",
}


class GitHubCollector:
    """Collects all relevant data from a GitHub repository for analysis.
    
    Usage:
        async with GitHubService(token=token) as gh:
            collector = GitHubCollector(gh)
            data = await collector.collect_issue_data("facebook", "react", 123)
    """
    
    def __init__(self, github_service: GitHubService):
        self.gh = github_service
    
    async def collect_issue_data(
        self, owner: str, repo: str, number: int
    ) -> dict[str, Any]:
        """Collect all data for a GitHub issue.
        
        Returns a structured dict with:
        - issue: The issue itself (title, body, labels, etc.)
        - comments: Issue comments
        - repo_info: Repository metadata
        - file_tree: Full file listing
        - relevant_files: Source files related to the issue
        - readme: README content
        - test_files: Discovered test files
        """
        logger.info("Collecting data for %s/%s#%d", owner, repo, number)
        
        # Fetch the issue
        issue = await self.gh.get_issue(owner, repo, number)
        
        # Fetch supporting data
        comments = await self.gh.get_issue_comments(owner, repo, number)
        repo_info = await self.gh.get_repo_info(owner, repo)
        file_tree = await self.gh.get_tree(owner, repo)
        readme = await self.gh.get_readme(owner, repo)
        
        # Decode README content
        readme_content = ""
        if readme and readme.get("content"):
            try:
                readme_content = base64.b64decode(readme["content"]).decode("utf-8")
            except Exception:
                readme_content = ""
        
        # Identify relevant files from the issue text
        issue_text = f"{issue.get('title', '')} {issue.get('body', '')}"
        for comment in comments:
            issue_text += f" {comment.get('body', '')}"
        
        # Find files mentioned in the issue or related to mentioned identifiers
        relevant_paths = self._find_relevant_paths(issue_text, file_tree)
        
        # Fetch content of relevant files (up to a limit)
        relevant_files = await self._fetch_files(owner, repo, relevant_paths[:15])
        
        # Find test files
        test_paths = self._find_test_files(file_tree)
        test_files = await self._fetch_files(owner, repo, test_paths[:10])
        
        return {
            "issue": issue,
            "comments": comments,
            "repo_info": repo_info,
            "file_tree": [
                {"path": f["path"], "type": f["type"], "size": f.get("size", 0)}
                for f in file_tree
                if f.get("type") == "blob"
            ],
            "relevant_files": relevant_files,
            "readme": readme_content,
            "test_files": test_files,
        }
    
    async def collect_pr_data(
        self, owner: str, repo: str, number: int
    ) -> dict[str, Any]:
        """Collect all data for a GitHub pull request.
        
        Similar to issue data, but also includes PR-specific info
        like changed files, diff, and PR metadata.
        """
        logger.info("Collecting PR data for %s/%s#%d", owner, repo, number)
        
        # Fetch the PR
        pr = await self.gh.get_pull_request(owner, repo, number)
        
        # Fetch supporting data
        comments = await self.gh.get_issue_comments(owner, repo, number)
        repo_info = await self.gh.get_repo_info(owner, repo)
        pr_files = await self.gh.get_pr_files(owner, repo, number)
        readme = await self.gh.get_readme(owner, repo)
        
        # Decode README content
        readme_content = ""
        if readme and readme.get("content"):
            try:
                readme_content = base64.b64decode(readme["content"]).decode("utf-8")
            except Exception:
                readme_content = ""
        
        # Fetch the actual file contents for changed files
        changed_paths = [f["filename"] for f in pr_files if f.get("filename")]
        relevant_files = await self._fetch_files(owner, repo, changed_paths[:15])
        
        # Find test files
        file_tree = await self.gh.get_tree(owner, repo)
        test_paths = self._find_test_files(file_tree)
        test_files = await self._fetch_files(owner, repo, test_paths[:10])
        
        return {
            "pull_request": pr,
            "comments": comments,
            "repo_info": repo_info,
            "pr_files": pr_files,
            "relevant_files": relevant_files,
            "readme": readme_content,
            "test_files": test_files,
            "file_tree": [
                {"path": f["path"], "type": f["type"], "size": f.get("size", 0)}
                for f in file_tree
                if f.get("type") == "blob"
            ],
        }
    
    def _find_relevant_paths(
        self, text: str, file_tree: list[dict]
    ) -> list[str]:
        """Find file paths in the repo that are relevant to the issue text.
        
        Strategy:
        1. Look for file paths explicitly mentioned in the text
        2. Look for function/class names mentioned that match file names
        3. Look for config files that might be relevant
        """
        text_lower = text.lower()
        relevant = []
        
        all_paths = [
            f["path"] for f in file_tree
            if f.get("type") == "blob"
        ]
        
        for path in all_paths:
            path_lower = path.lower()
            
            # Direct mention of the file path
            if path_lower in text_lower or path.split("/")[-1].lower() in text_lower:
                relevant.append(path)
                continue
            
            # File name stem matches a word in the text
            stem = path.split("/")[-1].rsplit(".", 1)[0].lower()
            if len(stem) > 2 and stem in text_lower:
                # Check it's a source file
                ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
                if ext in SOURCE_EXTENSIONS:
                    relevant.append(path)
        
        # Also include any config files at the root
        for path in all_paths:
            name = path.split("/")[-1]
            if name in CONFIG_FILES and "/" not in path.rstrip(name).rstrip("/"):
                if path not in relevant:
                    relevant.append(path)
        
        return relevant
    
    def _find_test_files(self, file_tree: list[dict]) -> list[str]:
        """Find test files in the repository."""
        test_paths = []
        
        for f in file_tree:
            if f.get("type") != "blob":
                continue
            path = f["path"]
            path_lower = path.lower()
            
            # In a test directory
            parts = path.split("/")
            if any(part.lower() in TEST_DIRS for part in parts):
                ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""
                if ext in SOURCE_EXTENSIONS:
                    test_paths.append(path)
                    continue
            
            # Test file naming conventions
            name = parts[-1].lower()
            if name.startswith("test_") or name.endswith("_test.py") or name.endswith(".test.ts") or name.endswith(".test.js") or name.endswith(".spec.ts") or name.endswith(".spec.js"):
                test_paths.append(path)
        
        return test_paths
    
    async def _fetch_files(
        self, owner: str, repo: str, paths: list[str]
    ) -> list[dict[str, str]]:
        """Fetch the content of multiple files from the repository.
        
        Returns a list of {path, content} dicts.
        Skips files that don't exist or are too large.
        """
        files = []
        for path in paths:
            try:
                result = await self.gh.get_file_content(owner, repo, path)
                if result and result.get("content"):
                    try:
                        content = base64.b64decode(result["content"]).decode("utf-8")
                        files.append({"path": path, "content": content})
                    except Exception:
                        logger.debug("Could not decode file: %s", path)
            except Exception as e:
                logger.debug("Could not fetch file %s: %s", path, e)
        
        return files
