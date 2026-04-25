from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database import get_session, upsert
from backend.models import Stock
from backend.collectors.profile import fetch_profile
from backend.services import search_stock, fetch_industries
import json

router = APIRouter(prefix="/api/stocks", tags=["stocks"])

class StockIn(BaseModel):
    code: str
    name: str = ""


@router.get("/watchlist")
def get_watchlist(session: Session = Depends(get_session)):
    stocks = session.query(Stock).filter(Stock.is_watchlist == True).all()
    return [{"code": s.code, "name": s.name, "market": s.market} for s in stocks]


@router.post("/watchlist")
def add_to_watchlist(stock: StockIn, session: Session = Depends(get_session)):
    code = stock.code.zfill(6)
    market = "SH" if code.startswith(("6", "5", "9")) else ("BJ" if code.startswith(("4", "8")) else "SZ")
    upsert(session, Stock, {
        "code": code, "name": stock.name or code,
        "market": market, "is_watchlist": True, "index_tags": "[]",
    }, ["code"])
    session.commit()
    return {"code": code, "name": stock.name}


@router.delete("/watchlist/{code}")
def remove_from_watchlist(code: str, session: Session = Depends(get_session)):
    stock = session.get(Stock, code.zfill(6))
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    stock.is_watchlist = False
    session.commit()
    return {"ok": True}


@router.get("/watchlist/{code}/check")
def check_watchlist(code: str, session: Session = Depends(get_session)):
    code = code.zfill(6)
    stock = session.get(Stock, code)
    return {"is_watchlist": stock.is_watchlist if stock else False}


@router.get("/search")
def search_stocks(q: str = "", session: Session = Depends(get_session)):
    return search_stock(q, session)


@router.get("/industries")
def get_industries():
    return fetch_industries()


@router.get("/{code}/profile")
def get_stock_profile(code: str, session: Session = Depends(get_session)):
    code = code.zfill(6)
    stock = fetch_profile(session, code)
    if not stock:
        raise HTTPException(status_code=404, detail="Stock not found")
    try:
        concepts = json.loads(stock.concepts or "[]")
    except json.JSONDecodeError:
        concepts = []
    return {
        "code": stock.code,
        "name": stock.name,
        "business": stock.business,
        "industry": stock.industry,
        "concepts": concepts,
        "total_share": stock.total_share,
        "float_share": stock.float_share,
        "total_mv": stock.total_mv,
        "float_mv": stock.float_mv,
        "pe": stock.pe,
        "pb": stock.pb,
        "list_date": stock.list_date,
    }
