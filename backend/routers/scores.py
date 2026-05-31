import json as _json
from datetime import date, timedelta
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from backend.database import get_session
from backend.models import Score, Stock, DailyData

router = APIRouter(prefix="/api/scores", tags=["scores"])

_A_SHARE_MARKETS = {"SH", "SZ", "BJ"}


def _latest_date(session):
    row = session.query(Score).order_by(Score.date.desc()).first()
    return row.date if row else date.today().isoformat()


@router.get("/leaderboard")
def get_leaderboard(
    type: str = Query("other"),
    strategy: str = Query("short_term"),
    market: str = Query(None),
    session: Session = Depends(get_session),
):
    latest = _latest_date(session)

    score_maps: dict[str, dict[str, Score]] = {}
    for strat in ("short_term", "trend", "setup"):
        score_maps[strat] = {
            s.code: s
            for s in session.query(Score).filter(Score.date == latest, Score.strategy == strat)
        }

    all_codes: set[str] = set()
    for m in score_maps.values():
        all_codes.update(m.keys())

    stocks = {s.code: s for s in session.query(Stock).filter(Stock.code.in_(all_codes))}
    all_codes = {c for c in all_codes if c in stocks}
    if type == "watchlist":
        all_codes = {c for c in all_codes if stocks[c].is_watchlist}

    # Filter by market if specified
    if market:
        all_codes = {c for c in all_codes if stocks[c].market == market}

    primary = score_maps.get(strategy, {})
    ranked = sorted(all_codes, key=lambda c: primary[c].total_score if c in primary else 0, reverse=True)[:200]

    return {
        "date": latest,
        "stocks": [
        {
            "rank": i + 1, "code": c, "name": stocks[c].name if c in stocks else c,
            "is_watchlist": stocks[c].is_watchlist if c in stocks else False,
            "total_score": primary[c].total_score if c in primary else None,
            "technical_score": primary[c].technical_score if c in primary else None,
            "capital_score": primary[c].capital_score if c in primary else None,
            "heat_score": primary[c].heat_score if c in primary else None,
            "setup_score": primary[c].setup_score if c in primary else None,
            "market": stocks[c].market if c in stocks else None,
            "industry": stocks[c].industry if c in stocks else None,
        }
        for i, c in enumerate(ranked)
        ]
    }

def _score_dict(s):
    return {
        "total": s.total_score,
        "technical": s.technical_score,
        "capital": s.capital_score,
        "fundamental": s.fundamental_score,
        "news": s.news_score,
        "heat": s.heat_score,
    }

@router.get("/{code}")
def get_stock_detail(code: str, session: Session = Depends(get_session)):
    latest = _latest_date(session)

    # Try code as-is first, then zfill(6) for digit codes
    stock = session.get(Stock, code)
    if stock:
        lookup_code = code
    elif code.isdigit():
        lookup_code = code.zfill(6)
        stock = session.get(Stock, lookup_code)
    else:
        lookup_code = code

    daily = session.query(DailyData).filter(
        DailyData.code == lookup_code, DailyData.date == latest
    ).first()
    short = session.query(Score).filter(
        Score.code == lookup_code, Score.date == latest, Score.strategy == "short_term"
    ).first()
    trend = session.query(Score).filter(
        Score.code == lookup_code, Score.date == latest, Score.strategy == "trend"
    ).first()
    setup = session.query(Score).filter(
        Score.code == lookup_code, Score.date == latest, Score.strategy == "setup"
    ).first()
    if not short and not trend and not setup:
        return {"error": "暂无评分数据"}

    trend_info = None
    if daily:
        try:
            pattern_tags = _json.loads(daily.pattern_tags or "[]")
        except (ValueError, TypeError):
            pattern_tags = []
        trend_info = {
            "return_5d": daily.return_5d,
            "return_20d": daily.return_20d,
            "return_60d": daily.return_60d,
            "pattern_tags": pattern_tags,
        }

    return {
        "code": lookup_code,
        "name": stock.name if stock else lookup_code,
        "market": stock.market if stock else None,
        "short_term": _score_dict(short) if short else None,
        "trend": _score_dict(trend) if trend else None,
        "setup": _score_dict(setup) if setup else None,
        "scores": _score_dict(trend) if trend else (_score_dict(short) if short else {}),
        "raw": {k: v for k, v in daily.__dict__.items() if not k.startswith("_")} if daily else {},
        "ai_analysis": daily.ai_analysis if daily else None,
        "trend_info": trend_info,
    }

@router.get("/{code}/history")
def get_score_history(
    code: str, strategy: str = Query("trend"),
    days: int = Query(30, ge=7, le=365),
    session: Session = Depends(get_session),
):
    # Try code as-is first, then zfill(6) for digit codes
    lookup_code = code
    if code.isdigit():
        stock = session.get(Stock, code)
        if not stock:
            lookup_code = code.zfill(6)
            stock = session.get(Stock, lookup_code)

    since = (date.today() - timedelta(days=days)).isoformat()
    records = (
        session.query(Score)
        .filter(Score.code == lookup_code, Score.strategy == strategy, Score.date >= since)
        .order_by(Score.date.asc()).all()
    )
    return [
        {"date": r.date, "total_score": r.total_score,
         "technical_score": r.technical_score, "capital_score": r.capital_score,
         "fundamental_score": r.fundamental_score, "news_score": r.news_score,
         "heat_score": r.heat_score}
        for r in records
    ]
