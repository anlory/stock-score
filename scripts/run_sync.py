"""
手动触发一次完整数据同步，打印各阶段耗时和结果。

用法:
    uv run python scripts/run_sync.py
    uv run python scripts/run_sync.py --date 2026-04-25   # 指定交易日
    uv run python scripts/run_sync.py --watchlist          # 仅同步自选股
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
    parser.add_argument("--watchlist", action="store_true", help="仅同步自选股，跳过 universe 全量同步")
    args = parser.parse_args()

    from backend.collectors.tushare_client import get_last_trade_date
    from backend.collectors.universe import sync_universe
    from backend.collectors.technical import collect_technical
    from backend.collectors.capital import collect_capital
    from backend.collectors.market_heat import collect_market_heat
    from backend.engine import ScoreEngine
    from backend.database import get_db_session
    from backend.models import Stock

    trade_date = args.date or get_last_trade_date()
    if not trade_date:
        logger.error("无法确定交易日，退出")
        return
    logger.info(f"交易日: {trade_date}  模式: {'仅自选股' if args.watchlist else '全量'}")

    t_total = time.time()
    timings: dict[str, float] = {}

    session = get_db_session()

    # 1. Universe / 股票池
    if args.watchlist:
        codes = {s.code for s in session.query(Stock).filter(Stock.is_watchlist == True).all()}
        logger.info(f"自选股: {len(codes)} 只")
    else:
        _, timings["universe"] = _step("Universe 同步", sync_universe, session, today=trade_date)
        codes = {s.code for s in session.query(Stock).all()}
        logger.info(f"股票池: {len(codes)} 只")
    session.close()

    # 2. 并行采集
    from concurrent.futures import ThreadPoolExecutor, as_completed

    collectors = [
        ("technical",   collect_technical),
        ("capital",     collect_capital),
        ("market_heat", collect_market_heat),
    ]

    def _run(name, fn):
        t = time.time()
        s = get_db_session()
        try:
            count = fn(s, codes, today=trade_date)
            elapsed = round(time.time() - t, 1)
            logger.info(f"<<< {name:12s} 完成  count={count}  耗时={elapsed}s")
            return name, elapsed
        except Exception as e:
            logger.error(f"[{name}] 失败: {e}", exc_info=True)
            return name, -1
        finally:
            s.close()

    logger.info(">>> 并行采集开始")
    t_collect = time.time()
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(_run, name, fn): name for name, fn in collectors}
        for f in as_completed(futures):
            name, elapsed = f.result()
            timings[name] = elapsed
    timings["collect_total"] = round(time.time() - t_collect, 1)

    # 3. 评分
    session = get_db_session()
    _, timings["scoring"] = _step("评分引擎", ScoreEngine().run, session, today=trade_date)
    session.close()

    # 汇总
    total = round(time.time() - t_total, 1)
    print("\n" + "=" * 50)
    print(f"  同步完成  交易日={trade_date}  总耗时={total}s")
    print("-" * 50)
    for k, v in timings.items():
        print(f"  {k:<18} {v:>7.1f}s")
    print("=" * 50)


if __name__ == "__main__":
    main()
