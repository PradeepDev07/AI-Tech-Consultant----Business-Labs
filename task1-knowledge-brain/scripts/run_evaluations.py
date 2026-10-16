#!/usr/bin/env python3
"""CLI script to execute the 20 evaluation test cases and output benchmark metrics."""

import json
from pathlib import Path
import sys

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.logging import logger
from evaluation.runner import EvaluationRunner


import argparse
from app.services.model_provider import MockModelProvider, OllamaModelProvider


def main():
    parser = argparse.ArgumentParser(description="Task 1 Benchmark Evaluation Runner")
    parser.add_argument("--provider", default="mock", choices=["mock", "ollama"], help="Model provider (mock or ollama)")
    parser.add_argument("--model", default="gpt-oss:20b-cloud", help="Model identifier when using ollama")
    parser.add_argument("--url", default="http://localhost:11434", help="Ollama base URL")
    args = parser.parse_args()

    if args.provider == "ollama":
        logger.info(f"Using OllamaModelProvider with model='{args.model}' at {args.url}")
        provider = OllamaModelProvider(base_url=args.url, model=args.model)
    else:
        logger.info("Using deterministic MockModelProvider (zero cost)")
        provider = MockModelProvider()

    logger.info("Initializing Evaluation Suite...")
    runner = EvaluationRunner(model_provider=provider)
    summary = runner.run_all()

    print("\n" + "=" * 90)
    print(f"       TASK 1: KNOWLEDGE BRAIN EVALUATION REPORT [{provider.provider_name}]")
    print("=" * 90)
    print(f"{'Case ID':<9} | {'Category':<24} | {'Abstain?':<8} | {'Ans OK?':<7} | {'Prec.':<6} | {'Rec.':<6} | {'Lat(ms)'}")
    print("-" * 90)

    for r in summary.case_results:
        abst_str = "YES" if r.abstained else "NO"
        abst_ok = "✓" if r.abstention_correct else "✗"
        ans_ok = "✓" if r.answer_correct else "✗"
        print(
            f"{r.case_id:<9} | {r.category[:24]:<24} | {abst_str} ({abst_ok})   | {ans_ok:<7} | {r.citation_precision:<6.2f} | {r.citation_recall:<6.2f} | {r.latency_ms}ms"
        )

    print("=" * 90)
    print("OVERALL SUMMARY METRICS:")
    print(f"Total Test Cases Evaluated:   {summary.total_cases}")
    print(f"Abstention Accuracy:          {summary.abstention_accuracy}% ({summary.passed_abstention_cases}/{summary.total_cases})")
    print(f"Answer Correctness Accuracy:  {summary.answer_accuracy}% ({summary.passed_answer_cases}/{summary.total_cases})")
    print(f"Mean Citation Precision:      {summary.mean_citation_precision:.4f}")
    print(f"Mean Citation Recall:         {summary.mean_citation_recall:.4f}")
    print(f"Mean Request Latency:         {summary.mean_latency_ms:.2f} ms")
    print(f"Model Provider Used:          {provider.provider_name}")
    if runner.telemetry_summary["total_prompt_tokens"] > 0:
        print(f"Total Prompt Tokens:          {runner.telemetry_summary['total_prompt_tokens']}")
        print(f"Total Completion Tokens:      {runner.telemetry_summary['total_eval_tokens']}")
        print(f"Total Model Time:             {runner.telemetry_summary['total_duration_ms']:.2f} ms")
    print(f"Model Cost:                   {summary.model_cost}")
    print("=" * 90 + "\n")

    # Persist results to storage
    out_path = Path(__file__).parent.parent / "storage" / "evaluation_results.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(
            {
                "total_cases": summary.total_cases,
                "abstention_accuracy": summary.abstention_accuracy,
                "answer_accuracy": summary.answer_accuracy,
                "mean_citation_precision": summary.mean_citation_precision,
                "mean_citation_recall": summary.mean_citation_recall,
                "mean_latency_ms": summary.mean_latency_ms,
                "model_cost": summary.model_cost,
                "case_results": [
                    {
                        "case_id": r.case_id,
                        "category": r.category,
                        "question": r.question,
                        "abstained": r.abstained,
                        "should_abstain": r.should_abstain,
                        "abstention_correct": r.abstention_correct,
                        "answer_correct": r.answer_correct,
                        "citation_precision": r.citation_precision,
                        "citation_recall": r.citation_recall,
                        "latency_ms": r.latency_ms,
                    }
                    for r in summary.case_results
                ],
            },
            f,
            indent=2,
        )
    logger.info(f"Evaluation results successfully saved to {out_path}")


if __name__ == "__main__":
    main()
