import json
import logging
from datetime import date as _date
from sqlalchemy.orm import Session
from backend.models import Stock, DailyData
from backend.database import upsert
from backend.collectors.tencent_kline import fetch_kline

logger = logging.getLogger(__name__)


def _compute_returns(closes: list[float]) -> dict:
    """Given chronological closes (oldest first), compute 5/20/60-day pct changes."""
    out = {"return_5d": None, "return_20d": None, "return_60d": None}
    if not closes:
        return out
    today = closes[-1]
    for window, key in [(5, "return_5d"), (20, "return_20d"), (60, "return_60d")]:
        if len(closes) > window:
            past = closes[-window - 1]
            if past:
                out[key] = round((today - past) / past * 100, 2)
    return out


def _detect_patterns(d: dict, prev_macd_dif, prev_macd_dea) -> list[str]:
    tags = []
    ma5, ma13 = d.get("ma5"), d.get("ma13")
    pma5, pma13 = d.get("prev_ma5"), d.get("prev_ma13")
    if None not in (ma5, ma13, pma5, pma13):
        if ma5 > ma13 and pma5 < pma13:
            tags.append("MA5上穿MA13")
        elif ma5 < ma13 and pma5 > pma13:
            tags.append("MA5下穿MA13")
    vr, chg = d.get("volume_ratio"), d.get("change_pct")
    if vr is not None and chg is not None and vr > 2 and chg > 3:
        tags.append("放量上攻")
    dif, dea = d.get("macd_dif"), d.get("macd_dea")
    if None not in (dif, dea, prev_macd_dif, prev_macd_dea):
        if dif > dea and prev_macd_dif <= prev_macd_dea:
            tags.append("MACD金叉")
    return tags


def _fetch_industry_changes(industry: str) -> dict:
    """Return {change, change_5d, change_20d} for the given industry board."""
    if not industry:
        return {"change": None, "change_5d": None, "change_20d": None}
    try:
        import akshare as ak
        df = ak.stock_board_industry_hist_em(symbol=industry, period="daily", adjust="")
        if df is None or df.empty or len(df) < 2:
            return {"change": None, "change_5d": None, "change_20d": None}
        closes = df["收盘"].astype(float).tolist() if "收盘" in df.columns else []
        if not closes:
            return {"change": None, "change_5d": None, "change_20d": None}
        today = closes[-1]
        def _chg(n):
            return round((today - closes[-n-1]) / closes[-n-1] * 100, 2) if len(closes) > n and closes[-n-1] else None
        return {"change": _chg(1), "change_5d": _chg(5), "change_20d": _chg(20)}
    except Exception as e:
        logger.warning(f"industry hist failed for {industry}: {e}")
        return {"change": None, "change_5d": None, "change_20d": None}


def _prev_macd(session: Session, code: str, today: str) -> tuple:
    """Fetch yesterday's DailyData macd_dif/dea for MACD cross detection."""
    row = (
        session.query(DailyData)
        .filter(DailyData.code == code, DailyData.date < today)
        .order_by(DailyData.date.desc())
        .first()
    )
    if not row:
        return (None, None)
    return (row.macd_dif, row.macd_dea)


def collect_trend(session: Session, target_codes: set[str], today: str | None = None) -> int:
    """Populate trend fields on DailyData for the given codes. Returns count written."""
    today = today or _date.today().isoformat()
    stocks = {s.code: s for s in session.query(Stock).filter(Stock.code.in_(target_codes))}
    industry_cache: dict[str, dict] = {}
    count = 0

    for code in target_codes:
        stock = stocks.get(code)
        daily = session.query(DailyData).filter_by(code=code, date=today).first()
        if not daily:
            continue

        # Returns
        try:
            kline = fetch_kline(code, days=65)
            closes = [float(row["close"]) for row in kline]
        except Exception as e:
            logger.warning(f"kline failed for {code}: {e}")
            closes = []
        returns = _compute_returns(closes)

        # Industry
        industry = stock.industry if stock else None
        if industry:
            if industry not in industry_cache:
                industry_cache[industry] = _fetch_industry_changes(industry)
            ichanges = industry_cache[industry]
        else:
            ichanges = {"change": None, "change_5d": None, "change_20d": None}

        # Patterns
        prev_dif, prev_dea = _prev_macd(session, code, today)
        tags = _detect_patterns(daily.__dict__, prev_dif, prev_dea)

        upsert(session, DailyData, {
            "code": code, "date": today,
            **returns,
            "industry_change": ichanges["change"],
            "industry_change_5d": ichanges["change_5d"],
            "industry_change_20d": ichanges["change_20d"],
            "pattern_tags": json.dumps(tags, ensure_ascii=False),
        }, ["code", "date"])
        count += 1

    session.commit()
    logger.info(f"Trend data collected: {count} stocks")
    return count
