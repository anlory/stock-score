from datetime import date, timedelta
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from backend.database import get_session
from backend.models import Score, Stock, DailyData
from backend.collectors.tencent_kline import fetch_kline

router = APIRouter(prefix="/api/scores", tags=["scores"])


@router.get("/kline/{code}")
def get_kline(code: str, days: int = Query(60, ge=7, le=365)):
    """Get daily K-line data for a stock via Tencent Finance API."""
    code = code.zfill(6)
    try:
        return fetch_kline(code, days)
    except Exception:
        return []

def _latest_date(session):
    row = session.query(Score).order_by(Score.date.desc()).first()
    return row.date if row else date.today().isoformat()


@router.get("/leaderboard")
def get_leaderboard(
    type: str = Query("other"),
    session: Session = Depends(get_session),
):
    latest = _latest_date(session)
    trend_map = {}
    for s in session.query(Score).filter(Score.date == latest, Score.strategy == "trend"):
        trend_map[s.code] = s
    short_map = {}
    for s in session.query(Score).filter(Score.date == latest, Score.strategy == "short_term"):
        short_map[s.code] = s

    all_codes = set(trend_map.keys()) | set(short_map.keys())
    stocks = {s.code: s for s in session.query(Stock).filter(Stock.code.in_(all_codes))}
    if type == "watchlist":
        all_codes = {c for c in all_codes if c in stocks and stocks[c].is_watchlist}

    ranked = sorted(all_codes, key=lambda c: trend_map[c].total_score if c in trend_map else 0, reverse=True)[:200]
    return {
        "date": latest,
        "stocks": [
        {
            "rank": i + 1, "code": c, "name": stocks[c].name if c in stocks else c,
            "is_watchlist": stocks[c].is_watchlist if c in stocks else False,
            "short_score": short_map[c].total_score if c in short_map else None,
            "trend_score": trend_map[c].total_score if c in trend_map else None,
            "technical_score": trend_map[c].technical_score if c in trend_map else None,
            "capital_score": trend_map[c].capital_score if c in trend_map else None,
            "fundamental_score": trend_map[c].fundamental_score if c in trend_map else None,
            "news_score": trend_map[c].news_score if c in trend_map else None,
            "heat_score": trend_map[c].heat_score if c in trend_map else None,
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
    code = code.zfill(6)
    stock = session.get(Stock, code)
    daily = session.query(DailyData).filter(
        DailyData.code == code, DailyData.date == latest
    ).first()
    short = session.query(Score).filter(
        Score.code == code, Score.date == latest, Score.strategy == "short_term"
    ).first()
    trend = session.query(Score).filter(
        Score.code == code, Score.date == latest, Score.strategy == "trend"
    ).first()
    if not short and not trend:
        return {"error": "暂无评分数据"}
    return {
        "code": code,
        "name": stock.name if stock else code,
        "short_term": _score_dict(short) if short else None,
        "trend": _score_dict(trend) if trend else None,
        "scores": _score_dict(trend) if trend else (_score_dict(short) if short else {}),
        "raw": {k: v for k, v in daily.__dict__.items() if not k.startswith("_")} if daily else {},
        "ai_analysis": daily.ai_analysis if daily else None,
    }

@router.get("/{code}/history")
def get_score_history(
    code: str, strategy: str = Query("trend"),
    days: int = Query(30, ge=7, le=365),
    session: Session = Depends(get_session),
):
    code = code.zfill(6)
    since = (date.today() - timedelta(days=days)).isoformat()
    records = (
        session.query(Score)
        .filter(Score.code == code, Score.strategy == strategy, Score.date >= since)
        .order_by(Score.date.asc()).all()
    )
    return [
        {"date": r.date, "total_score": r.total_score,
         "technical_score": r.technical_score, "capital_score": r.capital_score,
         "fundamental_score": r.fundamental_score, "news_score": r.news_score,
         "heat_score": r.heat_score}
        for r in records
    ]
