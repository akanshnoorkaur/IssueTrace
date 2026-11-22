from __future__ import annotations
"""
IssueLens API Routes

REST API endpoints for the IssueLens application.
All analysis happens on the backend — the frontend only sends URLs
and receives structured reports.
"""

import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.models.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorResponse,
    HealthResponse,
    HistoryItem,
    HistoryResponse,
    StatsResponse,
    parse_github_url,
)
from app.services.github_service import (
    GitHubService,
    GitHubNotFoundError,
    GitHubRateLimitError,
    GitHubServiceError,
)
from app.services.ai_service import AIService, AIServiceError
from app.services.database_service import DatabaseService
from app.engines.github_collector import GitHubCollector
from app.engines.claim_extractor import ClaimExtractor
from app.engines.evidence_retriever import EvidenceRetriever
from app.engines.ai_reasoner import AIReasoner
from app.engines.verifier import Verifier
from app.engines.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Check application health and service availability."""
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        ai_available=settings.is_ai_available,
        github_authenticated=settings.is_github_authenticated,
    )


@router.get("/stats", response_model=StatsResponse)
async def get_dashboard_stats():
    """Get dashboard statistics."""
    db = DatabaseService()
    stats = await db.get_dashboard_stats()
    return StatsResponse(**stats)


@router.post("/analyze/issue", response_model=AnalyzeResponse)
async def analyze_issue(request: AnalyzeRequest):
    """Analyze a GitHub issue.
    
    This is the main analysis endpoint. It runs the full pipeline:
    1. Parse the GitHub URL
    2. Collect issue data from GitHub
    3. Extract technical claims (via AI)
    4. Retrieve evidence from the repository
    5. Assess claims against evidence (via AI)
    6. Run static verification checks
    7. Generate a structured triage report
    """
    settings = get_settings()
    
    # Parse the URL
    try:
        parsed = parse_github_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if parsed["type"] != "issue":
        raise HTTPException(
            status_code=400,
            detail="Expected an issue URL. For pull requests, use /api/analyze/pull-request"
        )
    
    return await _run_analysis(parsed, settings, submission_type="issue")


@router.post("/analyze/pull-request", response_model=AnalyzeResponse)
async def analyze_pull_request(request: AnalyzeRequest):
    """Analyze a GitHub pull request."""
    settings = get_settings()
    
    try:
        parsed = parse_github_url(request.url)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    if parsed["type"] != "pull_request":
        raise HTTPException(
            status_code=400,
            detail="Expected a pull request URL. For issues, use /api/analyze/issue"
        )
    
    return await _run_analysis(parsed, settings, submission_type="pull_request")


async def _run_analysis(
    parsed: dict, settings, submission_type: str
) -> AnalyzeResponse:
    """Run the full analysis pipeline.
    
    This is the core orchestration function that ties all engines together.
    """
    analysis_id = str(uuid.uuid4())
    owner = parsed["owner"]
    repo = parsed["repo"]
    number = parsed["number"]
    
    logger.info(
        "Starting analysis %s for %s/%s#%d (%s)",
        analysis_id, owner, repo, number, submission_type,
    )
    
    # Initialize services
    ai_service = AIService(
        api_key=settings.gemini_api_key,
        model=settings.gemini_model,
    )
    db_service = DatabaseService()
    
    # Step 1: Collect GitHub data
    try:
        async with GitHubService(
            token=settings.github_token,
            base_url=settings.github_api_base,
        ) as gh:
            collector = GitHubCollector(gh)
            
            if submission_type == "issue":
                github_data = await collector.collect_issue_data(owner, repo, number)
            else:
                github_data = await collector.collect_pr_data(owner, repo, number)
                
    except GitHubNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"GitHub {submission_type} not found: {owner}/{repo}#{number}",
        )
    except GitHubRateLimitError:
        raise HTTPException(
            status_code=429,
            detail="GitHub API rate limit exceeded. Configure GITHUB_TOKEN for higher limits.",
        )
    except GitHubServiceError as e:
        raise HTTPException(status_code=502, detail=f"GitHub API error: {e}")
    
    # Step 2: Extract technical claims
    claim_extractor = ClaimExtractor(ai_service)
    submission_text = _extract_submission_text(github_data, submission_type)
    claim_result = await claim_extractor.extract_claims(submission_text)
    
    # Step 3: Retrieve evidence
    evidence_retriever = EvidenceRetriever()
    evidence_result = evidence_retriever.retrieve_evidence(
        claims=claim_result.claims,
        relevant_files=github_data.get("relevant_files", []),
        test_files=github_data.get("test_files", []),
        readme=github_data.get("readme", ""),
        file_tree=github_data.get("file_tree", []),
    )
    
    # Step 4: AI reasoning — assess claims against evidence
    ai_reasoner = AIReasoner(ai_service)
    assessment_result = await ai_reasoner.assess_claims(
        claims=claim_result.claims,
        evidence=evidence_result,
        repo_context={
            "owner": owner,
            "repo": repo,
            "readme_preview": github_data.get("readme", "")[:1000],
        },
    )
    
    # Step 5: Static verification
    verifier = Verifier()
    verification_results = verifier.verify_claims(
        claims=claim_result.claims,
        source_files=github_data.get("relevant_files", []),
        test_files=github_data.get("test_files", []),
    )
    
    # Step 6: Generate report
    report_generator = ReportGenerator()
    submission_data = github_data.get("issue") or github_data.get("pull_request", {})
    report = report_generator.generate(
        analysis_id=analysis_id,
        github_url=f"https://github.com/{owner}/{repo}/{('issues' if submission_type == 'issue' else 'pull')}/{number}",
        owner=owner,
        repo=repo,
        number=number,
        submission_type=submission_type,
        submission_data=submission_data,
        claim_result=claim_result,
        evidence_result=evidence_result,
        assessment_result=assessment_result,
        verification_results=verification_results,
    )
    
    # Step 7: Save to database
    report_dict = report.model_dump()
    await db_service.save(analysis_id, {
        "github_url": report.submission.github_url,
        "repo_owner": owner,
        "repo_name": repo,
        "issue_number": number,
        "issue_type": submission_type,
        "issue_title": report.submission.title,
        "overall_assessment": report.overall_assessment.value if report.overall_assessment else None,
        "overall_confidence": report.overall_confidence,
        "report": report_dict,
        "created_at": report.created_at,
    })
    
    logger.info("Analysis %s completed successfully", analysis_id)
    
    return AnalyzeResponse(
        analysis_id=analysis_id,
        status="completed",
        message="Analysis completed successfully",
        report=report_dict,
    )


@router.get("/analysis/{analysis_id}")
async def get_analysis(analysis_id: str):
    """Retrieve a previously completed analysis by ID."""
    db_service = DatabaseService()
    result = await db_service.get(analysis_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@router.get("/history", response_model=HistoryResponse)
async def get_history(limit: int = 50, offset: int = 0):
    """Get analysis history for the history page."""
    db_service = DatabaseService()
    analyses = await db_service.list_history(limit=limit, offset=offset)
    
    items = []
    for a in analyses:
        items.append(HistoryItem(
            id=a["id"],
            github_url=a["github_url"],
            repo_owner=a["repo_owner"],
            repo_name=a["repo_name"],
            issue_number=a["issue_number"],
            issue_type=a["issue_type"],
            issue_title=a.get("issue_title", ""),
            overall_assessment=a.get("overall_assessment"),
            overall_confidence=a.get("overall_confidence"),
            created_at=a["created_at"],
        ))
    
    return HistoryResponse(analyses=items, total=len(items))


def _extract_submission_text(github_data: dict, submission_type: str) -> str:
    """Extract the main text content from the GitHub submission for claim extraction."""
    if submission_type == "issue":
        issue = github_data.get("issue", {})
        parts = [
            f"Title: {issue.get('title', '')}",
            f"Body: {issue.get('body', '')}",
        ]
    else:
        pr = github_data.get("pull_request", {})
        parts = [
            f"Title: {pr.get('title', '')}",
            f"Body: {pr.get('body', '')}",
        ]
    
    # Include first few comments for context
    for comment in github_data.get("comments", [])[:5]:
        parts.append(f"Comment by {comment.get('user', {}).get('login', 'unknown')}: {comment.get('body', '')}")
    
    return "\n\n".join(parts)
