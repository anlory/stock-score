from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel
from backend.database import get_session, upsert
from backend.models import Stock
from backend.collectors.profile import fetch_profile
from backend.services import search_stock, fetch_sectors
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
    from backend.services import fetch_stock_from_tencent
    code = stock.code.zfill(6)
    existing = session.get(Stock, code)
    if existing:
        existing.is_watchlist = True
        if stock.name:
            existing.name = stock.name
        session.commit()
        return {"code": code, "name": existing.name}

    name = stock.name
    if not name:
        info = fetch_stock_from_tencent(code)
        name = info["name"] if info else code

    market = "SH" if code.startswith(("6", "5", "9")) else ("BJ" if code.startswith(("4", "8")) else "SZ")
    upsert(session, Stock, {
        "code": code, "name": name,
        "market": market, "is_watchlist": True, "index_tags": "[]",
    }, ["code"])
    session.commit()
    return {"code": code, "name": name}


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


@router.get("/sectors")
def get_sectors(session: Session = Depends(get_session)):
    return fetch_sectors(session)


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
        "chairman": stock.chairman,
        "manager": stock.manager,
        "setup_date": stock.setup_date,
        "province": stock.province,
        "city": stock.city,
        "introduction": stock.introduction,
        "main_business": stock.main_business,
        "website": stock.website,
        "employees": stock.employees,
        "office": stock.office,
    }
