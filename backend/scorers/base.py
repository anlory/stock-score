def clamp(value: float, min_val: float, max_val: float) -> float:
    return max(min_val, min(max_val, value))

def percentile_score(value, all_values: list, higher_is_better: bool = True) -> int:
    valid = [v for v in all_values if v is not None]
    if not valid or value is None:
        return 50
    below = sum(1 for v in valid if v < value)
    equal = sum(1 for v in valid if v == value)
    rank = (below + equal * 0.5) / len(valid)
    score = rank if higher_is_better else (1 - rank)
    return round(clamp(score * 100, 0, 100))

def safe_float(value, default=None):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
