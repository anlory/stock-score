import threading
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from fastapi import APIRouter
from backend.database import get_db_session
from backend.collectors.tushare_client import get_last_trade_date
from backend.collectors.universe import sync_universe
from backend.collectors.technical import collect_technical
from backend.collectors.capital import collect_capital
from backend.collectors.market_heat import collect_market_heat
from backend.collectors.hk_us.technical import collect_hk_us_technical
from backend.collectors.hk_us.fundamental import collect_hk_us_fundamental
from backend.collectors.hk_us.market_heat import collect_hk_us_heat
from backend.collectors.hk_us.news import collect_hk_us_news
from backend.engine import ScoreEngine
from backend.models import Stock
from backend.services import collect_single

router = APIRouter(prefix="/api/trigger", tags=["trigger"])
logger = logging.getLogger(__name__)

_collect_status = {"running": False, "last_run": None, "last_result": None}
_score_status = {"running": False, "last_run": None, "last_result": None}


def _run_collector(name, fn, codes, trade_date):
    try:
        session = get_db_session()
        try:
            count = fn(session, codes, today=trade_date)
            logger.info(f"[{name}] collected {count} stocks")
            return (name, count, None)
        finally:
            session.close()
    except Exception as e:
        logger.error(f"[{name}] failed: {e}", exc_info=True)
        return (name, 0, str(e))


def _run_collect(trade_date=None, target=None):
    """Run data collection only (universe sync + collectors).
    target: None (all), 'a' (A-share only), 'hk_us' (HK/US only)
    """
    _collect_status["running"] = True
    t0 = time.time()
    session = get_db_session()
    try:
        trade_date = trade_date or get_last_trade_date()
        if not trade_date:
            _collect_status["last_result"] = "Error: could not determine trade date"
            return None

        # A-share collection
        if target is None or target == "a":
            sync_universe(session, today=trade_date)
            codes = {s.code for s in session.query(Stock).filter(
                Stock.market.in_(["SH", "SZ", "BJ"]),
            ).all()}
            session.close()

            logger.info(f"[Collect] Trade date: {trade_date}, A-share: {len(codes)} stocks")

            collectors = [
                ("technical", collect_technical),
                ("capital", collect_capital),
                ("market_heat", collect_market_heat),
            ]

            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {
                    pool.submit(_run_collector, name, fn, codes, trade_date): name
                    for name, fn in collectors
                }
                for future in as_completed(futures):
                    name, count, err = future.result()
                    if err:
                        logger.error(f"Collector {name} failed: {err}")
        else:
            session.close()

        # HK/US stock collection
        if target is None or target == "hk_us":
            hk_session = get_db_session()
            try:
                hk_us_stocks = hk_session.query(Stock).filter(
                    ~Stock.market.in_(["SH", "SZ", "BJ"])
                ).all()
            except Exception:
                hk_us_stocks = []
            finally:
                hk_session.close()

            if hk_us_stocks:
                hk_us_codes = {s.code: s.market for s in hk_us_stocks}

                logger.info(f"[Collect] HK/US: {len(hk_us_codes)} stocks")

                hk_us_collectors = [
                    ("hk_us_technical", lambda s, c, t: collect_hk_us_technical(s, hk_us_codes, t)),
                    ("hk_us_fundamental", lambda s, c, t: collect_hk_us_fundamental(s, hk_us_codes, t)),
                    ("hk_us_heat", lambda s, c, t: collect_hk_us_heat(s, hk_us_codes, t)),
                    ("hk_us_news", lambda s, c, t: collect_hk_us_news(s, hk_us_codes, t)),
                ]

                # 串行执行避免 yfinance 全局限流
                for name, fn in hk_us_collectors:
                    _, count, err = _run_collector(name, fn, None, trade_date)
                    if err:
                        logger.error(f"HK/US collector {name} failed: {err}")

        elapsed = round(time.time() - t0)
        _collect_status["last_result"] = f"Collected {len(codes)} stocks for {trade_date} in {elapsed}s"
        logger.info(f"[Collect] done in {elapsed}s")
        return trade_date
    except Exception as e:
        _collect_status["last_result"] = f"Error: {e}"
        logger.error(f"[Collect] error: {e}", exc_info=True)
        return None
    finally:
        if session:
            session.close()
        _collect_status["running"] = False
        _collect_status["last_run"] = datetime.now().isoformat()


def _run_score(trade_date=None):
    """Run scoring only."""
    _score_status["running"] = True
    t0 = time.time()
    try:
        trade_date = trade_date or get_last_trade_date()
        if not trade_date:
            _score_status["last_result"] = "Error: could not determine trade date"
            return

        session = get_db_session()
        engine = ScoreEngine()
        count = engine.run(session, today=trade_date)
        session.close()
        elapsed = round(time.time() - t0)
        _score_status["last_result"] = f"Scored {count} records for {trade_date} in {elapsed}s"
        logger.info(f"[Score] done in {elapsed}s")
    except Exception as e:
        _score_status["last_result"] = f"Error: {e}"
        logger.error(f"[Score] error: {e}", exc_info=True)
    finally:
        _score_status["running"] = False
        _score_status["last_run"] = datetime.now().isoformat()


def _run_pipeline(target=None):
    """Full pipeline: skip collection if data already exists for today."""
    trade_date = get_last_trade_date()
    if not trade_date:
        _collect_status["running"] = True
        _collect_status["last_result"] = "Error: could not determine trade date"
        _collect_status["running"] = False
        return

    # Check if data already collected for this trade date
    from backend.models import DailyData
    session = get_db_session()
    existing = session.query(DailyData).filter(DailyData.date == trade_date).count()
    session.close()

    if existing > 0:
        logger.info(f"[Pipeline] Data already exists for {trade_date} ({existing} records), scoring only")
        _run_score(trade_date)
    else:
        trade_date = _run_collect(target=target)
        if trade_date:
            _run_score(trade_date)


@router.post("/collect")
def trigger_collect(market: str = None):
    """Full pipeline. Optional market filter: 'a', 'hk_us'."""
    if _collect_status["running"]:
        return {"status": "already_running"}

    if market == "a":
        thread = threading.Thread(target=lambda: _run_collect(target="a"), daemon=True)
    elif market == "hk_us":
        thread = threading.Thread(target=lambda: _run_collect(target="hk_us"), daemon=True)
    else:
        thread = threading.Thread(target=_run_pipeline, daemon=True)
    thread.start()
    return {"status": "started"}


@router.post("/collect-data")
def trigger_collect_data_only():
    """Collect data only, skip scoring."""
    if _collect_status["running"]:
        return {"status": "already_running"}
    thread = threading.Thread(target=_run_collect, daemon=True)
    thread.start()
    return {"status": "started"}


@router.post("/score")
def trigger_score():
    """Run scoring only, using existing collected data."""
    if _score_status["running"]:
        return {"status": "already_running"}
    thread = threading.Thread(target=_run_score, daemon=True)
    thread.start()
    return {"status": "started"}


@router.post("/collect/{code}")
def collect_single_endpoint(code: str):
    return collect_single(code)


@router.get("/status")
def get_status():
    return {
        "collect": _collect_status,
        "score": _score_status,
    }
