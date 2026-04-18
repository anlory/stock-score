from backend.scorers.base import clamp, safe_float

class HeatScorer:
    def score(self, data: dict, universe_stats: dict) -> float:
        total = 0.0
        change = safe_float(data.get("change_pct"))
        if change is not None:
            if 3 <= change <= 7:   total += 30
            elif 1 <= change < 3:  total += 20
            elif 7 < change <= 9:  total += 20
            elif change > 9:       total += 15
            elif 0 <= change < 1:  total += 10
            elif -3 <= change < 0: total += 5
        turnover = safe_float(data.get("turnover_rate"))
        if turnover is not None:
            if 3 <= turnover <= 10: total += 25
            elif 1 <= turnover < 3: total += 15
            elif turnover > 10:     total += 15
            else:                   total += 5
        vr = safe_float(data.get("volume_ratio"))
        if vr is not None:
            if vr >= 2.0:   total += 15
            elif vr >= 1.5: total += 12
            elif vr >= 1.0: total += 8
            else:           total += 3
        limit_up = data.get("consecutive_limit_up") or 0
        if limit_up >= 3:   total += 20
        elif limit_up == 2: total += 15
        elif limit_up == 1: total += 10
        rank = data.get("sector_heat_rank")
        if rank is not None:
            if rank <= 3:    total += 10
            elif rank <= 10: total += 7
            elif rank <= 30: total += 4
        return float(clamp(total, 0, 100))
