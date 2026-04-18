from datetime import date, timedelta
from fastapi import APIRouter, Query, Depends
from sqlalchemy.orm import Session
from backend.database import get_session
from backend.models import Score, Stock, DailyData

router = APIRouter(prefix="/api/scores", tags=["scores"])

@router.get("/leaderboard")
def get_leaderboard(
    strategy: str = Query("trend"),
    type: str = Query("other"),
    session: Session = Depends(get_session),
):
    today = date.today().isoformat()
    query = (
        session.query(Score, Stock)
        .join(Stock, Score.code == Stock.code)
        .filter(Score.date == today, Score.strategy == strategy)
    )
    if type == "watchlist":
        query = query.filter(Stock.is_watchlist == True)
    else:
        query = query.filter(Stock.is_watchlist == False)
    results = query.order_by(Score.total_score.desc()).limit(200).all()
    return [
        {
            "rank": i + 1, "code": s.code, "name": st.name,
            "total_score": s.total_score,
            "technical_score": s.technical_score,
            "capital_score": s.capital_score,
            "fundamental_score": s.fundamental_score,
            "news_score": s.news_score,
            "heat_score": s.heat_score,
        }
        for i, (s, st) in enumerate(results)
    ]

@router.get("/{code}")
def get_stock_detail(code: str, strategy: str = Query("trend"), session: Session = Depends(get_session)):
    today = date.today().isoformat()
    code = code.zfill(6)
    score = session.query(Score).filter(
        Score.code == code, Score.date == today, Score.strategy == strategy
    ).first()
    stock = session.get(Stock, code)
    daily = session.query(DailyData).filter(
        DailyData.code == code, DailyData.date == today
    ).first()
    if not score:
        return {"error": "No score data for today"}
    return {
        "code": code,
        "name": stock.name if stock else code,
        "scores": {
            "total": score.total_score,
            "technical": score.technical_score,
            "capital": score.capital_score,
            "fundamental": score.fundamental_score,
            "news": score.news_score,
            "heat": score.heat_score,
        },
        "raw": {k: v for k, v in daily.__dict__.items() if not k.startswith("_")} if daily else {},
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
