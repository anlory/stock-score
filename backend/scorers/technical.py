from backend.scorers.base import safe_float


class TechnicalScorer:
    def score(self, data: dict) -> float:
        close = safe_float(data.get("close"))
        ma5 = safe_float(data.get("ma5"))
        ma13 = safe_float(data.get("ma13"))
        ma30 = safe_float(data.get("ma30"))
        p_ma5 = safe_float(data.get("prev_ma5"))
        p_ma13 = safe_float(data.get("prev_ma13"))
        p_ma30 = safe_float(data.get("prev_ma30"))

        return_3d = safe_float(data.get("return_3d"))
        return_5d = safe_float(data.get("return_5d"))
        return_13d = safe_float(data.get("return_13d"))
        return_mid = safe_float(data.get("return_mid"))
        ma5_slope3 = safe_float(data.get("ma5_slope3"))
        is_10d_high = safe_float(data.get("is_10d_high"))
        is_30d_high = safe_float(data.get("is_30d_high"))

        vol_ma3 = safe_float(data.get("vol_ma3"))
        vol_ma5 = safe_float(data.get("vol_ma5"))
        vol_ma13 = safe_float(data.get("vol_ma13"))
        vol_ma30 = safe_float(data.get("vol_ma30"))
        close_above_ma5_5d = safe_float(data.get("close_above_ma5_5d"))
        last_close_above_ma5 = safe_float(data.get("last_close_above_ma5"))

        total = 0.0

        # ── 1. 价格动量 (45分) ──
        total += self._price_momentum(return_3d, return_13d, return_mid, ma5_slope3, is_10d_high)

        # ── 2. 量能配合 (30分) ──
        total += self._volume_coordination(return_5d, vol_ma3, vol_ma5, vol_ma13, vol_ma30)

        # ── 3. 趋势结构 (15分) ──
        total += self._trend_structure(close, ma5, ma13, ma30, p_ma5, p_ma13, p_ma30, is_30d_high)

        # ── 4. 趋势健康度 (10分) ──
        total += self._trend_health(close, ma5, ma13, is_30d_high, close_above_ma5_5d, last_close_above_ma5)

        return round(min(max(total, 0), 100), 2)

    # ── 价格动力 45 ──────────────────────────────────────
    def _price_momentum(self, r3, r13, r_mid, slope3, is_10h) -> float:
        s = 0.0
        # 短期爆发力 (18): 13日涨幅 > 12% → 满, 线性插值
        if r13 is not None:
            if r13 >= 12:
                s += 18
            elif r13 > 0:
                s += r13 / 12 * 18
        # 中期趋势 (9): 25日涨幅(剔除近5日) > 20% → 满
        if r_mid is not None:
            if r_mid >= 20:
                s += 9
            elif r_mid > 0:
                s += r_mid / 20 * 9
        # 启动加速度 (9): (3日涨幅 + 2%) > 13日涨幅 → 满
        if r3 is not None and r13 is not None:
            if (r3 + 2) > r13:
                s += 9
        # MA5斜率转向 (9): slope > 0 且 创10日新高
        if slope3 is not None and slope3 > 0 and is_10h == 1:
            s += 9
        return s

    # ── 量能协调 30 ──────────────────────────────────────
    def _volume_coordination(self, r5, v3, v5, v13, v30) -> float:
        s = 0.0
        # 攻击放量 (20): vol5/vol13 > 2.0 → 20, > 1.5 → 10, 线性
        if v5 and v13 and v13 > 0:
            ratio = v5 / v13
            if ratio >= 2.0:
                s += 20
            elif ratio >= 1.5:
                s += 10
            elif ratio > 1.0:
                s += (ratio - 1.0) / 0.5 * 10
        # 回踩缩量 (5): vol3/vol30 < 0.5 → 5
        if v3 and v30 and v30 > 0:
            if v3 / v30 < 0.5:
                s += 5
        # 量价同步 (5): 5日涨幅>0 且 vol5 > vol13
        if r5 is not None and r5 > 0 and v5 and v13 and v5 > v13:
            s += 5
        return s

    # ── 趋势结构 15 ──────────────────────────────────────
    def _trend_structure(self, c, m5, m13, m30, pm5, pm13, pm30, is_30h) -> float:
        s = 0.0
        # 均线排列 (10)
        if None not in (m5, m13, m30):
            full_align = m5 > m13 > m30
            if full_align:
                # 三线向上发散
                if None not in (pm5, pm13, pm30):
                    if m5 > pm5 and m13 > pm13 and m30 > pm30:
                        s += 10
                    else:
                        s += 7  # 排列但未全发散
                else:
                    s += 7
            elif m5 > m13:
                s += 5
            # else: MA5 <= MA13 → 0
        # 阶段新高 (5)
        if is_30h == 1:
            s += 5
        return s

    # ── 趋势健康度 10 (双通道取高分) ──────────────────────
    def _trend_health(self, c, m5, m13, is_30h, above5_count, last_above5) -> float:
        ch_a = 0.0
        ch_b = 0.0
        # 通道A: 回踩再起
        if c and m13 and m13 > 0:
            pct = (c - m13) / m13 * 100
            if abs(pct) <= 3:
                ch_a += 6
        if last_above5 == 1:
            ch_a += 4
        # 通道B: 强势不破
        if above5_count is not None and above5_count >= 5:
            ch_b += 5
        if is_30h == 1:
            ch_b += 5
        return max(ch_a, ch_b)
