import os
import re
import time
import pywencai
import pandas as pd
import requests as _requests
import logging

logger = logging.getLogger(__name__)

_PROXY_KEYS = ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY")
_PROXIES_NONE = {"http": None, "https": None}

# Clear proxy env vars at import time (needed by pywencai and other libs)
for _k in _PROXY_KEYS:
    os.environ.pop(_k, None)


def proxy_safe_get(url: str, **kwargs) -> _requests.Response:
    """requests.get with proxy bypass. Use for all external HTTP calls."""
    kwargs.setdefault("proxies", _PROXIES_NONE)
    kwargs.setdefault("timeout", 10)
    return _requests.get(url, **kwargs)


def query_wencai(query: str, query_type: str = "stock", loop: bool = False) -> pd.DataFrame:
    """Execute pywencai query. Returns empty DataFrame on failure."""
    try:
        result = pywencai.get(query=query, query_type=query_type, loop=loop)
        if result is None:
            return pd.DataFrame()
        if isinstance(result, dict):
            for key in ("tableV1", "data", "result"):
                if key in result and isinstance(result[key], pd.DataFrame):
                    result = result[key]
                    break
            else:
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


def build_col_map(columns: list[str], col_patterns: dict[str, list[str]]) -> dict[str, str]:
    """Map logical field names to actual column names using regex patterns."""
    mapping = {}
    for field, patterns in col_patterns.items():
        for col in columns:
            if any(re.search(p, col) for p in patterns):
                mapping[field] = col
                break
    return mapping


def collect_wencai_fields(df: pd.DataFrame, target_codes: set[str],
                          col_patterns: dict[str, list[str]],
                          value_transforms: dict[str, callable] = None) -> dict[str, dict]:
    """Extract and merge field values from a wencai DataFrame across multiple rows per stock.

    value_transforms: optional dict of field -> callable to convert raw values (e.g. {"report_count": int})
    """
    code_col = next((c for c in df.columns if "代码" in c or c == "code"), None)
    if not code_col:
        return {}

    col_map = build_col_map(df.columns.tolist(), col_patterns)
    transforms = value_transforms or {}
    merged = {}

    for _, row in df.iterrows():
        code = normalize_code(row[code_col])
        if code not in target_codes:
            continue
        if code not in merged:
            merged[code] = {"code": code}
        for field, col in col_map.items():
            if field in merged[code] and merged[code][field] is not None:
                continue
            val = row.get(col)
            if val is None or str(val) == "nan":
                continue
            if field in transforms:
                try:
                    merged[code][field] = transforms[field](val)
                except (TypeError, ValueError):
                    pass
            else:
                merged[code][field] = val

    return merged
