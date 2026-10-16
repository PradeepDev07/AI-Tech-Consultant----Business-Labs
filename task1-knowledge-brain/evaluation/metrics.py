"""Evaluation metric computation for grounded RAG accuracy."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CaseEvaluationResult:
    """Outcome of evaluating a single test case."""

    case_id: str
    category: str
    question: str
    abstained: bool
    should_abstain: bool
    abstention_correct: bool
    answer_correct: bool
    citation_precision: float
    citation_recall: float
    latency_ms: float
    error: str | None = None


@dataclass
class EvaluationSummary:
    """Aggregated evaluation metrics across all test cases."""

    total_cases: int = 0
    passed_abstention_cases: int = 0
    passed_answer_cases: int = 0
    abstention_accuracy: float = 0.0
    answer_accuracy: float = 0.0
    mean_citation_precision: float = 0.0
    mean_citation_recall: float = 0.0
    mean_latency_ms: float = 0.0
    model_cost: str = "$0.00 (Offline deterministic test execution)"
    case_results: list[CaseEvaluationResult] = field(default_factory=list)


def evaluate_case(case: dict[str, Any], response: Any) -> CaseEvaluationResult:
    """Evaluate a single test case response against expected outcomes."""
    case_id = case["id"]
    category = case["category"]
    question = case["question"]
    should_abstain = case.get("should_abstain", False)

    abstained = bool(getattr(response, "abstained", False))
    answer_text = str(getattr(response, "answer", "")).lower()
    citations = getattr(response, "citations", [])
    latency_ms = float(getattr(getattr(response, "retrieval_metadata", None), "latency_ms", 0.0))

    # 1. Abstention correctness
    abstention_correct = (abstained == should_abstain)

    # 2. Answer correctness
    expected_keywords = [k.lower() for k in case.get("expected_answer_keywords", [])]
    if should_abstain:
        answer_correct = abstention_correct
    else:
        if abstained or not expected_keywords:
            answer_correct = False
        else:
            matches = sum(1 for kw in expected_keywords if kw in answer_text)
            answer_correct = (matches >= max(1, len(expected_keywords) // 2))

    # 3. Citation metrics
    expected_citations = case.get("expected_citations", [])
    actual_citation_urls = [c.source_url for c in citations]

    if not expected_citations:
        citation_precision = 1.0 if not actual_citation_urls or should_abstain else 0.5
        citation_recall = 1.0
    else:
        tp = 0
        for exp in expected_citations:
            if any(exp in act for act in actual_citation_urls):
                tp += 1
        citation_recall = tp / len(expected_citations)
        citation_precision = tp / len(actual_citation_urls) if actual_citation_urls else 0.0

    return CaseEvaluationResult(
        case_id=case_id,
        category=category,
        question=question,
        abstained=abstained,
        should_abstain=should_abstain,
        abstention_correct=abstention_correct,
        answer_correct=answer_correct,
        citation_precision=round(citation_precision, 4),
        citation_recall=round(citation_recall, 4),
        latency_ms=round(latency_ms, 2),
    )


def summarize_results(case_results: list[CaseEvaluationResult]) -> EvaluationSummary:
    """Aggregate individual case results into an overall summary."""
    total = len(case_results)
    if total == 0:
        return EvaluationSummary()

    passed_abstention = sum(1 for r in case_results if r.abstention_correct)
    passed_answer = sum(1 for r in case_results if r.answer_correct)
    mean_prec = sum(r.citation_precision for r in case_results) / total
    mean_rec = sum(r.citation_recall for r in case_results) / total
    mean_lat = sum(r.latency_ms for r in case_results) / total

    return EvaluationSummary(
        total_cases=total,
        passed_abstention_cases=passed_abstention,
        passed_answer_cases=passed_answer,
        abstention_accuracy=round((passed_abstention / total) * 100.0, 2),
        answer_accuracy=round((passed_answer / total) * 100.0, 2),
        mean_citation_precision=round(mean_prec, 4),
        mean_citation_recall=round(mean_rec, 4),
        mean_latency_ms=round(mean_lat, 2),
        model_cost="$0.00 (Offline deterministic test execution)",
        case_results=case_results,
    )
