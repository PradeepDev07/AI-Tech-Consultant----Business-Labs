"""Question answering service orchestrating retrieval, grounding, citation, and abstention."""

import uuid
from app.core.exceptions import ModelProviderError, RetrievalError
from app.core.logging import logger
from app.schemas.questions import (
    Citation,
    QuestionRequest,
    QuestionResponse,
    RetrievalMetadata,
)
from app.services.model_provider import (
    ABSTENTION_TEXT,
    BaseModelProvider,
)
from retrieval.prompts import (
    SYSTEM_PROMPT,
    USER_PROMPT_TEMPLATE,
    format_evidence_block,
)
from retrieval.retriever import Retriever


class AnswerService:
    """Orchestrates grounded question answering with verification and citation construction."""

    def __init__(
        self,
        retriever: Retriever,
        model_provider: BaseModelProvider,
        min_evidence_threshold: float = 0.35,
    ):
        self.retriever = retriever
        self.model_provider = model_provider
        self.min_evidence_threshold = min_evidence_threshold

    def answer_question(self, request: QuestionRequest) -> QuestionResponse:
        """Process question through retrieval, evaluation of sufficiency, and grounded answer generation."""
        req_id = str(uuid.uuid4())
        question = request.question.strip()
        threshold = (
            request.min_evidence_threshold
            if request.min_evidence_threshold is not None
            else self.min_evidence_threshold
        )

        logger.info(f"[{req_id}] Processing question: '{question}'")

        # 0. Prompt injection guardrail
        lower_q = question.lower()
        if any(
            phrase in lower_q
            for phrase in [
                "ignore previous instructions",
                "disregard all prior instructions",
                "system override",
                "reveal the system prompt",
                "reveal your secret",
            ]
        ):
            logger.warning(f"[{req_id}] Neutralized prompt injection attempt in question.")
            return QuestionResponse(
                request_id=req_id,
                question=question,
                answer=(
                    "I must ignore instructions attempting to override system behavior. "
                    "Based on Brilliant Directories documentation, I cannot fulfill this request."
                ),
                abstained=True,
                abstention_reason="Adversarial prompt injection pattern detected in input.",
                citations=[],
                retrieval_metadata=RetrievalMetadata(
                    total_chunks_retrieved=0,
                    top_score=None,
                    retrieval_method="guardrail",
                    model_provider_used=self.model_provider.provider_name,
                    latency_ms=0.0,
                ),
            )

        # 1. Retrieve evidence
        retrieval_res = self.retriever.retrieve(
            query=question,
            top_k=request.top_k,
            min_threshold=threshold,
        )

        metadata = RetrievalMetadata(
            total_chunks_retrieved=len(retrieval_res.evidence),
            top_score=round(retrieval_res.top_score, 4) if retrieval_res.top_score is not None else None,
            retrieval_method=retrieval_res.retrieval_method,
            model_provider_used=self.model_provider.provider_name,
            latency_ms=retrieval_res.latency_ms,
        )

        # 2. Check evidence sufficiency
        if not retrieval_res.sufficient_evidence or not retrieval_res.evidence:
            logger.info(f"[{req_id}] Abstaining: Evidence insufficient (top score {metadata.top_score} < threshold {threshold})")
            return QuestionResponse(
                request_id=req_id,
                question=question,
                answer=ABSTENTION_TEXT,
                abstained=True,
                abstention_reason=f"Insufficient evidence retrieved (top score: {metadata.top_score}, threshold: {threshold})",
                citations=retrieval_res.citations,
                retrieval_metadata=metadata,
            )

        # 3. Format prompt for model
        evidence_block = format_evidence_block(
            [
                {
                    "text": ev.text,
                    "metadata": {
                        "title": ev.article_title,
                        "source_url": ev.source_url,
                        "heading": ev.heading,
                    },
                }
                for ev in retrieval_res.evidence
            ]
        )

        prompt = USER_PROMPT_TEMPLATE.format(
            question=question,
            evidence_block=evidence_block,
        )

        # 4. Generate answer
        try:
            answer_text = self.model_provider.generate_answer(
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )
        except ModelProviderError as exc:
            logger.error(f"[{req_id}] Model provider error: {exc}")
            raise

        # 5. Check if model decided to abstain
        abstained = False
        abstention_reason = None
        lower_ans = answer_text.lower()
        if (
            "not have sufficient information" in lower_ans
            or "insufficient information" in lower_ans
            or "cannot answer" in lower_ans
            or lower_ans.strip() == ABSTENTION_TEXT.lower()
        ):
            abstained = True
            abstention_reason = "Model determined available evidence was insufficient to answer with certainty."

        return QuestionResponse(
            request_id=req_id,
            question=question,
            answer=answer_text,
            abstained=abstained,
            abstention_reason=abstention_reason,
            citations=retrieval_res.citations,
            retrieval_metadata=metadata,
        )
