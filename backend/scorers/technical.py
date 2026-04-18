from backend.scorers.base import clamp, safe_float

class TechnicalScorer:
    def score(self, data: dict) -> float:
        close = safe_float(data.get("close"))
        ma5   = safe_float(data.get("ma5"))
        ma13  = safe_float(data.get("ma13"))
        ma30  = safe_float(data.get("ma30"))
        dif   = safe_float(data.get("macd_dif"))
        dea   = safe_float(data.get("macd_dea"))
        bar   = safe_float(data.get("macd_bar"))
        rsi   = safe_float(data.get("rsi14"))
        k     = safe_float(data.get("kdj_k"))
        d     = safe_float(data.get("kdj_d"))
        j     = safe_float(data.get("kdj_j"))
        bm    = safe_float(data.get("boll_mid"))
        bl    = safe_float(data.get("boll_lower"))
        vr    = safe_float(data.get("volume_ratio"))

        if all(v is None for v in [close, ma5, ma13, ma30, dif, rsi, k]):
            return 50.0

        total = 0
        # MA trend (30分)
        if None not in (close, ma5, ma13, ma30):
            if close > ma5:  total += 7
            if ma5 > ma13:   total += 8
            if ma13 > ma30:  total += 8
            if close > ma30: total += 7
        # MACD (25分)
        if None not in (dif, dea, bar):
            if dif > dea:            total += 10
            if bar > 0:              total += 10
            if bar > 0 and dif > 0:  total += 5
        # RSI (20分)
        if rsi is not None:
            if 50 <= rsi <= 70:   total += 20
            elif 40 <= rsi < 50:  total += 15
            elif 70 < rsi <= 80:  total += 10
            elif 30 <= rsi < 40:  total += 8
            else:                  total += 3
        # KDJ (15分)
        if None not in (k, d, j):
            if k > d:         total += 5
            if j > k:         total += 5
            if 20 <= k <= 80: total += 5
        # BOLL (10分)
        if None not in (close, bm, bl):
            if close > bm:   total += 10
            elif close > bl: total += 5
        # 量比 bonus
        if vr and vr >= 1.5:
            total = min(total + 5, 100)
        return float(clamp(total, 0, 100))
