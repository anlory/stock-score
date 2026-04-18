from backend.scorers.base import percentile_score, clamp, safe_float

class CapitalScorer:
    def score(self, data: dict, universe_stats: dict) -> float:
        total = 0.0
        v = safe_float(data.get("main_inflow_today"))
        total += percentile_score(v, universe_stats.get("main_inflow_today", []), True) * 0.40
        v = safe_float(data.get("main_inflow_5d"))
        total += percentile_score(v, universe_stats.get("main_inflow_5d", []), True) * 0.30
        v = safe_float(data.get("super_large_inflow"))
        total += percentile_score(v, universe_stats.get("super_large_inflow", []), True) * 0.15
        north = safe_float(data.get("north_inflow"))
        total += 10.0 if (north is not None and north > 0) else 0.0
        margin = safe_float(data.get("margin_net_buy"))
        total += 5.0 if (margin is not None and margin > 0) else 0.0
        return float(clamp(total, 0, 100))
