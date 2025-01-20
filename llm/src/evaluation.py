"""
Put citation here
"""


from collections import defaultdict, Counter
from typing import List, Union, Iterable, Dict
import itertools
import numpy as np

def estimate_pass_at_k(
        num_samples: Union[int, List[int], np.ndarray],
        num_correct: Union[int, List[int], np.ndarray],
        k: int
) -> np.ndarray:
    """
    Estimates pass@k of each run and returns them in an arry
    """
    
    # Determine the type of passed arguments
    # Raise error if lengths to not agree
    if isinstance(num_samples, int):
        num_samples_it = itertools.repeat(num_samples, len(num_correct))
    else:
        assert len(num_samples) == len(num_correct)
        num_samples_it = iter(num_samples)

    # Return the estimations
    return np.array([pass_at_k(int(n), int(c), k) for n, c in zip(num_samples_it, num_correct)])

def pass_at_k(n: int, c: int, k: int) -> float:
    """
    Calculates 1 - comb(n - c, k) / comb(n,k)
    """
    if n - c < k:
        return 1.0
    return 1.0 - np.prod(1.0 - k / np.arange(n - c + 1, n + 1))
