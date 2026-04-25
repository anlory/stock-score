"""Service layer: business logic extracted from routers."""
import json
import logging
import re
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


def fetch_industries() -> list[dict]:
    """Return all A-share industry sectors with today's change from Sina."""
    try:
        r = proxy_safe_get(
            "http://vip.stock.finance.sina.com.cn/q/view/newSinaHy.php",
            headers={"User-Agent": "Mozilla/5.0"},
        )
        m = re.search(r'\{(.+)\}', r.text, re.S)
        data = json.loads("{" + m.group(1) + "}")
        result = []
        for key, val in data.items():
            parts = val.split(",")
            if len(parts) >= 13:
                result.append({
                    "name": parts[1],
                    "count": int(parts[2]),
                    "change_pct": round(float(parts[5]), 2),
                    "volume": int(parts[6]),
                    "amount": round(float(parts[7]) / 1e8, 2),
                    "leading_name": parts[12],
                    "leading_pct": round(float(parts[11]), 2),
                })
        result.sort(key=lambda x: x["change_pct"], reverse=True)
        return result
    except Exception:
        return []


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
        from backend.collectors.trend import collect_trend

        collectors = [
            ("technical", collect_technical),
            ("capital", collect_capital),
            ("fundamental", collect_fundamental),
            ("news", collect_news),
            ("market_heat", collect_market_heat),
            ("trend", collect_trend),
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
