import os
import pywencai
import pandas as pd
import logging

# Bypass system proxy for requests used by pywencai and other libraries
for _k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"):
    os.environ.pop(_k, None)

logger = logging.getLogger(__name__)

def query_wencai(query: str, query_type: str = "stock") -> pd.DataFrame:
    """Execute pywencai query. Returns empty DataFrame on failure."""
    try:
        result = pywencai.get(query=query, query_type=query_type)
        if result is None:
            return pd.DataFrame()
        if isinstance(result, dict):
            return pd.DataFrame()
        if isinstance(result, pd.DataFrame) and result.empty:
            return pd.DataFrame()
        return result
    except Exception as e:
        logger.error(f"pywencai query failed [{query[:40]}]: {e}")
        return pd.DataFrame()

def normalize_code(code) -> str:
    """Normalize stock code to 6-digit string."""
    return str(code).split(".")[0].zfill(6)
