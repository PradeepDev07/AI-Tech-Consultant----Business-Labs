"""Escalation service handling human-in-the-loop expert review and approval."""

import uuid
from app.core.exceptions import EscalationNotFoundError
from app.schemas.escalation import (
    EscalationListResponse,
    EscalationResponse,
    EscalationStatus,
)
from app.services.database import Database


class EscalationService:
    """Service managing human escalation lifecycle."""

    def __init__(self, db: Database, vector_store=None):
        self.db = db
        self.vector_store = vector_store

    def create_escalation(
        self,
        question: str,
        retrieved_evidence: list[dict],
        context: dict | None = None,
    ) -> EscalationResponse:
        """Create a new escalation record for an unsupported or ambiguous question."""
        escalation_id = f"esc-{uuid.uuid4().hex[:10]}"
        record = self.db.create_escalation(
            escalation_id=escalation_id,
            question=question,
            retrieved_evidence=retrieved_evidence,
            context=context,
        )
        return EscalationResponse(**record)

    def get_escalation(self, escalation_id: str) -> EscalationResponse:
        """Retrieve escalation details."""
        record = self.db.get_escalation(escalation_id)
        if not record:
            raise EscalationNotFoundError(f"Escalation '{escalation_id}' not found.")
        return EscalationResponse(**record)

    def list_escalations(
        self,
        status: EscalationStatus | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> EscalationListResponse:
        """List escalation records with optional status filter."""
        records, total = self.db.list_escalations(
            status=status.value if status else None, limit=limit, offset=offset
        )
        return EscalationListResponse(
            total=total,
            escalations=[EscalationResponse(**r) for r in records],
        )

    def answer_escalation(
        self, escalation_id: str, expert_answer: str, expert_name: str
    ) -> EscalationResponse:
        """Record expert response for an open escalation."""
        record = self.db.get_escalation(escalation_id)
        if not record:
            raise EscalationNotFoundError(f"Escalation '{escalation_id}' not found.")
        updated = self.db.answer_escalation(escalation_id, expert_answer, expert_name)
        return EscalationResponse(**updated)

    def approve_escalation(
        self, escalation_id: str, approved_by: str, reviewer_notes: str | None = None
    ) -> EscalationResponse:
        """Approve expert answer and index it as authoritative knowledge."""
        record = self.db.get_escalation(escalation_id)
        if not record:
            raise EscalationNotFoundError(f"Escalation '{escalation_id}' not found.")

        updated = self.db.approve_escalation(
            escalation_id=escalation_id,
            approved_by=approved_by,
            reviewer_notes=reviewer_notes,
        )

        # Index approved answer into the vector store as verified expert knowledge
        if self.vector_store is not None:
            self._index_approved_knowledge(updated)
            self.db.mark_escalation_reindexed(escalation_id)
            updated = self.db.get_escalation(escalation_id)

        return EscalationResponse(**updated)

    def _index_approved_knowledge(self, escalation_dict: dict) -> None:
        """Store approved Q&A pair in vector store as an authoritative chunk."""
        content = (
            f"Question: {escalation_dict['question']}\n\n"
            f"Expert Approved Answer: {escalation_dict['expert_answer']}\n"
            f"Approved By: {escalation_dict.get('approved_by', 'Knowledge Admin')}"
        )
        doc_id = f"escalation-{escalation_dict['escalation_id']}"
        metadata = {
            "source_type": "approved_expert_answer",
            "article_id": escalation_dict["escalation_id"],
            "title": f"Expert Answer: {escalation_dict['question'][:60]}",
            "source_url": f"/escalations/{escalation_dict['escalation_id']}",
            "heading": "Human Expert Knowledge",
            "chunk_index": 0,
            "content_hash": str(hash(content)),
        }
        self.vector_store.upsert_chunks(
            chunks=[
                {
                    "chunk_id": doc_id,
                    "text": content,
                    "metadata": metadata,
                }
            ]
        )
