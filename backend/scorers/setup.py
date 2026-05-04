import json
from backend.scorers.base import safe_float, clamp, percentile_score


class SetupScorer:
    """Self-contained 100-point scorer for bottom/setup phase stocks.
    Setup signals 55 + Setup capital 30 + Setup heat 15."""

    def score(self, data: dict, universe_stats: dict = None) -> float:
        total = 0.0
        total += self._bottom_shrink_volume(data)
        total += self._mild_volume_expansion(data)
        total += self._ma_convergence(data)
        total += self._golden_crosses(data)
        total += self._sufficient_decline(data)
        total += self._ma5_slope_turn(data)
        total += self._rsi_recovery(data)
        total += self._setup_capital(data, universe_stats or {})
        total += self._setup_heat(data)
        return round(float(clamp(total, 0, 100)), 2)

    # ── 底部缩量 11 ──────────────────────────────────────
    def _bottom_shrink_volume(self, data: dict) -> float:
        v3 = safe_float(data.get("vol_ma3"))
        v30 = safe_float(data.get("vol_ma30"))
        if v3 is None or v30 is None or v30 <= 0:
            return 0.0
        ratio = v3 / v30
        if ratio < 0.4:
            return 11.0
        if ratio < 0.6:
            return 8.0
        if ratio < 0.8:
            return 4.0
        return 0.0

    # ── 温和放量 8 ────────────────────────────────────────
    def _mild_volume_expansion(self, data: dict) -> float:
        v5 = safe_float(data.get("vol_ma5"))
        v13 = safe_float(data.get("vol_ma13"))
        if v5 is None or v13 is None or v13 <= 0:
            return 0.0
        ratio = v5 / v13
        if 1.0 <= ratio <= 1.8:
            return 8.0
        if 0.8 <= ratio < 1.0:
            return 4.0
        return 0.0

    # ── 均线收敛 8 ────────────────────────────────────────
    def _ma_convergence(self, data: dict) -> float:
        m5 = safe_float(data.get("ma5"))
        m13 = safe_float(data.get("ma13"))
        m30 = safe_float(data.get("ma30"))
        if None in (m5, m13, m30) or m30 <= 0:
            return 0.0
        hi = max(m5, m13, m30)
        lo = min(m5, m13, m30)
        spread = (hi - lo) / lo * 100
        if spread < 3:
            return 8.0
        if spread < 5:
            return 5.0
        if spread < 8:
            return 3.0
        return 0.0

    # ── 金叉信号 11 (MA5上穿MA13 6 + MACD金叉 5) ────────
    def _golden_crosses(self, data: dict) -> float:
        tags_raw = data.get("pattern_tags", "[]")
        try:
            tags = json.loads(tags_raw) if isinstance(tags_raw, str) else []
        except (json.JSONDecodeError, TypeError):
            tags = []
        s = 0.0
        if "MA5上穿MA13" in tags:
            s += 6.0
        if "MACD金叉" in tags:
            s += 5.0
        return s

    # ── 跌幅充分 6 ────────────────────────────────────────
    def _sufficient_decline(self, data: dict) -> float:
        r60 = safe_float(data.get("return_60d"))
        r20 = safe_float(data.get("return_20d"))
        worst = min(
            r60 if r60 is not None else 0,
            r20 if r20 is not None else 0,
        )
        if worst < -15:
            return 6.0
        if worst < -10:
            return 5.0
        if worst < -5:
            return 3.0
        if worst < 0:
            return 1.0
        return 0.0

    # ── MA5斜率转正 + 站上MA5 8 ─────────────────────────
    def _ma5_slope_turn(self, data: dict) -> float:
        s = 0.0
        slope = safe_float(data.get("ma5_slope3"))
        if slope is not None and slope > 0:
            s += min(slope / 2.0 * 5.5, 5.5)
        above = safe_float(data.get("last_close_above_ma5"))
        if above == 1:
            s += 2.5
        return s

    # ── RSI低位回升 3 ────────────────────────────────────
    def _rsi_recovery(self, data: dict) -> float:
        rsi = safe_float(data.get("rsi14"))
        if rsi is None:
            return 0.0
        if 30 <= rsi <= 45:
            return 3.0
        if 45 < rsi <= 55:
            return 1.5
        return 0.0

    # ── 资金面(埋伏版) 30 ────────────────────────────────
    def _setup_capital(self, data: dict, stats: dict) -> float:
        s = 0.0
        # 温和净流入 15: >0 且不超过75分位 → 满分
        today_in = safe_float(data.get("main_inflow_today"))
        inflow_list = stats.get("main_inflow_today", [])
        if today_in is not None and today_in > 0:
            p75 = _p75(inflow_list) if inflow_list else float("inf")
            if today_in <= p75:
                s += 15.0
            elif p75 > 0:
                s += max(0, 15.0 * (1 - (today_in - p75) / p75))
        # 持续流入 10: 5日净流入 > 0
        inflow_5d = safe_float(data.get("main_inflow_5d"))
        inflow_5d_list = stats.get("main_inflow_5d", [])
        if inflow_5d is not None and inflow_5d > 0:
            pct = percentile_score(inflow_5d, inflow_5d_list, True)
            s += pct / 100.0 * 10.0
        # 超大单不流出 5
        sl = safe_float(data.get("super_large_inflow"))
        if sl is not None and sl >= 0:
            s += 5.0
        return s

    # ── 热度面(埋伏版) 15 ────────────────────────────────
    def _setup_heat(self, data: dict) -> float:
        s = 0.0
        # 低换手 8: 越低越好
        turnover = safe_float(data.get("turnover_rate"))
        if turnover is not None:
            if turnover < 1:
                s += 8.0
            elif turnover < 3:
                s += 5.0
            elif turnover < 5:
                s += 2.0
        # 低振幅 4
        change = safe_float(data.get("change_pct"))
        if change is not None:
            if abs(change) < 1:
                s += 4.0
            elif abs(change) < 2:
                s += 2.0
            elif abs(change) < 3:
                s += 1.0
        # 量比适中 3: 不追高量
        vr = safe_float(data.get("volume_ratio"))
        if vr is not None:
            if vr < 1.0:
                s += 3.0
            elif vr < 1.5:
                s += 2.0
            elif vr < 2.0:
                s += 1.0
        return s


def _p75(values: list) -> float:
    if not values:
        return float("inf")
    sorted_v = sorted(values)
    idx = int(len(sorted_v) * 0.75)
    return sorted_v[min(idx, len(sorted_v) - 1)]
