from backend.collectors.tushare_client import to_ts_code, from_ts_code, to_ts_date

def test_to_ts_code_sh():
    assert to_ts_code("600519") == "600519.SH"

def test_to_ts_code_sz():
    assert to_ts_code("000001") == "000001.SZ"

def test_to_ts_code_bj():
    assert to_ts_code("430047") == "430047.BJ"

def test_to_ts_code_sh_prefix_5():
    assert to_ts_code("501010") == "501010.SH"

def test_from_ts_code():
    assert from_ts_code("000001.SZ") == "000001"
    assert from_ts_code("600519.SH") == "600519"

def test_to_ts_date():
    assert to_ts_date("2024-01-01") == "20240101"
    assert to_ts_date("2026-04-25") == "20260425"
