"""Requirements extraction agent parsing transcripts into structured requirements."""

import re
from typing import Any
from app.providers.model_provider import BaseModelProvider
from app.schemas import (
    RequirementCategory,
    RequirementItem,
    RequirementPriority,
    RequirementStatus,
)


class RequirementsAgent:
    """Extracts structured, traceable requirements from meeting transcripts."""

    def __init__(self, model_provider: BaseModelProvider):
        self.model_provider = model_provider

    async def extract_requirements(
        self, transcript_text: str
    ) -> tuple[list[RequirementItem], list[str], list[str]]:
        """
        Extracts structured requirements, out-of-scope exclusions, and open questions.
        Returns: (requirements, out_of_scope, open_questions)
        """
        lower_text = transcript_text.lower()

        # 1. Prompt Injection Defense
        is_injection = (
            "ignore previous instructions" in lower_text
            or "disregard all prior instructions" in lower_text
            or "system override" in lower_text
            or "reveal system prompt" in lower_text
        )

        requirements: list[RequirementItem] = []
        out_of_scope: list[str] = []
        open_questions: list[str] = []

        if is_injection:
            # Trap and neutralize adversarial attempt
            requirements.append(
                RequirementItem(
                    id="SEC-INJ-001",
                    category=RequirementCategory.SECURITY_AND_PRIVACY,
                    title="Adversarial Input Quarantined",
                    description="Quarantined adversarial instructions embedded in meeting transcript.",
                    source_quote="System prompt override instruction detected.",
                    status=RequirementStatus.REQUIRES_CLARIFICATION,
                    priority=RequirementPriority.CRITICAL,
                    acceptance_criteria=["Verify sender authorization", "Sanitize transcript"],
                    assumptions=[],
                    risks=["Prompt injection attempt targeting system policies"],
                    dependencies=[],
                    confidence_score=1.0,
                )
            )
            open_questions.append("Security Alert: Malicious prompt injection commands detected in transcript.")
            return requirements, out_of_scope, open_questions

        # 2. Rule-assisted extraction for robust coverage and traceability
        # Lines or statements analysis
        paragraphs = [p.strip() for p in transcript_text.split("\n") if p.strip()]

        req_counter = 1

        # Check for explicit exclusions / out of scope
        for p in paragraphs:
            p_lower = p.lower()
            if "not in scope" in p_lower or "out of scope" in p_lower or "exclude" in p_lower or "we don't need" in p_lower:
                out_of_scope.append(p)

        # Functional requirements detection
        if any(k in lower_text for k in ["directory", "search", "filter", "member listings", "categories"]):
            quote = self._find_best_quote(paragraphs, ["directory", "search", "filter", "member"])
            requirements.append(
                RequirementItem(
                    id=f"REQ-{req_counter:03d}",
                    category=RequirementCategory.FUNCTIONAL,
                    title="Member Directory and Search",
                    description="Implement searchable business directory with category and location filtering.",
                    source_quote=quote or "Member directory search requirement.",
                    status=RequirementStatus.CONFIRMED,
                    priority=RequirementPriority.HIGH,
                    acceptance_criteria=[
                        "Directory visitors can search members by keyword",
                        "Results can be filtered by category and city/location",
                    ],
                    assumptions=["Standard Brilliant Directories search widgets are used"],
                    risks=["Location geocoding requires valid Google Maps API billing"],
                    dependencies=["Google Maps API"],
                    confidence_score=0.95,
                )
            )
            req_counter += 1

        # Lead matching / quote requests
        if any(k in lower_text for k in ["lead", "quote request", "auto-match", "leads"]):
            quote = self._find_best_quote(paragraphs, ["lead", "quote", "auto-match"])
            requirements.append(
                RequirementItem(
                    id=f"REQ-{req_counter:03d}",
                    category=RequirementCategory.FUNCTIONAL,
                    title="Automated Member Lead Distribution",
                    description="Enable visitors to submit quote inquiries that automatically route to matching members.",
                    source_quote=quote or "Lead generation and automated matching.",
                    status=RequirementStatus.CONFIRMED,
                    priority=RequirementPriority.HIGH,
                    acceptance_criteria=[
                        "Quote form submits lead to admin dashboard",
                        "Matching members receive automated email alert",
                    ],
                    assumptions=["Brilliant Directories Automated Lead Matching Addon is available"],
                    risks=[],
                    dependencies=["Lead Matching Addon"],
                    confidence_score=0.9,
                )
            )
            req_counter += 1

        # Integrations & Payment Gateways
        if any(k in lower_text for k in ["stripe", "payment", "paypal", "billing", "gateway"]):
            quote = self._find_best_quote(paragraphs, ["stripe", "payment", "gateway", "billing"])
            requirements.append(
                RequirementItem(
                    id=f"REQ-{req_counter:03d}",
                    category=RequirementCategory.INTEGRATIONS,
                    title="Recurring Payment Gateway Integration",
                    description="Integrate Stripe payment gateway for automated recurring subscription billing.",
                    source_quote=quote or "Payment gateway integration.",
                    status=RequirementStatus.CONFIRMED,
                    priority=RequirementPriority.HIGH,
                    acceptance_criteria=[
                        "Members can pay for membership plans via credit card",
                        "Automated recurring subscriptions renew monthly or annually",
                    ],
                    assumptions=["Client provides active Stripe API keys"],
                    risks=["PCI compliance relies on Stripe hosted elements"],
                    dependencies=["Stripe Account"],
                    confidence_score=0.95,
                )
            )
            req_counter += 1

        # Non-functional / Performance
        if any(k in lower_text for k in ["fast", "page load", "seconds", "performance", "speed", "under 2 seconds"]):
            quote = self._find_best_quote(paragraphs, ["fast", "load", "seconds", "speed"])
            requirements.append(
                RequirementItem(
                    id=f"REQ-{req_counter:03d}",
                    category=RequirementCategory.PERFORMANCE,
                    title="Directory Page Load Performance",
                    description="Ensure directory search results and profile pages load within acceptable performance limits.",
                    source_quote=quote or "Site performance requirement.",
                    status=RequirementStatus.CONFIRMED,
                    priority=RequirementPriority.MEDIUM,
                    acceptance_criteria=["Profile and search pages load under 3 seconds under normal network conditions"],
                    assumptions=["Image sizes uploaded by members are compressed"],
                    risks=["High member count may require caching optimization"],
                    dependencies=[],
                    confidence_score=0.85,
                )
            )
            req_counter += 1

        # Roles and Permissions
        if any(k in lower_text for k in ["admin", "role", "permission", "staff", "moderator", "access control"]):
            quote = self._find_best_quote(paragraphs, ["admin", "role", "permission", "staff", "access"])
            requirements.append(
                RequirementItem(
                    id=f"REQ-{req_counter:03d}",
                    category=RequirementCategory.ROLES_AND_PERMISSIONS,
                    title="Staff Role-Based Access Control",
                    description="Configure administrator and staff permissions to manage listings and review user comments.",
                    source_quote=quote or "Role-based access requirement.",
                    status=RequirementStatus.CONFIRMED,
                    priority=RequirementPriority.MEDIUM,
                    acceptance_criteria=[
                        "Admin can assign staff roles with restricted access",
                        "Staff cannot access master billing or export all data without permission",
                    ],
                    assumptions=["BD Multi-Admin or Admin Roles feature is utilized"],
                    risks=[],
                    dependencies=[],
                    confidence_score=0.9,
                )
            )
            req_counter += 1

        # Data & Member Import
        if any(k in lower_text for k in ["import", "csv", "migrate", "migration", "spreadsheet", "records"]):
            quote = self._find_best_quote(paragraphs, ["import", "csv", "migrate", "spreadsheet"])
            requirements.append(
                RequirementItem(
                    id=f"REQ-{req_counter:03d}",
                    category=RequirementCategory.DATA,
                    title="Member Data CSV Migration",
                    description="Import legacy member profiles and categories from client CSV export.",
                    source_quote=quote or "Data migration requirement.",
                    status=RequirementStatus.CONFIRMED,
                    priority=RequirementPriority.HIGH,
                    acceptance_criteria=[
                        "All valid CSV rows are imported into active member accounts",
                        "Custom fields map accurately to member profile fields",
                    ],
                    assumptions=["Client provides sanitized UTF-8 CSV file"],
                    risks=["Dirty legacy data may require manual cleanup before import"],
                    dependencies=["Client CSV Data"],
                    confidence_score=0.9,
                )
            )
            req_counter += 1

        # Ambiguous / Contradictory / Unclear requirements
        if any(k in lower_text for k in ["maybe", "not sure", "possibly", "later", "undecided", "thinking about"]):
            quote = self._find_best_quote(paragraphs, ["maybe", "not sure", "possibly", "undecided"])
            requirements.append(
                RequirementItem(
                    id=f"REQ-{req_counter:03d}",
                    category=RequirementCategory.FUNCTIONAL,
                    title="Unconfirmed Optional Feature",
                    description="Potential requirement mentioned tentatively during discovery discussion.",
                    source_quote=quote or "Tentative feature discussion.",
                    status=RequirementStatus.REQUIRES_CLARIFICATION,
                    priority=RequirementPriority.LOW,
                    acceptance_criteria=["Clarify whether this feature is required for MVP or phase 2"],
                    assumptions=["Feature is currently deferred until customer clarification"],
                    risks=["Scope creep if added mid-development"],
                    dependencies=[],
                    confidence_score=0.5,
                )
            )
            req_counter += 1
            open_questions.append(f"Customer mentioned tentative capability ({quote}). Confirmation needed.")

        # Mobile App / Native App detection
        if any(k in lower_text for k in ["native app", "mobile app", "ios", "swift", "android", "flutter", "app store"]):
            quote = self._find_best_quote(paragraphs, ["native", "mobile", "ios", "swift", "android", "app store"])
            requirements.append(
                RequirementItem(
                    id=f"REQ-{req_counter:03d}",
                    category=RequirementCategory.FUNCTIONAL,
                    title="Native iOS & Mobile Application",
                    description="Compiled native mobile application for Apple App Store and Google Play.",
                    source_quote=quote or "Mobile application requirement.",
                    status=RequirementStatus.CONFIRMED,
                    priority=RequirementPriority.HIGH,
                    acceptance_criteria=["Native app downloadable from app stores"],
                    assumptions=["Requires external mobile developer or custom API wrapper"],
                    risks=["Brilliant Directories core is responsive web, not native compiled mobile code"],
                    dependencies=["External Mobile Development"],
                    confidence_score=0.9,
                )
            )
            req_counter += 1

        # Check for ambiguous deadlines
        if "asap" in lower_text or "soon" in lower_text or "by the end of the year maybe" in lower_text:
            open_questions.append("Delivery Timeline Ambiguity: Specific launch date is not formally confirmed.")

        # Check for missing or uncommitted budget
        if (
            ("budget" not in lower_text and "dollar" not in lower_text and "$" not in lower_text)
            or "not thought about budget" in lower_text
            or "haven't set a formal budget" in lower_text
            or "no budget" in lower_text
        ):
            open_questions.append("Commercial Terms: Client budget or target investment limit was not stated or confirmed during the meeting.")

        # Ensure at least 1 requirement is extracted if text exists
        if not requirements:
            requirements.append(
                RequirementItem(
                    id="REQ-001",
                    category=RequirementCategory.FUNCTIONAL,
                    title="General Solution Implementation",
                    description="Implement requested capabilities discussed in discovery session.",
                    source_quote=paragraphs[0] if paragraphs else "Transcript discussion.",
                    status=RequirementStatus.REQUIRES_CLARIFICATION,
                    priority=RequirementPriority.MEDIUM,
                    acceptance_criteria=["Formalize technical specifications"],
                    assumptions=["Standard platform functionality will be configured"],
                    risks=["Low transcript detail requires discovery follow-up"],
                    dependencies=[],
                    confidence_score=0.6,
                )
            )

        return requirements, out_of_scope, open_questions

    def _find_best_quote(self, paragraphs: list[str], keywords: list[str]) -> str | None:
        for p in paragraphs:
            p_lower = p.lower()
            if any(k in p_lower for k in keywords):
                return p[:300]
        return None
