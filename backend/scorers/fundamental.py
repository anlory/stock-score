from backend.scorers.base import percentile_score, clamp, safe_float

class FundamentalScorer:
    def score(self, data: dict, universe_stats: dict) -> float:
        total = 0.0
        pe = safe_float(data.get("pe"))
        valid_pe = [v for v in universe_stats.get("pe", []) if v and v > 0]
        if pe and pe > 0:
            total += percentile_score(pe, valid_pe, higher_is_better=False) * 0.25
        pb = safe_float(data.get("pb"))
        valid_pb = [v for v in universe_stats.get("pb", []) if v and v > 0]
        if pb and pb > 0:
            total += percentile_score(pb, valid_pb, higher_is_better=False) * 0.20
        roe = safe_float(data.get("roe"))
        total += percentile_score(roe, universe_stats.get("roe", []), True) * 0.30
        growth = safe_float(data.get("profit_growth_yoy"))
        total += percentile_score(growth, universe_stats.get("profit_growth_yoy", []), True) * 0.25
        return float(clamp(total, 0, 100))
