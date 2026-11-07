"""Code evaluation metrics: pass@k and sandbox-based solution verification."""

from __future__ import annotations

import math


def pass_at_k(n: int, c: int, k: int) -> float:
    """Unbiased pass@k estimator.

    Args:
        n: Total number of samples generated per problem.
        c: Number of correct samples among the n samples.
        k: The k in pass@k (e.g., 1, 5, 10).

    Returns:
        Estimated probability that at least one of k samples is correct.
        Returns 1.0 if fewer than k incorrect candidates exist; pass@1 is c/n.
        Raises ValueError when k exceeds the actual number of candidates.
    """
    if n < 1 or not 0 <= c <= n or not 1 <= k <= n:
        raise ValueError("pass@k requires n >= k >= 1 and 0 <= c <= n")
    if c == 0:
        return 0.0
    if n - c < k:
        return 1.0

    total = math.comb(n, k)
    incorrect = math.comb(n - c, k)
    return 1.0 - incorrect / total


def evaluate_solution(code: str, test_cases: list[str], sandbox) -> bool:
    """Evaluate a generated code solution against test cases in a sandbox.

    Args:
        code: The generated code string.
        test_cases: List of Python assert statements (or test case strings).
        sandbox: A CodeSandbox instance for safe execution.

    Returns:
        True if all test cases pass, False otherwise.
    """
    if not test_cases:
        return False

    # Wrap test cases into a runnable script
    test_code = "\n".join(test_cases)
    full_code = f"{code}\n\n# --- Test cases ---\n{test_code}"

    result = sandbox.run(full_code)
    return result.success


def compute_pass_at_k_scores(
    results_per_problem: list[list[bool]],
    k_values: list[int] = (1, 5, 10),
) -> dict[int, float]:
    """Compute pass@k scores across all problems.

    Args:
        results_per_problem: For each problem, a list of bools indicating
            whether each sample (out of n) was correct.
        k_values: k values to compute pass@k for.

    Returns:
        Dict mapping k -> average pass@k score across all problems.
    """
    scores: dict[int, float] = {}

    for k in k_values:
        if results_per_problem and any(len(samples) < k for samples in results_per_problem):
            continue  # An unavailable pass@k must not be reported as a measured score.
        problem_scores = []
        for samples in results_per_problem:
            c = sum(samples)
            problem_scores.append(pass_at_k(len(samples), c, k))
        scores[k] = sum(problem_scores) / len(problem_scores) if problem_scores else 0.0

    return scores
