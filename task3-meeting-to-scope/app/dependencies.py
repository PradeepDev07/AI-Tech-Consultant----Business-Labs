"""FastAPI dependency injection factories for Task 3."""

from functools import lru_cache
from fastapi import Depends
from agents.estimation_agent import EstimationAgent
from agents.feasibility_agent import FeasibilityAgent
from agents.proposal_agent import ProposalAgent
from agents.requirements_agent import RequirementsAgent
from app.client.knowledge_client import KnowledgeBrainClient
from app.config import Settings, get_settings
from app.database import Database
from app.providers.model_provider import (
    BaseModelProvider,
    MockModelProvider,
    OllamaModelProvider,
    ProviderManager,
    get_provider_manager,
)
from app.services.approval_service import ApprovalService
from app.services.estimation_service import EstimationService
from app.services.feasibility_service import FeasibilityService
from app.services.proposal_service import ProposalService
from app.services.requirements_service import RequirementsService
from app.services.scope_diff_service import ScopeDiffService
from app.services.transcript_service import TranscriptService


def get_database(settings: Settings = Depends(get_settings)) -> Database:
    return Database(db_path=settings.DATABASE_PATH)


def get_knowledge_client(
    settings: Settings = Depends(get_settings),
) -> KnowledgeBrainClient:
    return KnowledgeBrainClient(
        base_url=settings.TASK1_API_BASE_URL,
        timeout_seconds=settings.TASK1_API_TIMEOUT_SECONDS,
        max_retries=settings.TASK1_MAX_RETRIES,
    )


def get_provider_manager_instance() -> ProviderManager:
    return get_provider_manager()


def get_model_provider(
    settings: Settings = Depends(get_settings),
) -> BaseModelProvider:
    return get_provider_manager().get_active_provider()


def get_transcript_service(
    database: Database = Depends(get_database),
    settings: Settings = Depends(get_settings),
) -> TranscriptService:
    return TranscriptService(database=database, max_length=settings.MAX_TRANSCRIPT_LENGTH)


def get_requirements_service(
    model_provider: BaseModelProvider = Depends(get_model_provider),
) -> RequirementsService:
    agent = RequirementsAgent(model_provider=model_provider)
    return RequirementsService(agent=agent)


def get_feasibility_service(
    knowledge_client: KnowledgeBrainClient = Depends(get_knowledge_client),
) -> FeasibilityService:
    agent = FeasibilityAgent(knowledge_client=knowledge_client)
    return FeasibilityService(agent=agent)


def get_estimation_service(
    model_provider: BaseModelProvider = Depends(get_model_provider),
) -> EstimationService:
    agent = EstimationAgent(model_provider=model_provider)
    return EstimationService(agent=agent)


def get_proposal_service() -> ProposalService:
    agent = ProposalAgent()
    return ProposalService(agent=agent)


def get_scope_diff_service(
    database: Database = Depends(get_database),
) -> ScopeDiffService:
    return ScopeDiffService(database=database)


def get_approval_service(
    database: Database = Depends(get_database),
) -> ApprovalService:
    return ApprovalService(database=database)
