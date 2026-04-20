import threading
import logging
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

router = APIRouter(prefix="/api/trigger", tags=["trigger"])
logger = logging.getLogger(__name__)

_status = {"running": False, "last_run": None, "last_result": None}

def _run_pipeline():
    _status["running"] = True
    session = get_db_session()
    try:
        sync_universe(session)
        codes = {s.code for s in session.query(Stock).all()}
        collect_technical(session, codes)
        collect_capital(session, codes)
        collect_fundamental(session, codes)
        collect_news(session, codes)
        collect_market_heat(session, codes)
        collect_trend(session, codes)
        engine = ScoreEngine()
        count = engine.run(session)
        _status["last_result"] = f"Scored {count} records"
    except Exception as e:
        _status["last_result"] = f"Error: {e}"
        logger.error(f"Pipeline error: {e}", exc_info=True)
    finally:
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

@router.get("/status")
def get_status():
    return _status
