from __future__ import annotations
"""
Technical Claim Models

Represents individual technical claims extracted from GitHub issues and PRs.
These models validate the structure returned by the AI claim extraction engine.
"""

from enum import Enum
from pydantic import BaseModel, Field


class ClaimType(str, Enum):
    """Categories of technical claims found in issues/PRs."""
    BEHAVIOR = "behavior"
    REGRESSION = "regression"
    FUNCTIONALITY = "functionality"
    PERFORMANCE = "performance"
    SECURITY = "security"
    COMPATIBILITY = "compatibility"
    OTHER = "other"


class TechnicalClaim(BaseModel):
    """A single technical claim extracted from an issue or PR.
    
    Each claim represents one verifiable assertion the submitter is making
    about the codebase, its behavior, or a problem they encountered.
    """
    claim_id: int = Field(
        ..., description="Unique sequential ID for this claim"
    )
    original_statement: str = Field(
        ..., description="The exact or closely paraphrased statement from the submission"
    )
    claim_type: ClaimType = Field(
        ..., description="Category of this claim"
    )
    relevant_location: str | None = Field(
        None,
        description="Relevant function, class, file, or module if identifiable",
    )
    expected_behavior: str | None = Field(
        None, description="What the submitter expects should happen"
    )
    reported_behavior: str | None = Field(
        None, description="What the submitter says actually happens"
    )
    evidence_required: list[str] = Field(
        default_factory=list,
        description="Types of evidence needed to verify this claim",
    )


class ClaimExtractionResult(BaseModel):
    """Result of the claim extraction engine.
    
    Contains all claims extracted plus metadata about the extraction process.
    """
    claims: list[TechnicalClaim] = Field(default_factory=list)
    summary: str = Field(
        default="", description="Brief summary of what the submission is about"
    )
    ai_available: bool = Field(
        default=True,
        description="Whether AI was available for extraction",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Any warnings about the extraction process",
    )
