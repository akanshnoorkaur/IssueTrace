from __future__ import annotations
"""
Report Models

The final triage report that combines all pipeline outputs.
This is what gets stored in the database and shown to the user.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field

from .claims import TechnicalClaim
from .evidence import ClaimEvidence
from .assessment import ClaimAssessment, AssessmentLabel


class SubmissionOverview(BaseModel):
    """Summary of the GitHub submission being analyzed."""
    github_url: str
    repo_owner: str
    repo_name: str
    issue_number: int
    issue_type: str  # "issue" or "pull_request"
    title: str
    body_preview: str = Field(
        default="", description="First ~500 chars of the body"
    )
    labels: list[str] = Field(default_factory=list)
    author: str = ""
    created_at: str = ""
    comments_count: int = 0


class ClaimReport(BaseModel):
    """Full report for a single claim: the claim itself, evidence, and assessment."""
    claim: TechnicalClaim
    evidence: list[dict] = Field(
        default_factory=list, description="Evidence items for this claim"
    )
    assessment: ClaimAssessment | None = None


class TriageReport(BaseModel):
    """The complete triage report for a GitHub issue or PR.
    
    This is the primary output of the entire analysis pipeline.
    """
    analysis_id: str
    submission: SubmissionOverview
    claims: list[ClaimReport] = Field(default_factory=list)
    overall_assessment: AssessmentLabel | None = None
    overall_confidence: float | None = None
    overall_reasoning: str = ""
    recommendations: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    
    @property
    def claim_count(self) -> int:
        return len(self.claims)
    
    @property
    def confirmed_count(self) -> int:
        return sum(
            1 for c in self.claims
            if c.assessment and c.assessment.assessment == AssessmentLabel.CONFIRMED
        )
    
    @property
    def invalid_count(self) -> int:
        return sum(
            1 for c in self.claims
            if c.assessment and c.assessment.assessment == AssessmentLabel.INVALID
        )
    
    @property
    def cannot_reproduce_count(self) -> int:
        return sum(
            1 for c in self.claims
            if c.assessment and c.assessment.assessment == AssessmentLabel.CANNOT_REPRODUCE
        )
