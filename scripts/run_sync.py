"""
手动触发数据同步/评分，打印各阶段耗时和结果。

用法:
    uv run python scripts/run_sync.py                    # 全量 A股+港美股（采集+评分）
    uv run python scripts/run_sync.py --collect-only      # 仅采集数据
    uv run python scripts/run_sync.py --score-only        # 仅评分
    uv run python scripts/run_sync.py --date 2026-04-25   # 指定交易日
    uv run python scripts/run_sync.py --watchlist          # 仅同步自选股
    uv run python scripts/run_sync.py --a-stock            # 仅 A 股
    uv run python scripts/run_sync.py --hk-us              # 仅港美股
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("NODE_NO_WARNINGS", "1")

import argparse
import logging
import time
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("sync")


def _step(name, fn, *args, **kwargs):
    logger.info(f">>> {name} 开始")
    t = time.time()
    result = fn(*args, **kwargs)
    elapsed = round(time.time() - t, 1)
    logger.info(f"<<< {name} 完成  耗时={elapsed}s  结果={result}")
    return result, elapsed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", help="指定交易日 YYYY-MM-DD，默认自动取最近交易日")
    parser.add_argument("--collect-only", action="store_true", help="仅采集数据，跳过评分")
    parser.add_argument("--score-only", action="store_true", help="仅评分，跳过采集")
    parser.add_argument("--watchlist", action="store_true", help="仅同步自选股，跳过 universe 全量同步")
    parser.add_argument("--a-stock", action="store_true", help="仅同步 A 股")
    parser.add_argument("--hk-us", action="store_true", help="仅同步港美股")
    args = parser.parse_args()

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
    from backend.database import get_db_session
    from backend.models import Stock

    trade_date = args.date or get_last_trade_date()
    if not trade_date:
        logger.error("无法确定交易日，退出")
        return

    do_a = not args.hk_us          # 默认做 A 股，除非指定 --hk-us
    do_hk_us = not args.a_stock    # 默认做港美股，除非指定 --a-stock
    do_watchlist = args.watchlist

    if do_watchlist:
        mode = "自选股"
        do_a = True
        do_hk_us = False
    elif do_a and do_hk_us:
        mode = "全量(A股+港美股)"
    elif do_a:
        mode = "仅A股"
    else:
        mode = "仅港美股"

    if args.score_only:
        mode = "仅评分"
    elif args.collect_only:
        mode += " 仅采集"

    logger.info(f"交易日: {trade_date}  模式: {mode}")

    t_total = time.time()
    timings: dict[str, float] = {}

    # ── 评分模式 ──
    if args.score_only:
        session = get_db_session()
        _, timings["scoring"] = _step("评分引擎", ScoreEngine().run, session, today=trade_date)
        session.close()
        _print_summary(trade_date, timings, t_total)
        return

    # ── 采集模式 ──
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _run(name, fn, codes_arg):
        t = time.time()
        s = get_db_session()
        try:
            count = fn(s, codes_arg, today=trade_date)
            elapsed = round(time.time() - t, 1)
            logger.info(f"<<< {name:20s} 完成  count={count}  耗时={elapsed}s")
            return name, elapsed
        except Exception as e:
            logger.error(f"[{name}] 失败: {e}", exc_info=True)
            return name, -1
        finally:
            s.close()

    # ── A 股采集 ──
    if do_a:
        session = get_db_session()

        if do_watchlist:
            a_codes = {s.code for s in session.query(Stock).filter(
                Stock.is_watchlist == True,
                Stock.market.in_(["SH", "SZ", "BJ"]),
            ).all()}
            logger.info(f"A 股自选: {len(a_codes)} 只")
        else:
            _, timings["universe_a"] = _step("A 股 Universe 同步", sync_universe, session, today=trade_date)
            a_codes = {s.code for s in session.query(Stock).filter(
                Stock.market.in_(["SH", "SZ", "BJ"]),
            ).all()}
            logger.info(f"A 股股票池: {len(a_codes)} 只")
        session.close()

        if a_codes:
            a_collectors = [
                ("a_technical",    collect_technical),
                ("a_capital",      collect_capital),
                ("a_market_heat",  collect_market_heat),
            ]
            logger.info(">>> A 股并行采集开始")
            t_a = time.time()
            with ThreadPoolExecutor(max_workers=6) as pool:
                futures = {pool.submit(_run, name, fn, a_codes): name for name, fn in a_collectors}
                for f in as_completed(futures):
                    name, elapsed = f.result()
                    timings[name] = elapsed
            timings["a_collect_total"] = round(time.time() - t_a, 1)

    # ── 港美股采集 ──
    if do_hk_us and not do_watchlist:
        session = get_db_session()
        hk_us_stocks = session.query(Stock).filter(
            ~Stock.market.in_(["SH", "SZ", "BJ"]),
        ).all()

        # 如果港美股股票池为空，先同步成分股
        if not hk_us_stocks:
            from backend.collectors.hk_us.universe import sync_hk_us_universe
            logger.info("港美股股票池为空，先同步成分股...")
            _, timings["universe_hk_us"] = _step("港美股 Universe 同步", sync_hk_us_universe, session)
            hk_us_stocks = session.query(Stock).filter(
                ~Stock.market.in_(["SH", "SZ", "BJ"]),
            ).all()
        session.close()

        if hk_us_stocks:
            hk_us_codes = {s.code: s.market for s in hk_us_stocks}
            logger.info(f"港美股股票池: {len(hk_us_codes)} 只")

            hk_us_collectors = [
                ("hk_us_technical",    lambda s, c, today=None: collect_hk_us_technical(s, hk_us_codes, today)),
                ("hk_us_fundamental",  lambda s, c, today=None: collect_hk_us_fundamental(s, hk_us_codes, today)),
                ("hk_us_heat",         lambda s, c, today=None: collect_hk_us_heat(s, hk_us_codes, today)),
                ("hk_us_news",         lambda s, c, today=None: collect_hk_us_news(s, hk_us_codes, today)),
            ]
            # 串行执行避免 yfinance 全局限流
            logger.info(">>> 港美股采集开始（串行）")
            t_hk = time.time()
            for name, fn in hk_us_collectors:
                _, timings[name] = _run(name, fn, None)
            timings["hk_us_collect_total"] = round(time.time() - t_hk, 1)

    # 评分（全量模式 或 未指定 --collect-only）
    if not args.collect_only:
        session = get_db_session()
        _, timings["scoring"] = _step("评分引擎", ScoreEngine().run, session, today=trade_date)
        session.close()

    _print_summary(trade_date, timings, t_total)


def _print_summary(trade_date, timings, t_total):
    total = round(time.time() - t_total, 1)
    print("\n" + "=" * 50)
    print(f"  同步完成  交易日={trade_date}  总耗时={total}s")
    print("-" * 50)
    for k, v in timings.items():
        print(f"  {k:<18} {v:>7.1f}s")
    print("=" * 50)


if __name__ == "__main__":
    main()
