"""Integration test verifying evaluation runner executes the 20 benchmark test cases."""

from evaluation.runner import EvaluationRunner


def test_evaluation_runner_benchmark():
    """Verify that all 20 evaluation cases execute successfully with high accuracy."""
    runner = EvaluationRunner()
    summary = runner.run_all()

    assert summary.total_cases == 20
    assert summary.abstention_accuracy >= 95.0
    assert summary.answer_accuracy >= 95.0
    assert summary.mean_citation_recall >= 0.90
    assert len(summary.case_results) == 20
