"""Proposal generation service module."""

from agents.proposal_agent import ProposalAgent
from app.schemas import ProposalResponse, ScopeDocument


class ProposalService:
    """Coordinates client proposal generation derived from ScopeDocument."""

    def __init__(self, agent: ProposalAgent):
        self.agent = agent

    def generate_proposal(self, scope: ScopeDocument) -> ProposalResponse:
        return self.agent.generate_proposal(scope)
