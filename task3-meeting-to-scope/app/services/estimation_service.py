"""Estimation and proposal generation services."""

from agents.estimation_agent import EstimationAgent
from agents.proposal_agent import ProposalAgent
from app.schemas import (
    EstimateItem,
    EstimateSummary,
    ProposalResponse,
    RequirementFeasibility,
    RequirementItem,
    ScopeDocument,
)


class EstimationService:
    """Coordinates work package estimation and totals verification."""

    def __init__(self, agent: EstimationAgent):
        self.agent = agent

    async def generate_estimates(
        self,
        requirements: list[RequirementItem],
        feasibility_list: list[RequirementFeasibility] | None = None,
    ) -> tuple[list[EstimateItem], EstimateSummary]:
        return await self.agent.generate_estimates(requirements, feasibility_list)


class ProposalService:
    """Coordinates client proposal generation derived from ScopeDocument."""

    def __init__(self, agent: ProposalAgent):
        self.agent = agent

    def generate_proposal(self, scope: ScopeDocument) -> ProposalResponse:
        return self.agent.generate_proposal(scope)
