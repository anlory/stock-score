import logging
from datetime import date
from backend.scorers.technical import TechnicalScorer
from backend.scorers.capital import CapitalScorer
from backend.scorers.fundamental import FundamentalScorer
from backend.scorers.news import NewsScorer
from backend.scorers.market_heat import HeatScorer
from backend.scorers.setup import SetupScorer
from backend.database import upsert
from backend.models import Score, Strategy, DailyData, Stock

logger = logging.getLogger(__name__)

_A_SHARE_MARKETS = {"SH", "SZ", "BJ"}


class ScoreEngine:
    def __init__(self):
        self.technical = TechnicalScorer()
        self.capital = CapitalScorer()
        self.fundamental = FundamentalScorer()
        self.news = NewsScorer()
        self.heat = HeatScorer()
        self.setup = SetupScorer()

    def _build_universe_stats(self, records: list) -> dict:
        fields = [
            "main_inflow_today", "main_inflow_5d", "super_large_inflow",
            "pe", "pb", "roe", "profit_growth_yoy", "change_pct", "turnover_rate",
        ]
        stats = {f: [] for f in fields}
        for r in records:
            d = r if isinstance(r, dict) else r.__dict__
            for f in fields:
                v = d.get(f)
                if v is not None:
                    try:
                        stats[f].append(float(v))
                    except (TypeError, ValueError):
                        pass
        return stats

    def _dimension_scores(self, data, universe: list, market: str = None) -> dict:
        stats = self._build_universe_stats(universe)
        d = data if isinstance(data, dict) else data.__dict__

        # Detect market from data if not provided
        if market is None:
            market = d.get("market", "")

        # Attach market so scorers can see it
        d["market"] = market

        capital_score = self.capital.score(d, stats)
        # HK/US/ETF stocks have no capital flow data
        if market not in _A_SHARE_MARKETS:
            capital_score = 0.0

        return {
            "technical_score": self.technical.score(d),
            "capital_score": capital_score,
            "fundamental_score": self.fundamental.score(d, stats),
            "news_score": self.news.score(d),
            "heat_score": self.heat.score(d, stats),
            "setup_score": self.setup.score(d, stats),
        }

    def _redistribute_weights(self, strategy, market: str) -> dict:
        """Return weight dict, redistributing capital_weight for HK/US stocks."""
        weights = {
            "technical": strategy.technical_weight,
            "capital": strategy.capital_weight,
            "fundamental": strategy.fundamental_weight,
            "news": strategy.news_weight,
            "heat": strategy.heat_weight,
            "setup": getattr(strategy, "setup_weight", 0) or 0,
        }
        if market not in _A_SHARE_MARKETS:
            # Redistribute capital_weight equally to technical and fundamental
            capital_w = weights["capital"]
            half = capital_w / 2
            weights["technical"] += half
            weights["fundamental"] += half
            weights["capital"] = 0.0
        # ETF gets no fundamental/news either
        if market == "ETF":
            fund_w = weights["fundamental"]
            news_w = weights["news"]
            weights["technical"] += fund_w * 0.6
            weights["heat"] += fund_w * 0.4
            weights["heat"] += news_w
            weights["fundamental"] = 0.0
            weights["news"] = 0.0
        return weights

    def _calc_total(self, dims: dict, strategy, market: str) -> float:
        """Calculate total score using market-aware weights."""
        weights = self._redistribute_weights(strategy, market)
        total = (
            dims["technical_score"] * weights["technical"] +
            dims["capital_score"] * weights["capital"] +
            dims["fundamental_score"] * weights["fundamental"] +
            dims["news_score"] * weights["news"] +
            dims["heat_score"] * weights["heat"] +
            dims["setup_score"] * weights["setup"]
        )
        return round(total, 2)

    def score_stock(self, data, universe: list, strategy, market: str = None) -> dict:
        """Score a single stock directly with raw dimension scores. Used by collect_single."""
        if market is None:
            d = data if isinstance(data, dict) else data.__dict__
            market = d.get("market", "")
        dims = self._dimension_scores(data, universe, market=market)
        total = self._calc_total(dims, strategy, market)
        return {**dims, "total_score": total}

    def run(self, session, today: str = None):
        """Score all stocks for today across all strategies. Returns count of score records written."""
        today = today or date.today().isoformat()
        records = session.query(DailyData).filter(DailyData.date == today).all()
        if not records:
            logger.warning(f"No daily data for {today}")
            return 0

        # Load Stock objects to get market info
        codes = [r.code for r in records]
        stock_map = {
            s.code: s for s in session.query(Stock).filter(Stock.code.in_(codes))
        }

        # Build separate universe pools by market type
        a_share_records = []
        hk_us_records = []
        etf_records = []
        for r in records:
            stock = stock_map.get(r.code)
            market = stock.market if stock else ""
            r_dict = r.__dict__
            r_dict["market"] = market
            if market == "ETF":
                etf_records.append(r_dict)
            elif market in _A_SHARE_MARKETS:
                a_share_records.append(r_dict)
            else:
                hk_us_records.append(r_dict)

        universe_a = [r if isinstance(r, dict) else r.__dict__ for r in a_share_records]
        universe_hk = [r if isinstance(r, dict) else r.__dict__ for r in hk_us_records]
        universe_etf = [r if isinstance(r, dict) else r.__dict__ for r in etf_records]

        strategies = session.query(Strategy).all()
        scored = 0

        for record in records:
            stock = stock_map.get(record.code)
            market = stock.market if stock else ""
            r_dict = record.__dict__
            r_dict["market"] = market

            # Use the correct universe pool for percentile ranking
            if market == "ETF":
                universe = universe_etf
            elif market in _A_SHARE_MARKETS:
                universe = universe_a
            else:
                universe = universe_hk

            dims = self._dimension_scores(record, universe, market=market)
            for strategy in strategies:
                total = self._calc_total(dims, strategy, market)
                score_record = {
                    "code": record.code, "date": today, "strategy": strategy.name,
                    "technical_score": dims["technical_score"],
                    "capital_score": dims["capital_score"],
                    "fundamental_score": dims["fundamental_score"],
                    "news_score": dims["news_score"],
                    "heat_score": dims["heat_score"],
                    "setup_score": dims["setup_score"],
                    "total_score": total,
                }
                upsert(session, Score, score_record, ["code", "date", "strategy"])
                scored += 1

        session.commit()
        logger.info(f"Scoring complete: {scored} records")
        return scored
