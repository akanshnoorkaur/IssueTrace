from __future__ import annotations
"""Tests for the report generator engine."""

import pytest
from app.engines.report_generator import ReportGenerator
from app.models.claims import ClaimExtractionResult, TechnicalClaim, ClaimType
from app.models.evidence import EvidenceRetrievalResult, ClaimEvidence, EvidenceItem, EvidenceCategory
from app.models.assessment import (
    AssessmentResult, ClaimAssessment, AssessmentLabel, VerificationStatus,
)
from app.models.report import TriageReport


@pytest.fixture
def generator():
    return ReportGenerator()


@pytest.fixture
def claim_result():
    return ClaimExtractionResult(
        claims=[
            TechnicalClaim(
                claim_id=1,
                original_statement="calculate_total fails with negative discount",
                claim_type=ClaimType.BEHAVIOR,
                relevant_location="calculate_total",
            ),
        ],
        summary="Bug report about pricing function",
    )


@pytest.fixture
def evidence_result():
    return EvidenceRetrievalResult(
        claim_evidence=[
            ClaimEvidence(
                claim_id=1,
                evidence_items=[
                    EvidenceItem(
                        file_path="src/pricing.py",
                        line_start=4,
                        line_end=10,
                        snippet="def calculate_total(price, discount=0):\n    return price * (1 - discount/100)",
                        category=EvidenceCategory.SOURCE_CODE,
                        relevance_explanation="Function definition",
                        relevance_score=0.9,
                    ),
                ],
            ),
        ],
        total_files_searched=5,
        total_evidence_items=1,
    )


@pytest.fixture
def assessment_result():
    return AssessmentResult(
        assessments=[
            ClaimAssessment(
                claim_id=1,
                assessment=AssessmentLabel.CONFIRMED,
                confidence=0.85,
                reasoning="The calculate_total function does not validate negative discounts.",
                recommendation="Add input validation for the discount parameter.",
                limitations=["Static analysis only"],
            ),
        ],
        ai_available=True,
        model_used="gemini-3.8-flash",
    )


@pytest.fixture
def submission_data():
    return {
        "title": "Bug: calculate_total returns wrong value",
        "body": "The calculate_total function...",
        "user": {"login": "testuser"},
        "labels": [{"name": "bug"}],
        "created_at": "2024-01-15T10:00:00Z",
        "comments": 2,
    }


class TestReportGenerator:
    
    def test_generate_report(
        self, generator, claim_result, evidence_result,
        assessment_result, submission_data,
    ):
        """Should generate a complete report."""
        report = generator.generate(
            analysis_id="test-123",
            github_url="https://github.com/owner/repo/issues/42",
            owner="owner",
            repo="repo",
            number=42,
            submission_type="issue",
            submission_data=submission_data,
            claim_result=claim_result,
            evidence_result=evidence_result,
            assessment_result=assessment_result,
            verification_results=[],
        )
        
        assert isinstance(report, TriageReport)
        assert report.analysis_id == "test-123"
        assert report.submission.repo_owner == "owner"
        assert report.submission.repo_name == "repo"
        assert report.submission.issue_number == 42
        assert report.submission.title == "Bug: calculate_total returns wrong value"
    
    def test_report_includes_claims(
        self, generator, claim_result, evidence_result,
        assessment_result, submission_data,
    ):
        """Report should include all claims with evidence and assessments."""
        report = generator.generate(
            analysis_id="test-123",
            github_url="https://github.com/owner/repo/issues/42",
            owner="owner", repo="repo", number=42,
            submission_type="issue",
            submission_data=submission_data,
            claim_result=claim_result,
            evidence_result=evidence_result,
            assessment_result=assessment_result,
            verification_results=[],
        )
        
        assert len(report.claims) == 1
        assert report.claims[0].claim.claim_id == 1
        assert len(report.claims[0].evidence) > 0
        assert report.claims[0].assessment is not None
        assert report.claims[0].assessment.assessment == AssessmentLabel.CONFIRMED
    
    def test_report_overall_assessment(
        self, generator, claim_result, evidence_result,
        assessment_result, submission_data,
    ):
        """Report should compute overall assessment."""
        report = generator.generate(
            analysis_id="test-123",
            github_url="https://github.com/owner/repo/issues/42",
            owner="owner", repo="repo", number=42,
            submission_type="issue",
            submission_data=submission_data,
            claim_result=claim_result,
            evidence_result=evidence_result,
            assessment_result=assessment_result,
            verification_results=[],
        )
        
        assert report.overall_assessment == AssessmentLabel.CONFIRMED
        assert report.overall_confidence is not None
        assert 0.0 <= report.overall_confidence <= 1.0
    
    def test_report_includes_recommendations(
        self, generator, claim_result, evidence_result,
        assessment_result, submission_data,
    ):
        """Report should include recommendations."""
        report = generator.generate(
            analysis_id="test-123",
            github_url="https://github.com/owner/repo/issues/42",
            owner="owner", repo="repo", number=42,
            submission_type="issue",
            submission_data=submission_data,
            claim_result=claim_result,
            evidence_result=evidence_result,
            assessment_result=assessment_result,
            verification_results=[],
        )
        
        assert len(report.recommendations) > 0
    
    def test_report_includes_limitations(
        self, generator, claim_result, evidence_result,
        assessment_result, submission_data,
    ):
        """Report should always include limitations."""
        report = generator.generate(
            analysis_id="test-123",
            github_url="https://github.com/owner/repo/issues/42",
            owner="owner", repo="repo", number=42,
            submission_type="issue",
            submission_data=submission_data,
            claim_result=claim_result,
            evidence_result=evidence_result,
            assessment_result=assessment_result,
            verification_results=[],
        )
        
        assert len(report.limitations) > 0
    
    def test_report_serializes_to_dict(
        self, generator, claim_result, evidence_result,
        assessment_result, submission_data,
    ):
        """Report should serialize to dict for JSON response."""
        report = generator.generate(
            analysis_id="test-123",
            github_url="https://github.com/owner/repo/issues/42",
            owner="owner", repo="repo", number=42,
            submission_type="issue",
            submission_data=submission_data,
            claim_result=claim_result,
            evidence_result=evidence_result,
            assessment_result=assessment_result,
            verification_results=[],
        )
        
        report_dict = report.model_dump()
        assert isinstance(report_dict, dict)
        assert "analysis_id" in report_dict
        assert "submission" in report_dict
        assert "claims" in report_dict
    
    def test_report_with_no_claims(
        self, generator, evidence_result, assessment_result, submission_data,
    ):
        """Should handle empty claims list."""
        empty_claims = ClaimExtractionResult(claims=[], summary="No claims")
        empty_evidence = EvidenceRetrievalResult()
        empty_assessment = AssessmentResult()
        
        report = generator.generate(
            analysis_id="test-456",
            github_url="https://github.com/owner/repo/issues/1",
            owner="owner", repo="repo", number=1,
            submission_type="issue",
            submission_data=submission_data,
            claim_result=empty_claims,
            evidence_result=empty_evidence,
            assessment_result=empty_assessment,
            verification_results=[],
        )
        
        assert len(report.claims) == 0
        assert report.overall_assessment is None
