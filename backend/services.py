"""Service layer: business logic extracted from routers."""
import logging
from datetime import datetime
from backend.collectors.base import proxy_safe_get
from backend.database import get_db_session, upsert
from backend.models import Stock

logger = logging.getLogger(__name__)


def fetch_stock_from_tencent(code: str) -> dict | None:
    """Fetch stock name from Tencent Finance API."""
    code = code.zfill(6)
    prefix = "sh" if code.startswith(("6", "5", "9")) else ("bj" if code.startswith(("4", "8")) else "sz")
    market = prefix.upper()
    try:
        r = proxy_safe_get(f"http://qt.gtimg.cn/q={prefix}{code}")
        raw = r.text
        if '~' not in raw:
            return None
        parts = raw.split("~")
        if len(parts) < 2:
            return None
        name = parts[1]
        if not name:
            return None
        return {"code": code, "name": name, "market": market}
    except Exception:
        return None


def search_stock(q: str, session) -> list[dict]:
    """Search local DB first, fallback to Tencent API."""
    q = q.strip()
    if not q:
        return []
    local = session.query(Stock).filter(
        (Stock.code.contains(q)) | (Stock.name.contains(q))
    ).limit(10).all()
    if local:
        return [{"code": s.code, "name": s.name, "market": s.market} for s in local]
    result = fetch_stock_from_tencent(q)
    if result:
        upsert(session, Stock, {
            "code": result["code"], "name": result["name"],
            "market": result["market"], "is_watchlist": False, "index_tags": "[]",
        }, ["code"])
        session.commit()
        return [result]
    return []


def fetch_sectors(session) -> list[dict]:
    """Return top sectors by avg change_pct, each with constituent stocks."""
    from collections import defaultdict
    from sqlalchemy import func
    from backend.models import DailyData

    latest = session.query(func.max(DailyData.date)).scalar()
    if not latest:
        return []

    stocks = session.query(Stock).filter(Stock.industry != None, Stock.industry != "").all()
    codes = [s.code for s in stocks]
    dailies = {
        d.code: d
        for d in session.query(DailyData).filter(DailyData.date == latest, DailyData.code.in_(codes))
    }

    by_industry = defaultdict(list)
    for s in stocks:
        d = dailies.get(s.code)
        by_industry[s.industry].append({
            "code": s.code,
            "name": s.name,
            "change_pct": round(d.change_pct, 2) if d and d.change_pct is not None else None,
        })

    result = []
    for name, sector_stocks in by_industry.items():
        changes = [s["change_pct"] for s in sector_stocks if s["change_pct"] is not None]
        if not changes:
            continue
        avg_change = round(sum(changes) / len(changes), 2)
        sector_stocks.sort(key=lambda x: x["change_pct"] or 0, reverse=True)
        result.append({
            "name": name,
            "avg_change": avg_change,
            "count": len(sector_stocks),
            "stocks": sector_stocks[:30],
        })

    result.sort(key=lambda x: x["avg_change"], reverse=True)
    return result[:20]


def collect_single(code: str) -> dict:
    """Collect data and score for a single stock. Returns status dict."""
    code = code.zfill(6)
    session = get_db_session()
    try:
        stock = session.query(Stock).get(code)
        if not stock:
            return {"status": "error", "message": "Stock not in database"}

        target = {code}

        from backend.collectors.profile import fetch_profile
        try:
            fetch_profile(session, code)
        except Exception as e:
            logger.warning(f"profile collect failed for {code}: {e}")

        from backend.collectors.technical import collect_technical
        from backend.collectors.capital import collect_capital
        from backend.collectors.fundamental import collect_fundamental
        from backend.collectors.news import collect_news
        from backend.collectors.market_heat import collect_market_heat

        collectors = [
            ("technical", collect_technical),
            ("capital", collect_capital),
            ("fundamental", collect_fundamental),
            ("news", collect_news),
            ("market_heat", collect_market_heat),
        ]
        for name, fn in collectors:
            try:
                fn(session, target)
            except Exception as e:
                logger.warning(f"[{name}] collect failed for {code}: {e}")

        from backend.models import DailyData, Score, Strategy
        from backend.engine import ScoreEngine

        today = datetime.now().strftime("%Y-%m-%d")
        records = session.query(DailyData).filter(DailyData.code == code, DailyData.date == today).all()
        if records:
            universe = [r.__dict__ for r in records]
            engine = ScoreEngine()
            strategies = session.query(Strategy).all()
            for strategy in strategies:
                scores = engine.score_stock(records[0], universe, strategy)
                upsert(session, Score, {
                    "code": code, "date": today, "strategy": strategy.name,
                    **scores,
                }, ["code", "date", "strategy"])
            session.commit()

        return {"status": "done", "code": code}
    except Exception as e:
        logger.error(f"Single collect failed for {code}: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
    finally:
        session.close()
