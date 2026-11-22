from __future__ import annotations
"""
Evidence Retrieval Engine

Finds relevant repository evidence for each technical claim.
Uses lexical search, Python AST analysis, and pattern matching
to locate supporting, contradicting, or related code.

Designed with an extensible architecture — vector search can be added later.
"""

import ast
import logging
import re
from typing import Any

from app.models.claims import TechnicalClaim
from app.models.evidence import (
    ClaimEvidence,
    EvidenceCategory,
    EvidenceItem,
    EvidenceRetrievalResult,
)

logger = logging.getLogger(__name__)

# Maximum snippet length to include
MAX_SNIPPET_LENGTH = 2000


class EvidenceRetriever:
    """Retrieves evidence from repository files for each claim.
    
    Current methods:
    - Lexical search (keyword matching)
    - Python AST analysis (function/class extraction)
    - File path matching
    - Test discovery
    - Documentation search
    
    Future extension point: add VectorRetriever for semantic search.
    """
    
    def retrieve_evidence(
        self,
        claims: list[TechnicalClaim],
        relevant_files: list[dict[str, str]],
        test_files: list[dict[str, str]],
        readme: str,
        file_tree: list[dict],
    ) -> EvidenceRetrievalResult:
        """Find evidence for each claim from the repository data.
        
        Args:
            claims: Extracted technical claims
            relevant_files: List of {path, content} dicts for relevant source files
            test_files: List of {path, content} dicts for test files
            readme: README content
            file_tree: Full file listing for context
            
        Returns:
            EvidenceRetrievalResult with evidence for each claim
        """
        all_files = relevant_files + test_files
        claim_evidence_list = []
        total_evidence = 0
        
        for claim in claims:
            evidence = self._find_evidence_for_claim(
                claim, relevant_files, test_files, readme, file_tree
            )
            claim_evidence_list.append(evidence)
            total_evidence += len(evidence.evidence_items)
        
        return EvidenceRetrievalResult(
            claim_evidence=claim_evidence_list,
            total_files_searched=len(all_files),
            total_evidence_items=total_evidence,
        )
    
    def _find_evidence_for_claim(
        self,
        claim: TechnicalClaim,
        relevant_files: list[dict[str, str]],
        test_files: list[dict[str, str]],
        readme: str,
        file_tree: list[dict],
    ) -> ClaimEvidence:
        """Find all evidence items for a single claim."""
        evidence_items = []
        search_queries = []
        
        # Build search terms from the claim
        search_terms = self._extract_search_terms(claim)
        search_queries.extend(search_terms)
        
        # Search source files
        for file_data in relevant_files:
            path = file_data["path"]
            content = file_data["content"]
            
            matches = self._search_file(content, search_terms, path)
            for match in matches:
                evidence_items.append(EvidenceItem(
                    file_path=path,
                    line_start=match.get("line_start"),
                    line_end=match.get("line_end"),
                    snippet=match["snippet"][:MAX_SNIPPET_LENGTH],
                    category=EvidenceCategory.SOURCE_CODE,
                    relevance_explanation=match.get("reason", ""),
                    relevance_score=match.get("score", 0.5),
                ))
        
        # Search test files
        for file_data in test_files:
            path = file_data["path"]
            content = file_data["content"]
            
            matches = self._search_file(content, search_terms, path)
            for match in matches:
                evidence_items.append(EvidenceItem(
                    file_path=path,
                    line_start=match.get("line_start"),
                    line_end=match.get("line_end"),
                    snippet=match["snippet"][:MAX_SNIPPET_LENGTH],
                    category=EvidenceCategory.TEST,
                    relevance_explanation=match.get("reason", ""),
                    relevance_score=match.get("score", 0.4),
                ))
        
        # Search README/docs
        if readme:
            doc_matches = self._search_text(readme, search_terms)
            for match in doc_matches:
                evidence_items.append(EvidenceItem(
                    file_path="README.md",
                    line_start=match.get("line_start"),
                    line_end=match.get("line_end"),
                    snippet=match["snippet"][:MAX_SNIPPET_LENGTH],
                    category=EvidenceCategory.DOCUMENTATION,
                    relevance_explanation=match.get("reason", ""),
                    relevance_score=match.get("score", 0.3),
                ))
        
        # If claim references a specific location, check if it exists in the file tree
        if claim.relevant_location:
            location_evidence = self._check_location_exists(
                claim.relevant_location, file_tree, relevant_files
            )
            if location_evidence:
                evidence_items.append(location_evidence)
        
        # Python AST analysis for .py files
        for file_data in relevant_files:
            if file_data["path"].endswith(".py"):
                ast_evidence = self._analyze_python_ast(
                    file_data["path"], file_data["content"], search_terms
                )
                evidence_items.extend(ast_evidence)
        
        # Sort by relevance first so higher quality evidence (e.g. AST score 0.9) takes precedence during deduplication
        evidence_items.sort(key=lambda x: x.relevance_score, reverse=True)

        # Deduplicate by file_path + line_start
        seen = set()
        unique_evidence = []
        for item in evidence_items:
            key = (item.file_path, item.line_start)
            if key not in seen:
                seen.add(key)
                unique_evidence.append(item)
        
        # Sort by relevance
        unique_evidence.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return ClaimEvidence(
            claim_id=claim.claim_id,
            evidence_items=unique_evidence[:20],  # Cap at 20 per claim
            search_queries_used=search_queries,
        )
    
    def _extract_search_terms(self, claim: TechnicalClaim) -> list[str]:
        """Extract meaningful search terms from a claim."""
        terms = []
        
        # From the original statement — extract identifiers
        text = claim.original_statement
        # Find words that look like code identifiers (camelCase, snake_case, etc.)
        identifiers = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)*\b', text)
        # Filter out common English words
        common_words = {
            "the", "is", "are", "was", "were", "be", "been", "being",
            "have", "has", "had", "do", "does", "did", "will", "would",
            "could", "should", "may", "might", "must", "shall", "can",
            "not", "no", "nor", "and", "but", "or", "if", "then",
            "else", "when", "where", "which", "that", "this", "these",
            "those", "what", "who", "how", "why", "all", "each",
            "every", "both", "few", "more", "most", "other", "some",
            "such", "than", "too", "very", "just", "because", "as",
            "until", "while", "of", "at", "by", "for", "with",
            "about", "against", "between", "through", "during",
            "before", "after", "above", "below", "to", "from",
            "in", "out", "on", "off", "over", "under", "again",
            "further", "it", "its", "also", "into", "only", "so",
            "an", "a", "my", "your", "their", "our", "i", "you",
            "he", "she", "they", "we", "me", "him", "her", "us",
            "them", "there", "here", "up", "down",
        }
        for ident in identifiers:
            if ident.lower() not in common_words and len(ident) > 2:
                terms.append(ident)
        
        # From relevant location
        if claim.relevant_location:
            terms.append(claim.relevant_location)
            # Split on dots and slashes for path-like locations
            parts = re.split(r'[./\\]', claim.relevant_location)
            terms.extend(p for p in parts if len(p) > 2)
        
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for t in terms:
            if t.lower() not in seen:
                seen.add(t.lower())
                unique.append(t)
        
        return unique[:15]  # Cap search terms
    
    def _search_file(
        self, content: str, terms: list[str], file_path: str
    ) -> list[dict]:
        """Search a file for lines matching any of the search terms."""
        matches = []
        lines = content.split("\n")
        
        for term in terms:
            term_lower = term.lower()
            for i, line in enumerate(lines, 1):
                if term_lower in line.lower():
                    # Get surrounding context (3 lines before and after)
                    start = max(0, i - 4)
                    end = min(len(lines), i + 3)
                    snippet = "\n".join(lines[start:end])
                    
                    matches.append({
                        "line_start": i,
                        "line_end": min(i + 2, len(lines)),
                        "snippet": snippet,
                        "reason": f"Contains '{term}' (line {i})",
                        "score": 0.6,
                    })
        
        return matches
    
    def _search_text(self, text: str, terms: list[str]) -> list[dict]:
        """Search a text block for matching terms."""
        matches = []
        lines = text.split("\n")
        
        for term in terms:
            term_lower = term.lower()
            for i, line in enumerate(lines, 1):
                if term_lower in line.lower():
                    start = max(0, i - 3)
                    end = min(len(lines), i + 3)
                    snippet = "\n".join(lines[start:end])
                    
                    matches.append({
                        "line_start": i,
                        "line_end": min(i + 2, len(lines)),
                        "snippet": snippet,
                        "reason": f"Documentation mentions '{term}'",
                        "score": 0.3,
                    })
        
        return matches
    
    def _check_location_exists(
        self,
        location: str,
        file_tree: list[dict],
        relevant_files: list[dict[str, str]],
    ) -> EvidenceItem | None:
        """Check if a referenced location exists in the repository."""
        all_paths = {f["path"] for f in file_tree}
        
        # Check if it's a file path
        if location in all_paths:
            return EvidenceItem(
                file_path=location,
                snippet=f"File exists in repository: {location}",
                category=EvidenceCategory.SOURCE_CODE,
                relevance_explanation=f"Referenced file '{location}' exists in the repository",
                relevance_score=0.8,
            )
        
        # Check if it's a function or class in any of the files
        for file_data in relevant_files:
            if location in file_data["content"]:
                # Find the line
                lines = file_data["content"].split("\n")
                for i, line in enumerate(lines, 1):
                    if location in line:
                        start = max(0, i - 2)
                        end = min(len(lines), i + 5)
                        snippet = "\n".join(lines[start:end])
                        return EvidenceItem(
                            file_path=file_data["path"],
                            line_start=i,
                            line_end=min(i + 4, len(lines)),
                            snippet=snippet,
                            category=EvidenceCategory.SOURCE_CODE,
                            relevance_explanation=f"Referenced identifier '{location}' found",
                            relevance_score=0.8,
                        )
        
        return None
    
    def _analyze_python_ast(
        self, file_path: str, content: str, search_terms: list[str]
    ) -> list[EvidenceItem]:
        """Use Python's AST module to extract functions and classes.
        
        This provides more precise matching than text search —
        it understands the code structure.
        """
        evidence = []
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return evidence
        
        lines = content.split("\n")
        terms_lower = {t.lower() for t in search_terms}
        
        for node in ast.walk(tree):
            name = None
            node_type = None
            
            if isinstance(node, ast.FunctionDef):
                name = node.name
                node_type = "function"
            elif isinstance(node, ast.AsyncFunctionDef):
                name = node.name
                node_type = "async function"
            elif isinstance(node, ast.ClassDef):
                name = node.name
                node_type = "class"
            
            if name and name.lower() in terms_lower:
                start_line = node.lineno
                end_line = getattr(node, 'end_lineno', start_line + 5)
                # Get the first few lines of the definition
                snippet_start = max(0, start_line - 1)
                snippet_end = min(len(lines), snippet_start + 10)
                snippet = "\n".join(lines[snippet_start:snippet_end])
                
                evidence.append(EvidenceItem(
                    file_path=file_path,
                    line_start=start_line,
                    line_end=min(end_line, start_line + 10),
                    snippet=snippet[:MAX_SNIPPET_LENGTH],
                    category=EvidenceCategory.SOURCE_CODE,
                    relevance_explanation=f"Python {node_type} '{name}' definition found via AST analysis",
                    relevance_score=0.9,
                ))
        
        return evidence
