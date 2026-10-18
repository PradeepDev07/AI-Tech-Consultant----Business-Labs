"""Feasibility analysis service."""

from agents.feasibility_agent import FeasibilityAgent
from app.schemas import RequirementFeasibility, RequirementItem


class FeasibilityService:
    """Coordinates feasibility evaluation against Task 1 Knowledge Brain."""

    def __init__(self, agent: FeasibilityAgent):
        self.agent = agent

    async def evaluate(
        self, requirements: list[RequirementItem]
    ) -> list[RequirementFeasibility]:
        return await self.agent.evaluate_feasibility(requirements)
