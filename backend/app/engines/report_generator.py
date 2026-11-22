from __future__ import annotations
"""
Report Generator Engine

Combines all pipeline outputs into a comprehensive TriageReport.
This is the final step — it aggregates claims, evidence, assessments,
and verification results into a structured report.
"""

import logging
from typing import Any

from app.models.claims import ClaimExtractionResult
from app.models.evidence import EvidenceRetrievalResult
from app.models.assessment import AssessmentResult, AssessmentLabel
from app.models.report import TriageReport, SubmissionOverview, ClaimReport

logger = logging.getLogger(__name__)


class ReportGenerator:
    """Generates the final triage report from all pipeline outputs."""
    
    def generate(
        self,
        analysis_id: str,
        github_url: str,
        owner: str,
        repo: str,
        number: int,
        submission_type: str,
        submission_data: dict[str, Any],
        claim_result: ClaimExtractionResult,
        evidence_result: EvidenceRetrievalResult,
        assessment_result: AssessmentResult,
        verification_results: list,
    ) -> TriageReport:
        """Generate the complete triage report.
        
        Combines:
        - Submission overview
        - Extracted claims
        - Evidence for each claim
        - AI assessments
        - Verification results
        - Overall assessment
        - Recommendations and limitations
        """
        # Build submission overview
        submission = SubmissionOverview(
            github_url=github_url,
            repo_owner=owner,
            repo_name=repo,
            issue_number=number,
            issue_type=submission_type,
            title=submission_data.get("title", ""),
            body_preview=(submission_data.get("body", "") or "")[:500],
            labels=[
                label.get("name", "") 
                for label in submission_data.get("labels", [])
            ],
            author=submission_data.get("user", {}).get("login", ""),
            created_at=submission_data.get("created_at", ""),
            comments_count=submission_data.get("comments", 0),
        )
        
        # Build per-claim reports
        evidence_map = {
            ce.claim_id: ce for ce in evidence_result.claim_evidence
        }
        assessment_map = {
            a.claim_id: a for a in assessment_result.assessments
        }
        verification_map: dict[int, list] = {}
        for vr in verification_results:
            cid = vr.claim_id if hasattr(vr, 'claim_id') else vr.get("claim_id", 0)
            if cid not in verification_map:
                verification_map[cid] = []
            verification_map[cid].append(vr)
        
        claim_reports = []
        for claim in claim_result.claims:
            claim_ev = evidence_map.get(claim.claim_id)
            evidence_dicts = []
            if claim_ev:
                evidence_dicts = [
                    item.model_dump() for item in claim_ev.evidence_items
                ]
            
            assessment = assessment_map.get(claim.claim_id)
            
            claim_reports.append(ClaimReport(
                claim=claim,
                evidence=evidence_dicts,
                assessment=assessment,
            ))
        
        # Determine overall assessment
        overall_assessment, overall_confidence = self._compute_overall(
            assessment_result
        )
        
        # Build recommendations
        recommendations = self._build_recommendations(
            claim_reports, assessment_result
        )
        
        # Build limitations
        limitations = self._build_limitations(
            claim_result, evidence_result, assessment_result
        )
        
        # Overall reasoning
        overall_reasoning = self._build_overall_reasoning(
            claim_reports, overall_assessment
        )
        
        # Metadata
        metadata = {
            "total_claims": len(claim_result.claims),
            "total_evidence_items": evidence_result.total_evidence_items,
            "files_searched": evidence_result.total_files_searched,
            "ai_available": assessment_result.ai_available,
            "model_used": assessment_result.model_used,
            "verification_checks": len(verification_results),
        }
        
        return TriageReport(
            analysis_id=analysis_id,
            submission=submission,
            claims=claim_reports,
            overall_assessment=overall_assessment,
            overall_confidence=overall_confidence,
            overall_reasoning=overall_reasoning,
            recommendations=recommendations,
            limitations=limitations,
            metadata=metadata,
        )
    
    def _compute_overall(
        self, assessment_result: AssessmentResult
    ) -> tuple[AssessmentLabel | None, float | None]:
        """Compute the overall assessment from individual claim assessments.
        
        Strategy: Use the most severe assessment as the overall.
        If any claim is CONFIRMED, the overall is CONFIRMED.
        If none confirmed but some are INVALID, overall is INVALID.
        Otherwise CANNOT_REPRODUCE.
        """
        if not assessment_result.assessments:
            return None, None
        
        confirmed = 0
        invalid = 0
        cannot_reproduce = 0
        total_confidence = 0.0
        
        for a in assessment_result.assessments:
            total_confidence += a.confidence
            if a.assessment == AssessmentLabel.CONFIRMED:
                confirmed += 1
            elif a.assessment == AssessmentLabel.INVALID:
                invalid += 1
            else:
                cannot_reproduce += 1
        
        avg_confidence = total_confidence / len(assessment_result.assessments)
        
        # Determine overall label
        if confirmed > 0 and confirmed >= invalid:
            return AssessmentLabel.CONFIRMED, avg_confidence
        elif invalid > 0 and invalid > confirmed:
            return AssessmentLabel.INVALID, avg_confidence
        else:
            return AssessmentLabel.CANNOT_REPRODUCE, avg_confidence
    
    def _build_recommendations(
        self,
        claim_reports: list[ClaimReport],
        assessment_result: AssessmentResult,
    ) -> list[str]:
        """Build maintainer recommendations based on the analysis."""
        recommendations = []
        
        confirmed_claims = [
            cr for cr in claim_reports
            if cr.assessment and cr.assessment.assessment == AssessmentLabel.CONFIRMED
        ]
        invalid_claims = [
            cr for cr in claim_reports
            if cr.assessment and cr.assessment.assessment == AssessmentLabel.INVALID
        ]
        unresolved_claims = [
            cr for cr in claim_reports
            if cr.assessment and cr.assessment.assessment == AssessmentLabel.CANNOT_REPRODUCE
        ]
        
        if confirmed_claims:
            recommendations.append(
                f"{len(confirmed_claims)} claim(s) appear to be supported by repository evidence. "
                "Consider investigating and prioritizing these."
            )
        
        if invalid_claims:
            recommendations.append(
                f"{len(invalid_claims)} claim(s) appear to be contradicted by available evidence. "
                "Consider requesting clarification from the submitter."
            )
        
        if unresolved_claims:
            recommendations.append(
                f"{len(unresolved_claims)} claim(s) could not be fully evaluated with available evidence. "
                "Additional information or manual investigation may be needed."
            )
        
        if not assessment_result.ai_available:
            recommendations.append(
                "AI analysis was not available for this run. "
                "Configure GEMINI_API_KEY and re-run for more detailed assessments."
            )
        
        # Include individual claim recommendations
        for cr in claim_reports:
            if cr.assessment and cr.assessment.recommendation:
                recommendations.append(
                    f"Claim #{cr.claim.claim_id}: {cr.assessment.recommendation}"
                )
        
        return recommendations
    
    def _build_limitations(
        self,
        claim_result: ClaimExtractionResult,
        evidence_result: EvidenceRetrievalResult,
        assessment_result: AssessmentResult,
    ) -> list[str]:
        """Document the limitations of this analysis."""
        limitations = [
            "This analysis is based on static code analysis and AI reasoning. "
            "No code was executed to reproduce reported issues.",
            "Confidence scores are model estimates, not calibrated probabilities.",
        ]
        
        if not assessment_result.ai_available:
            limitations.append(
                "AI-powered analysis was not available. "
                "Claims were not semantically evaluated."
            )
        
        if claim_result.warnings:
            limitations.extend(claim_result.warnings)
        
        if evidence_result.warnings:
            limitations.extend(evidence_result.warnings)
        
        if assessment_result.warnings:
            limitations.extend(assessment_result.warnings)
        
        limitations.append(
            "Only publicly accessible repository files were analyzed. "
            "Private dependencies, runtime state, and environment-specific "
            "factors were not considered."
        )
        
        return limitations
    
    def _build_overall_reasoning(
        self,
        claim_reports: list[ClaimReport],
        overall_assessment: AssessmentLabel | None,
    ) -> str:
        """Build a human-readable overall reasoning summary."""
        if not claim_reports:
            return "No technical claims were extracted from this submission."
        
        parts = [f"Analyzed {len(claim_reports)} technical claim(s)."]
        
        for cr in claim_reports:
            if cr.assessment:
                parts.append(
                    f"Claim #{cr.claim.claim_id} ({cr.claim.claim_type.value}): "
                    f"{cr.assessment.assessment.value} "
                    f"(confidence: {cr.assessment.confidence:.0%})"
                )
        
        if overall_assessment:
            parts.append(f"\nOverall assessment: {overall_assessment.value}")
        
        return "\n".join(parts)
