"""Feasibility agent analyzing requirements against Task 1 Knowledge Brain."""

from app.client.knowledge_client import KnowledgeBrainClient
from app.schemas import (
    FeasibilityCategory,
    RequirementFeasibility,
    RequirementItem,
)


class FeasibilityAgent:
    """Evaluates requirement feasibility by querying Task 1 Knowledge Brain."""

    def __init__(self, knowledge_client: KnowledgeBrainClient):
        self.knowledge_client = knowledge_client

    async def evaluate_feasibility(
        self, requirements: list[RequirementItem]
    ) -> list[RequirementFeasibility]:
        """Query Task 1 Knowledge Brain for each requirement and map evidence."""
        results: list[RequirementFeasibility] = []

        for req in requirements:
            # Check for known unsupported architectural requests (e.g., custom native mobile iOS/Android app)
            req_text = f"{req.title} {req.description}".lower()
            if any(k in req_text for k in ["native ios", "native app", "swift", "flutter", "mobile application", "app store", "native mobile"]):
                results.append(
                    RequirementFeasibility(
                        requirement_id=req.id,
                        feasibility_status=FeasibilityCategory.BLOCKED_BY_DEPENDENCY,
                        findings="Brilliant Directories is a responsive web application and does not provide native compiled mobile app binaries.",
                        evidence_citations=[],
                        missing_information=["Requires third-party mobile webview wrapper or custom API development"],
                        technical_notes="Native mobile apps are outside core platform capabilities.",
                        is_supported=False,
                    )
                )
                continue

            # Query Task 1 Knowledge Brain
            query = f"How does Brilliant Directories support {req.title}? {req.description}"
            knowledge = await self.knowledge_client.query_knowledge(query, top_k=3)

            if not knowledge.success:
                # Task 1 failure, outage, or client error
                results.append(
                    RequirementFeasibility(
                        requirement_id=req.id,
                        feasibility_status=FeasibilityCategory.INSUFFICIENT_EVIDENCE,
                        findings=f"Task 1 Knowledge Brain query failed or timed out: {knowledge.error or 'Service unavailable'}. Feasibility marked unverified pending human review.",
                        evidence_citations=[],
                        missing_information=["Task 1 documentation lookup could not complete"],
                        technical_notes="Technical validation required by engineering staff.",
                        is_supported=False,
                    )
                )
            elif knowledge.abstained or not knowledge.citations:
                # Task 1 abstained due to insufficient evidence
                results.append(
                    RequirementFeasibility(
                        requirement_id=req.id,
                        feasibility_status=FeasibilityCategory.INSUFFICIENT_EVIDENCE,
                        findings=f"Task 1 Knowledge Brain abstained: {knowledge.abstention_reason or 'No relevant documentation found'}.",
                        evidence_citations=[],
                        missing_information=["Official Solution Center documentation lacks specific evidence for this capability"],
                        technical_notes="May require custom widget coding or external plugin.",
                        is_supported=False,
                    )
                )
            else:
                # Evidence confirmed from Task 1 Knowledge Brain
                results.append(
                    RequirementFeasibility(
                        requirement_id=req.id,
                        feasibility_status=FeasibilityCategory.SUPPORTED_BY_EVIDENCE,
                        findings=knowledge.answer,
                        evidence_citations=knowledge.citations,
                        missing_information=[],
                        technical_notes=f"Supported by {len(knowledge.citations)} verified Solution Center article(s).",
                        is_supported=True,
                    )
                )

        return results
