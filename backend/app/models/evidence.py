from __future__ import annotations
"""
Evidence Models

Represents pieces of evidence retrieved from the repository to verify claims.
Every evidence item cites a real file path and snippet from the actual repo.
"""

from enum import Enum
from pydantic import BaseModel, Field


class EvidenceCategory(str, Enum):
    """Types of evidence that can be found in a repository."""
    SOURCE_CODE = "source_code"
    TEST = "test"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"
    COMMIT_HISTORY = "commit_history"
    ISSUE_COMMENT = "issue_comment"


class EvidenceItem(BaseModel):
    """A single piece of evidence from the repository.
    
    Every field here comes from actual repository data —
    nothing is fabricated by the AI.
    """
    file_path: str = Field(
        ..., description="Path to the file in the repository"
    )
    line_start: int | None = Field(
        None, description="Starting line number (1-based)"
    )
    line_end: int | None = Field(
        None, description="Ending line number (1-based)"
    )
    snippet: str = Field(
        ..., description="The relevant code or text snippet"
    )
    category: EvidenceCategory = Field(
        ..., description="What type of evidence this is"
    )
    relevance_explanation: str = Field(
        default="",
        description="Why this evidence is relevant to the claim",
    )
    relevance_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="How relevant this evidence is (0-1)",
    )


class ClaimEvidence(BaseModel):
    """Evidence collected for a specific claim."""
    claim_id: int = Field(
        ..., description="ID of the claim this evidence relates to"
    )
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    search_queries_used: list[str] = Field(
        default_factory=list,
        description="What was searched for to find this evidence",
    )


class EvidenceRetrievalResult(BaseModel):
    """Result of the evidence retrieval engine."""
    claim_evidence: list[ClaimEvidence] = Field(default_factory=list)
    total_files_searched: int = 0
    total_evidence_items: int = 0
    warnings: list[str] = Field(default_factory=list)
