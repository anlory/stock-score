import logging
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def collect_trend(session: Session, target_codes: set[str], today: str | None = None) -> int:
    return 0
