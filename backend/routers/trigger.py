import threading
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from fastapi import APIRouter
from backend.database import get_db_session
from backend.collectors.universe import sync_universe
from backend.collectors.technical import collect_technical
from backend.collectors.capital import collect_capital
from backend.collectors.fundamental import collect_fundamental
from backend.collectors.news import collect_news
from backend.collectors.market_heat import collect_market_heat
from backend.collectors.trend import collect_trend
from backend.engine import ScoreEngine
from backend.models import Stock
from backend.services import collect_single

router = APIRouter(prefix="/api/trigger", tags=["trigger"])
logger = logging.getLogger(__name__)

_status = {"running": False, "last_run": None, "last_result": None}


def _run_collector(name, fn, codes):
    try:
        session = get_db_session()
        try:
            count = fn(session, codes)
            logger.info(f"[{name}] collected {count} stocks")
            return (name, count, None)
        finally:
            session.close()
    except Exception as e:
        logger.error(f"[{name}] failed: {e}", exc_info=True)
        return (name, 0, str(e))


def _run_pipeline():
    _status["running"] = True
    session = get_db_session()
    try:
        sync_universe(session)
        codes = {s.code for s in session.query(Stock).all()}
        session.close()

        logger.info(f"Universe synced: {len(codes)} stocks, starting parallel collection")

        collectors = [
            ("technical", collect_technical),
            ("capital", collect_capital),
            ("fundamental", collect_fundamental),
            ("news", collect_news),
            ("market_heat", collect_market_heat),
            ("trend", collect_trend),
        ]

        with ThreadPoolExecutor(max_workers=6) as pool:
            futures = {
                pool.submit(_run_collector, name, fn, codes): name
                for name, fn in collectors
            }
            for future in as_completed(futures):
                name, count, err = future.result()
                if err:
                    logger.error(f"Collector {name} failed: {err}")

        session = get_db_session()
        engine = ScoreEngine()
        count = engine.run(session)
        _status["last_result"] = f"Scored {count} records"
    except Exception as e:
        _status["last_result"] = f"Error: {e}"
        logger.error(f"Pipeline error: {e}", exc_info=True)
    finally:
        if session:
            session.close()
        _status["running"] = False
        _status["last_run"] = datetime.now().isoformat()


@router.post("/collect")
def trigger_collect():
    if _status["running"]:
        return {"status": "already_running"}
    thread = threading.Thread(target=_run_pipeline, daemon=True)
    thread.start()
    return {"status": "started"}


@router.post("/collect/{code}")
def collect_single_endpoint(code: str):
    return collect_single(code)


@router.get("/status")
def get_status():
    return _status
