import numpy as np

def volume_weighted_average(current_losses: np.ndarray, next_losses: np.ndarray) -> float:
    """
    Volume weighted average: Sum(next_losses) / Sum(current_losses)
    """
    current_losses = np.array(current_losses, dtype=float)
    next_losses = np.array(next_losses, dtype=float)
    mask = ~np.isnan(current_losses) & ~np.isnan(next_losses) & (current_losses > 0)
    cur = current_losses[mask]
    nxt = next_losses[mask]
    if len(cur) == 0:
        return 1.0
    return float(np.sum(nxt) / np.sum(cur))

def simple_average(factors: np.ndarray) -> float:
    """
    Simple (straight) average of LDF factors.
    """
    factors = np.array(factors, dtype=float)
    mask = ~np.isnan(factors) & ~np.isinf(factors)
    valid = factors[mask]
    if len(valid) == 0:
        return 1.0
    return float(np.mean(valid))

def geometric_average(factors: np.ndarray) -> float:
    """
    Geometric average of LDF factors.
    """
    factors = np.array(factors, dtype=float)
    mask = ~np.isnan(factors) & ~np.isinf(factors) & (factors > 0)
    valid = factors[mask]
    if len(valid) == 0:
        return 1.0
    return float(np.prod(valid) ** (1.0 / len(valid)))

def medial_average(factors: np.ndarray) -> float:
    """
    Medial average of LDF factors (excludes highest and lowest value, then averages).
    """
    factors = np.array(factors, dtype=float)
    mask = ~np.isnan(factors) & ~np.isinf(factors)
    valid = factors[mask]
    n = len(valid)
    if n == 0:
        return 1.0
    elif n <= 2:
        return float(np.mean(valid))
    else:
        sorted_factors = np.sort(valid)
        return float(np.mean(sorted_factors[1:-1]))
