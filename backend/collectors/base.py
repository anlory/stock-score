import pywencai
import pandas as pd
import logging

logger = logging.getLogger(__name__)

def query_wencai(loop_ask: str, query_type: str = "stock") -> pd.DataFrame:
    """Execute pywencai query. Returns empty DataFrame on failure."""
    try:
        result = pywencai.get(loop_ask=loop_ask, query_type=query_type)
        if result is None or (hasattr(result, 'empty') and result.empty):
            return pd.DataFrame()
        return result
    except Exception as e:
        logger.error(f"pywencai query failed [{loop_ask[:40]}]: {e}")
        return pd.DataFrame()

def normalize_code(code) -> str:
    """Normalize stock code to 6-digit string."""
    return str(code).split(".")[0].zfill(6)
