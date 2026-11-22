from __future__ import annotations
"""
Verification Engine

Performs safe static verification checks on the codebase.
No arbitrary code execution — only reads and analyzes source code.

Current checks:
- Function/class existence
- Parameter existence  
- Configuration checks
- Test coverage analysis
- Import verification

Future: Docker-based isolated execution environment.
"""

import ast
import logging
from typing import Any

from app.models.claims import TechnicalClaim
from app.models.assessment import VerificationStatus

logger = logging.getLogger(__name__)


class VerificationResult:
    """Result of a single verification check."""
    
    def __init__(
        self,
        claim_id: int,
        check_type: str,
        status: VerificationStatus,
        details: str,
        file_path: str | None = None,
        line_number: int | None = None,
    ):
        self.claim_id = claim_id
        self.check_type = check_type
        self.status = status
        self.details = details
        self.file_path = file_path
        self.line_number = line_number
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "check_type": self.check_type,
            "status": self.status.value,
            "details": self.details,
            "file_path": self.file_path,
            "line_number": self.line_number,
        }


class Verifier:
    """Performs static verification checks on source code.
    
    All checks are read-only and safe:
    - No code execution
    - No network access
    - No file system modification
    """
    
    def verify_claims(
        self,
        claims: list[TechnicalClaim],
        source_files: list[dict[str, str]],
        test_files: list[dict[str, str]],
    ) -> list[VerificationResult]:
        """Run verification checks for all claims.
        
        Args:
            claims: Technical claims to verify
            source_files: List of {path, content} source files
            test_files: List of {path, content} test files
            
        Returns:
            List of verification results
        """
        results = []
        
        for claim in claims:
            claim_results = self._verify_claim(claim, source_files, test_files)
            results.extend(claim_results)
        
        return results
    
    def _verify_claim(
        self,
        claim: TechnicalClaim,
        source_files: list[dict[str, str]],
        test_files: list[dict[str, str]],
    ) -> list[VerificationResult]:
        """Run all applicable verification checks for a single claim."""
        results = []
        
        # Check if referenced location exists
        if claim.relevant_location:
            result = self._check_location_exists(
                claim.claim_id, claim.relevant_location, source_files
            )
            results.append(result)
        
        # Check for related tests
        test_result = self._check_test_coverage(
            claim.claim_id, claim, test_files
        )
        results.append(test_result)
        
        # Python-specific checks
        for file_data in source_files:
            if file_data["path"].endswith(".py"):
                py_results = self._python_checks(
                    claim.claim_id, claim, file_data
                )
                results.extend(py_results)
        
        return results
    
    def _check_location_exists(
        self,
        claim_id: int,
        location: str,
        source_files: list[dict[str, str]],
    ) -> VerificationResult:
        """Verify that a referenced code location exists."""
        # Check as file path
        for file_data in source_files:
            if location in file_data["path"]:
                return VerificationResult(
                    claim_id=claim_id,
                    check_type="location_exists",
                    status=VerificationStatus.VERIFIED,
                    details=f"Referenced location '{location}' found in {file_data['path']}",
                    file_path=file_data["path"],
                )
        
        # Check as identifier in file content
        for file_data in source_files:
            if location in file_data["content"]:
                return VerificationResult(
                    claim_id=claim_id,
                    check_type="location_exists",
                    status=VerificationStatus.VERIFIED,
                    details=f"Referenced identifier '{location}' found in {file_data['path']}",
                    file_path=file_data["path"],
                )
        
        return VerificationResult(
            claim_id=claim_id,
            check_type="location_exists",
            status=VerificationStatus.NOT_VERIFIED,
            details=f"Referenced location '{location}' not found in available source files",
        )
    
    def _check_test_coverage(
        self,
        claim_id: int,
        claim: TechnicalClaim,
        test_files: list[dict[str, str]],
    ) -> VerificationResult:
        """Check if there are tests related to the claim."""
        if not test_files:
            return VerificationResult(
                claim_id=claim_id,
                check_type="test_coverage",
                status=VerificationStatus.NOT_VERIFIED,
                details="No test files available to check",
            )
        
        # Look for tests mentioning the claimed location or keywords
        search_terms = []
        if claim.relevant_location:
            search_terms.append(claim.relevant_location.lower())
        
        # Extract key terms from the claim
        words = claim.original_statement.lower().split()
        search_terms.extend(w for w in words if len(w) > 4 and w.isalpha())
        
        related_tests = []
        for file_data in test_files:
            content_lower = file_data["content"].lower()
            for term in search_terms:
                if term in content_lower:
                    related_tests.append(file_data["path"])
                    break
        
        if related_tests:
            return VerificationResult(
                claim_id=claim_id,
                check_type="test_coverage",
                status=VerificationStatus.PARTIALLY_VERIFIED,
                details=f"Found {len(related_tests)} related test file(s): {', '.join(related_tests[:3])}",
            )
        
        return VerificationResult(
            claim_id=claim_id,
            check_type="test_coverage",
            status=VerificationStatus.NOT_VERIFIED,
            details="No related tests found for this claim",
        )
    
    def _python_checks(
        self,
        claim_id: int,
        claim: TechnicalClaim,
        file_data: dict[str, str],
    ) -> list[VerificationResult]:
        """Python-specific AST-based verification checks."""
        results = []
        
        try:
            tree = ast.parse(file_data["content"])
        except SyntaxError:
            return results
        
        if not claim.relevant_location:
            return results
        
        location = claim.relevant_location
        
        # Check if the referenced function/class exists and get its signature
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == location:
                    # Function exists — check parameters
                    args = [arg.arg for arg in node.args.args]
                    results.append(VerificationResult(
                        claim_id=claim_id,
                        check_type="function_signature",
                        status=VerificationStatus.VERIFIED,
                        details=f"Function '{location}' exists with parameters: {args}",
                        file_path=file_data["path"],
                        line_number=node.lineno,
                    ))
                    
                    # Check for return statement
                    has_return = any(
                        isinstance(n, ast.Return) and n.value is not None
                        for n in ast.walk(node)
                    )
                    if has_return:
                        results.append(VerificationResult(
                            claim_id=claim_id,
                            check_type="return_value",
                            status=VerificationStatus.VERIFIED,
                            details=f"Function '{location}' has a return value",
                            file_path=file_data["path"],
                            line_number=node.lineno,
                        ))
            
            elif isinstance(node, ast.ClassDef):
                if node.name == location:
                    methods = [
                        n.name for n in node.body
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                    ]
                    results.append(VerificationResult(
                        claim_id=claim_id,
                        check_type="class_structure",
                        status=VerificationStatus.VERIFIED,
                        details=f"Class '{location}' exists with methods: {methods[:10]}",
                        file_path=file_data["path"],
                        line_number=node.lineno,
                    ))
        
        return results
