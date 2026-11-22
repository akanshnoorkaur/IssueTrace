from __future__ import annotations
"""Tests for the claim extraction engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.engines.claim_extractor import ClaimExtractor
from app.services.ai_service import AIService
from app.models.claims import ClaimExtractionResult, TechnicalClaim, ClaimType


@pytest.fixture
def mock_ai_unavailable():
    """AI service that is not available."""
    ai = MagicMock(spec=AIService)
    ai.available = False
    return ai


@pytest.fixture
def mock_ai_available():
    """AI service that returns a mock extraction result."""
    ai = AsyncMock(spec=AIService)
    ai.available = True
    ai.generate_structured.return_value = ClaimExtractionResult(
        claims=[
            TechnicalClaim(
                claim_id=1,
                original_statement="calculate_total returns wrong value with negative discount",
                claim_type=ClaimType.BEHAVIOR,
                relevant_location="calculate_total",
                expected_behavior="Should raise an error or return 100",
                reported_behavior="Returns 110 instead",
                evidence_required=["Source code of calculate_total", "Parameter validation logic"],
            ),
            TechnicalClaim(
                claim_id=2,
                original_statement="Negative discount increases the total price",
                claim_type=ClaimType.BEHAVIOR,
                relevant_location="calculate_total",
                expected_behavior="Discount should not increase price",
                reported_behavior="Price increases with negative discount",
                evidence_required=["Discount calculation logic"],
            ),
        ],
        summary="Bug report about calculate_total function handling negative discounts incorrectly",
        ai_available=True,
    )
    return ai


@pytest.mark.asyncio
async def test_extraction_without_ai(mock_ai_unavailable):
    """When AI is unavailable, should return empty claims with warning."""
    extractor = ClaimExtractor(mock_ai_unavailable)
    result = await extractor.extract_claims("Some issue text")
    
    assert isinstance(result, ClaimExtractionResult)
    assert len(result.claims) == 0
    assert result.ai_available is False
    assert len(result.warnings) > 0
    assert "unavailable" in result.warnings[0].lower()


@pytest.mark.asyncio
async def test_extraction_with_ai(mock_ai_available):
    """When AI is available, should extract structured claims."""
    extractor = ClaimExtractor(mock_ai_available)
    result = await extractor.extract_claims("Bug: calculate_total fails with negative discount")
    
    assert isinstance(result, ClaimExtractionResult)
    assert len(result.claims) == 2
    assert result.claims[0].claim_id == 1
    assert result.claims[0].claim_type == ClaimType.BEHAVIOR
    assert "calculate_total" in result.claims[0].original_statement
    assert result.summary != ""


@pytest.mark.asyncio
async def test_extraction_validates_claims(mock_ai_available):
    """Extracted claims should have required fields."""
    extractor = ClaimExtractor(mock_ai_available)
    result = await extractor.extract_claims("Test")
    
    for claim in result.claims:
        assert claim.claim_id > 0
        assert len(claim.original_statement) > 0
        assert isinstance(claim.claim_type, ClaimType)


@pytest.mark.asyncio
async def test_extraction_handles_ai_error():
    """When AI raises an error, should return empty claims with warning."""
    from app.services.ai_service import AIServiceError
    
    ai = AsyncMock(spec=AIService)
    ai.available = True
    ai.generate_structured.side_effect = AIServiceError("API error")
    
    extractor = ClaimExtractor(ai)
    result = await extractor.extract_claims("Some text")
    
    assert len(result.claims) == 0
    assert len(result.warnings) > 0


@pytest.mark.asyncio
async def test_extraction_handles_none_response():
    """When AI returns None, should handle gracefully."""
    ai = AsyncMock(spec=AIService)
    ai.available = True
    ai.generate_structured.return_value = None
    
    extractor = ClaimExtractor(ai)
    result = await extractor.extract_claims("Some text")
    
    assert len(result.claims) == 0
    assert len(result.warnings) > 0
