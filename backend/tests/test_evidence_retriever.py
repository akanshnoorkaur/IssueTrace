from __future__ import annotations
"""Tests for the evidence retrieval engine."""

import pytest
from app.engines.evidence_retriever import EvidenceRetriever
from app.models.claims import TechnicalClaim, ClaimType
from app.models.evidence import EvidenceCategory


@pytest.fixture
def retriever():
    return EvidenceRetriever()


@pytest.fixture
def sample_claim():
    return TechnicalClaim(
        claim_id=1,
        original_statement="calculate_total returns wrong value with negative discount",
        claim_type=ClaimType.BEHAVIOR,
        relevant_location="calculate_total",
        expected_behavior="Should raise an error",
        reported_behavior="Returns 110",
        evidence_required=["Source code of calculate_total"],
    )


class TestEvidenceRetriever:
    
    def test_retrieve_finds_source_evidence(
        self, retriever, sample_claim, sample_source_files, sample_test_files,
        sample_readme, sample_file_tree,
    ):
        """Should find evidence in source files."""
        result = retriever.retrieve_evidence(
            claims=[sample_claim],
            relevant_files=sample_source_files,
            test_files=sample_test_files,
            readme=sample_readme,
            file_tree=sample_file_tree,
        )
        
        assert len(result.claim_evidence) == 1
        evidence = result.claim_evidence[0]
        assert evidence.claim_id == 1
        assert len(evidence.evidence_items) > 0
    
    def test_retrieve_finds_function_via_ast(
        self, retriever, sample_claim, sample_source_files, sample_test_files,
        sample_readme, sample_file_tree,
    ):
        """Should find function definitions via AST analysis."""
        result = retriever.retrieve_evidence(
            claims=[sample_claim],
            relevant_files=sample_source_files,
            test_files=sample_test_files,
            readme=sample_readme,
            file_tree=sample_file_tree,
        )
        
        evidence = result.claim_evidence[0]
        ast_evidence = [
            e for e in evidence.evidence_items
            if "AST" in e.relevance_explanation
        ]
        assert len(ast_evidence) > 0
        assert ast_evidence[0].file_path == "src/pricing.py"
    
    def test_retrieve_includes_test_evidence(
        self, retriever, sample_claim, sample_source_files, sample_test_files,
        sample_readme, sample_file_tree,
    ):
        """Should find related tests."""
        result = retriever.retrieve_evidence(
            claims=[sample_claim],
            relevant_files=sample_source_files,
            test_files=sample_test_files,
            readme=sample_readme,
            file_tree=sample_file_tree,
        )
        
        evidence = result.claim_evidence[0]
        test_evidence = [
            e for e in evidence.evidence_items
            if e.category == EvidenceCategory.TEST
        ]
        assert len(test_evidence) > 0
    
    def test_retrieve_with_no_claims(
        self, retriever, sample_source_files, sample_test_files,
        sample_readme, sample_file_tree,
    ):
        """Should handle empty claims list."""
        result = retriever.retrieve_evidence(
            claims=[],
            relevant_files=sample_source_files,
            test_files=sample_test_files,
            readme=sample_readme,
            file_tree=sample_file_tree,
        )
        
        assert len(result.claim_evidence) == 0
        assert result.total_evidence_items == 0
    
    def test_retrieve_with_no_files(self, retriever, sample_claim):
        """Should handle empty file lists gracefully."""
        result = retriever.retrieve_evidence(
            claims=[sample_claim],
            relevant_files=[],
            test_files=[],
            readme="",
            file_tree=[],
        )
        
        assert len(result.claim_evidence) == 1
        # May have zero evidence items — that's correct behavior
    
    def test_evidence_items_have_required_fields(
        self, retriever, sample_claim, sample_source_files, sample_test_files,
        sample_readme, sample_file_tree,
    ):
        """All evidence items should have required fields."""
        result = retriever.retrieve_evidence(
            claims=[sample_claim],
            relevant_files=sample_source_files,
            test_files=sample_test_files,
            readme=sample_readme,
            file_tree=sample_file_tree,
        )
        
        for ce in result.claim_evidence:
            for item in ce.evidence_items:
                assert item.file_path  # Non-empty
                assert item.snippet  # Non-empty
                assert isinstance(item.category, EvidenceCategory)
                assert 0.0 <= item.relevance_score <= 1.0


class TestSearchTermExtraction:
    
    def test_extracts_identifiers(self, retriever):
        claim = TechnicalClaim(
            claim_id=1,
            original_statement="The calculate_total function fails",
            claim_type=ClaimType.BEHAVIOR,
            relevant_location="calculate_total",
        )
        terms = retriever._extract_search_terms(claim)
        assert "calculate_total" in terms
    
    def test_filters_common_words(self, retriever):
        claim = TechnicalClaim(
            claim_id=1,
            original_statement="The function is not working as expected",
            claim_type=ClaimType.BEHAVIOR,
        )
        terms = retriever._extract_search_terms(claim)
        assert "the" not in [t.lower() for t in terms]
        assert "not" not in [t.lower() for t in terms]


class TestPythonAstAnalysis:
    
    def test_finds_function_definition(self, retriever):
        content = (
            "def my_function(x, y):\n"
            "    return x + y\n"
        )
        evidence = retriever._analyze_python_ast(
            "test.py", content, ["my_function"]
        )
        assert len(evidence) > 0
        assert evidence[0].file_path == "test.py"
        assert "my_function" in evidence[0].relevance_explanation
    
    def test_finds_class_definition(self, retriever):
        content = (
            "class MyClass:\n"
            "    def __init__(self):\n"
            "        pass\n"
        )
        evidence = retriever._analyze_python_ast(
            "test.py", content, ["MyClass"]
        )
        assert len(evidence) > 0
        assert "class" in evidence[0].relevance_explanation.lower()
    
    def test_handles_syntax_error(self, retriever):
        content = "def broken(\n"  # Invalid Python
        evidence = retriever._analyze_python_ast(
            "test.py", content, ["broken"]
        )
        assert len(evidence) == 0  # Should not crash
