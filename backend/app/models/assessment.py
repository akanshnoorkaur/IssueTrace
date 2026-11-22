from __future__ import annotations
"""
Assessment Models

Represents the AI's evaluation of each claim against the retrieved evidence.
The three primary assessment labels are CONFIRMED, INVALID, and CANNOT_REPRODUCE.
"""

from enum import Enum
from pydantic import BaseModel, Field


class AssessmentLabel(str, Enum):
    """The three primary triage assessment labels."""
    CONFIRMED = "CONFIRMED"
    INVALID = "INVALID"
    CANNOT_REPRODUCE = "CANNOT_REPRODUCE"


class VerificationStatus(str, Enum):
    """Status of automated verification attempts."""
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    PARTIALLY_VERIFIED = "PARTIALLY_VERIFIED"
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    ERROR = "ERROR"


class EvidenceReference(BaseModel):
    """A reference to a specific piece of evidence used in reasoning."""
    file_path: str
    line_start: int | None = None
    line_end: int | None = None
    description: str = ""


class ClaimAssessment(BaseModel):
    """AI assessment of a single technical claim.
    
    The model evaluates each claim against available evidence and produces
    a structured assessment with supporting reasoning.
    """
    claim_id: int = Field(
        ..., description="ID of the claim being assessed"
    )
    assessment: AssessmentLabel = Field(
        ..., description="Primary assessment label"
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Model's confidence estimate (NOT a calibrated probability)",
    )
    reasoning: str = Field(
        ..., description="Explanation of how this conclusion was reached"
    )
    supporting_evidence: list[EvidenceReference] = Field(
        default_factory=list,
        description="Evidence that supports the claim",
    )
    contradicting_evidence: list[EvidenceReference] = Field(
        default_factory=list,
        description="Evidence that contradicts the claim",
    )
    missing_evidence: list[str] = Field(
        default_factory=list,
        description="Evidence that would be needed but was not found",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.NOT_ATTEMPTED,
        description="Whether automated verification was attempted and its result",
    )
    limitations: list[str] = Field(
        default_factory=list,
        description="Limitations of this assessment",
    )
    recommendation: str = Field(
        default="",
        description="Suggested action for the maintainer",
    )


class AssessmentResult(BaseModel):
    """Result of the AI reasoning engine."""
    assessments: list[ClaimAssessment] = Field(default_factory=list)
    ai_available: bool = True
    model_used: str | None = None
    warnings: list[str] = Field(default_factory=list)
