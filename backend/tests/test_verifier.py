from __future__ import annotations
"""Tests for the verification engine."""

import pytest
from app.engines.verifier import Verifier, VerificationResult
from app.models.claims import TechnicalClaim, ClaimType
from app.models.assessment import VerificationStatus


@pytest.fixture
def verifier():
    return Verifier()


@pytest.fixture
def claim_with_location():
    return TechnicalClaim(
        claim_id=1,
        original_statement="calculate_total returns wrong value",
        claim_type=ClaimType.BEHAVIOR,
        relevant_location="calculate_total",
    )


@pytest.fixture
def claim_without_location():
    return TechnicalClaim(
        claim_id=2,
        original_statement="The application crashes on startup",
        claim_type=ClaimType.BEHAVIOR,
    )


class TestVerifier:
    
    def test_verify_finds_function(
        self, verifier, claim_with_location, sample_source_files, sample_test_files
    ):
        """Should verify that a referenced function exists."""
        results = verifier.verify_claims(
            claims=[claim_with_location],
            source_files=sample_source_files,
            test_files=sample_test_files,
        )
        
        location_checks = [
            r for r in results if r.check_type == "location_exists"
        ]
        assert len(location_checks) > 0
        assert location_checks[0].status == VerificationStatus.VERIFIED
    
    def test_verify_function_signature(
        self, verifier, claim_with_location, sample_source_files, sample_test_files
    ):
        """Should extract function signature via AST."""
        results = verifier.verify_claims(
            claims=[claim_with_location],
            source_files=sample_source_files,
            test_files=sample_test_files,
        )
        
        sig_checks = [
            r for r in results if r.check_type == "function_signature"
        ]
        assert len(sig_checks) > 0
        assert "calculate_total" in sig_checks[0].details
    
    def test_verify_test_coverage(
        self, verifier, claim_with_location, sample_source_files, sample_test_files
    ):
        """Should check for related tests."""
        results = verifier.verify_claims(
            claims=[claim_with_location],
            source_files=sample_source_files,
            test_files=sample_test_files,
        )
        
        test_checks = [
            r for r in results if r.check_type == "test_coverage"
        ]
        assert len(test_checks) > 0
    
    def test_verify_missing_location(
        self, verifier, sample_source_files, sample_test_files
    ):
        """Should report when a referenced location doesn't exist."""
        claim = TechnicalClaim(
            claim_id=3,
            original_statement="nonexistent_function fails",
            claim_type=ClaimType.BEHAVIOR,
            relevant_location="nonexistent_function",
        )
        
        results = verifier.verify_claims(
            claims=[claim],
            source_files=sample_source_files,
            test_files=sample_test_files,
        )
        
        location_checks = [
            r for r in results if r.check_type == "location_exists"
        ]
        assert len(location_checks) > 0
        assert location_checks[0].status == VerificationStatus.NOT_VERIFIED
    
    def test_verify_no_files(self, verifier, claim_with_location):
        """Should handle empty file lists."""
        results = verifier.verify_claims(
            claims=[claim_with_location],
            source_files=[],
            test_files=[],
        )
        
        assert len(results) > 0  # Should still produce results (not verified)
    
    def test_verify_claim_without_location(
        self, verifier, claim_without_location, sample_source_files, sample_test_files
    ):
        """Should handle claims without a specific location."""
        results = verifier.verify_claims(
            claims=[claim_without_location],
            source_files=sample_source_files,
            test_files=sample_test_files,
        )
        
        # Should have test coverage check but no location check
        location_checks = [
            r for r in results if r.check_type == "location_exists"
        ]
        assert len(location_checks) == 0
    
    def test_result_to_dict(self):
        """VerificationResult should serialize to dict."""
        result = VerificationResult(
            claim_id=1,
            check_type="test_check",
            status=VerificationStatus.VERIFIED,
            details="Test passed",
            file_path="test.py",
            line_number=10,
        )
        d = result.to_dict()
        assert d["claim_id"] == 1
        assert d["status"] == "VERIFIED"
        assert d["file_path"] == "test.py"
