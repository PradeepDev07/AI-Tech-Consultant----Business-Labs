"""Requirements extraction service."""

from agents.requirements_agent import RequirementsAgent
from app.schemas import RequirementItem


class RequirementsService:
    """Coordinates requirement extraction from raw transcript text."""

    def __init__(self, agent: RequirementsAgent):
        self.agent = agent

    async def extract(
        self, transcript_text: str
    ) -> tuple[list[RequirementItem], list[str], list[str]]:
        return await self.agent.extract_requirements(transcript_text)
