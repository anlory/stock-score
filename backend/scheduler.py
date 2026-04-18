from apscheduler.schedulers.background import BackgroundScheduler
from backend.config import COLLECT_HOUR, COLLECT_MINUTE
import logging

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()

def start_scheduler():
    from backend.routers.trigger import _run_pipeline
    scheduler.add_job(
        _run_pipeline, trigger="cron",
        hour=COLLECT_HOUR, minute=COLLECT_MINUTE,
        id="daily_collect", replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Scheduler: daily collect at {COLLECT_HOUR}:{COLLECT_MINUTE:02d}")
