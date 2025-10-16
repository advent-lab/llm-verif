"""
Evaluation metrics for test bench generation.

Contains statistical functions for evaluating the quality and performance
of generated test benches, including pass@k metrics.
"""

from typing import List, Union
import itertools
import numpy as np


def estimate_pass_at_k(
    num_samples: Union[int, List[int], np.ndarray],
    num_correct: Union[List[int], np.ndarray],
    k: int
) -> np.ndarray:
    """
    Estimates pass@k of each run and returns them in an array.

    The pass@k metric estimates the probability that at least one of k
    randomly sampled solutions passes, given n total samples with c correct ones.

    Args:
        num_samples: Number of samples generated (can be int or array).
        num_correct: Number of correct samples (array-like).
        k: Number of samples to consider for the pass@k metric.

    Returns:
        np.ndarray: Array of pass@k estimates for each run.

    Raises:
        AssertionError: If lengths of num_samples and num_correct don't match.

    Examples:
        >>> estimate_pass_at_k(10, [5, 6, 7], k=3)
        array([0.833, 0.917, 0.975])
    """
    # Determine the type of passed arguments
    # Raise error if lengths do not agree
    if isinstance(num_samples, int):
        num_samples_it = itertools.repeat(num_samples, len(num_correct))
    else:
        assert len(num_samples) == len(num_correct), \
            f"Length mismatch: num_samples ({len(num_samples)}) != num_correct ({len(num_correct)})"
        num_samples_it = iter(num_samples)

    # Return the estimations
    return np.array([pass_at_k(int(n), int(c), k) for n, c in zip(num_samples_it, num_correct)])


def pass_at_k(n: int, c: int, k: int) -> float:
    """
    Calculates the pass@k metric: 1 - comb(n - c, k) / comb(n, k).

    This function computes the probability that at least one correct solution
    appears when randomly sampling k items from n total items, where c are correct.

    The formula avoids direct computation of binomial coefficients for numerical stability.

    Args:
        n: Total number of samples.
        c: Number of correct samples.
        k: Number of samples to draw.

    Returns:
        float: The pass@k probability (between 0.0 and 1.0).

    Examples:
        >>> pass_at_k(10, 5, 3)
        0.8333333333333334
        >>> pass_at_k(10, 10, 1)
        1.0
        >>> pass_at_k(10, 0, 5)
        0.0
    """
    if n - c < k:
        return 1.0
    return 1.0 - float(np.prod(1.0 - k / np.arange(n - c + 1, n + 1)))
