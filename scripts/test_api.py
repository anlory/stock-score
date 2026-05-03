"""
单个接口数据测试，输出原始结果到终端。

用法:
    uv run python scripts/test_api.py <接口> [股票代码] [交易日]

接口列表:
    daily           日K线
    daily_basic     每日指标（PE/PB/换手率等）
    moneyflow       资金流向
    fina_indicator  财务指标（ROE/净利润增速）
    limit_list      涨停板列表
    trade_cal       交易日历
    stock_basic     股票基本信息
    stock_company   公司信息
    ths_index       同花顺行业指数列表
    ths_daily       同花顺行业日行情
    index_member    指数成分股
    news            消息面（pywencai）

示例:
    uv run python scripts/test_api.py daily                          # 默认 000001，最近交易日
    uv run python scripts/test_api.py daily --code 600036
    uv run python scripts/test_api.py moneyflow -c 000001 -d 2026-04-25
    uv run python scripts/test_api.py news --code 000001
    uv run python scripts/test_api.py trade_cal
    uv run python scripts/test_api.py ths_index
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("NODE_NO_WARNINGS", "1")

from datetime import date, timedelta


def get_date(arg=None):
    if arg:
        return arg
    # 取最近 7 天内最近的交易日
    from backend.collectors.tushare_client import get_last_trade_date
    return get_last_trade_date()


def get_pro():
    from backend.collectors.tushare_client import get_pro as _get_pro
    return _get_pro()


def print_df(df, label=""):
    if df is None or (hasattr(df, "empty") and df.empty):
        print(f"[{label}] 无数据")
        return
    print(f"\n[{label}]  shape={df.shape}")
    print(df.to_string(max_rows=20, max_cols=20))
    print()


def cmd_daily(code="000001", trade_date=None):
    from backend.collectors.tushare_client import to_ts_code, to_ts_date, ts_call
    pro = get_pro()
    d = trade_date or get_date()
    start = to_ts_date((date.fromisoformat(d) - timedelta(days=10)).isoformat())
    df = ts_call(pro.daily, ts_code=to_ts_code(code), start_date=start, end_date=to_ts_date(d))
    print_df(df, f"daily {code}")


def cmd_daily_basic(code="000001", trade_date=None):
    from backend.collectors.tushare_client import to_ts_code, to_ts_date, ts_call
    pro = get_pro()
    d = to_ts_date(trade_date or get_date())
    df = ts_call(pro.daily_basic, trade_date=d, fields="ts_code,pe_ttm,pb,total_mv,turnover_rate,volume_ratio")
    if df is not None and not df.empty:
        ts = to_ts_code(code)
        row = df[df["ts_code"] == ts]
        print_df(row if not row.empty else df.head(5), f"daily_basic {code}")
    else:
        print("[daily_basic] 无数据")


def cmd_moneyflow(code="000001", trade_date=None):
    from backend.collectors.tushare_client import to_ts_code, to_ts_date, ts_call
    pro = get_pro()
    d = trade_date or get_date()
    start = to_ts_date((date.fromisoformat(d) - timedelta(days=10)).isoformat())
    df = ts_call(pro.moneyflow, ts_code=to_ts_code(code), start_date=start, end_date=to_ts_date(d))
    print_df(df, f"moneyflow {code}")


def cmd_fina_indicator(code="000001", trade_date=None):
    from backend.collectors.tushare_client import to_ts_code, ts_call
    from backend.collectors.fundamental import _latest_fina_period
    pro = get_pro()
    d = date.fromisoformat(trade_date or get_date())
    period = _latest_fina_period(d.year, d.month)
    df = ts_call(pro.fina_indicator, ts_code=to_ts_code(code), period=period,
                 fields="ts_code,roe,netprofit_yoy,ann_date,end_date")
    print_df(df, f"fina_indicator {code} period={period}")


def cmd_limit_list(trade_date=None):
    from backend.collectors.tushare_client import to_ts_date, ts_call
    pro = get_pro()
    d = to_ts_date(trade_date or get_date())
    df = ts_call(pro.limit_list_d, trade_date=d, fields="ts_code,trade_date,fd_amount,first_time")
    print_df(df, f"limit_list_d {d}")


def cmd_trade_cal(trade_date=None):
    from backend.collectors.tushare_client import to_ts_date, ts_call
    pro = get_pro()
    d = trade_date or get_date()
    start = to_ts_date((date.fromisoformat(d) - timedelta(days=14)).isoformat())
    df = ts_call(pro.trade_cal, start_date=start, end_date=to_ts_date(d), is_open="1", fields="cal_date")
    print_df(df, "trade_cal")


def cmd_stock_basic(code="000001", trade_date=None):
    from backend.collectors.tushare_client import to_ts_code, ts_call
    pro = get_pro()
    df = ts_call(pro.stock_basic, ts_code=to_ts_code(code), list_status="L",
                 fields="ts_code,name,industry,list_date,total_share,float_share")
    print_df(df, f"stock_basic {code}")


def cmd_stock_company(code="000001", trade_date=None):
    from backend.collectors.tushare_client import to_ts_code, ts_call
    pro = get_pro()
    df = ts_call(pro.stock_company, ts_code=to_ts_code(code), fields="ts_code,business_scope")
    print_df(df, f"stock_company {code}")


def cmd_ths_index(code=None, trade_date=None):
    from backend.collectors.tushare_client import ts_call
    pro = get_pro()
    df = ts_call(pro.ths_index, exchange="A", type="N")
    print_df(df, "ths_index")


def cmd_ths_daily(code=None, trade_date=None):
    from backend.collectors.tushare_client import to_ts_date, ts_call
    pro = get_pro()
    d = to_ts_date(trade_date or get_date())
    df = ts_call(pro.ths_daily, trade_date=d)
    print_df(df, f"ths_daily {d}")


def cmd_index_member(code="000300.SH", trade_date=None):
    from backend.collectors.tushare_client import ts_call
    pro = get_pro()
    df = ts_call(pro.index_member, index_code=code, fields="con_code,con_name")
    print_df(df, f"index_member {code}")


def cmd_news(code="000001", trade_date=None):
    from backend.collectors.base import query_wencai
    df = query_wencai(f"{code} 近30日研报数量 研报评级")
    print_df(df, f"news(pywencai) {code}")


COMMANDS = {
    "daily":          cmd_daily,
    "daily_basic":    cmd_daily_basic,
    "moneyflow":      cmd_moneyflow,
    "fina_indicator": cmd_fina_indicator,
    "limit_list":     cmd_limit_list,
    "trade_cal":      cmd_trade_cal,
    "stock_basic":    cmd_stock_basic,
    "stock_company":  cmd_stock_company,
    "ths_index":      cmd_ths_index,
    "ths_daily":      cmd_ths_daily,
    "index_member":   cmd_index_member,
    "news":           cmd_news,
}


def main():
    import argparse
    import inspect

    parser = argparse.ArgumentParser(
        description="单个 tushare / pywencai 接口测试",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="可用接口:\n  " + "\n  ".join(COMMANDS),
    )
    parser.add_argument("接口", choices=COMMANDS, metavar="接口", help="接口名，见下方列表")
    parser.add_argument("--code", "-c", default="000001", help="股票代码（默认 000001）")
    parser.add_argument("--date", "-d", default=None, help="交易日 YYYY-MM-DD（默认自动取最近交易日）")

    args = parser.parse_args()
    fn = COMMANDS[args.接口]
    sig = inspect.signature(fn)
    kwargs = {}
    if "code" in sig.parameters:
        kwargs["code"] = args.code
    if "trade_date" in sig.parameters:
        kwargs["trade_date"] = args.date

    fn(**kwargs)


if __name__ == "__main__":
    main()
