import logging
from datetime import date
from backend.scorers.technical import TechnicalScorer
from backend.scorers.capital import CapitalScorer
from backend.scorers.fundamental import FundamentalScorer
from backend.scorers.news import NewsScorer
from backend.scorers.market_heat import HeatScorer
from backend.scorers.setup import SetupScorer
from backend.database import upsert
from backend.models import Score, Strategy, DailyData

logger = logging.getLogger(__name__)


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

    def _dimension_scores(self, data, universe: list) -> dict:
        stats = self._build_universe_stats(universe)
        d = data if isinstance(data, dict) else data.__dict__
        return {
            "technical_score": self.technical.score(d),
            "capital_score": self.capital.score(d, stats),
            "fundamental_score": self.fundamental.score(d, stats),
            "news_score": self.news.score(d),
            "heat_score": self.heat.score(d, stats),
            "setup_score": self.setup.score(d, stats),
        }

    def score_stock(self, data, universe: list, strategy) -> dict:
        """Score a single stock directly with raw dimension scores. Used by collect_single."""
        dims = self._dimension_scores(data, universe)
        total = (
            dims["technical_score"] * strategy.technical_weight +
            dims["capital_score"] * strategy.capital_weight +
            dims["fundamental_score"] * strategy.fundamental_weight +
            dims["news_score"] * strategy.news_weight +
            dims["heat_score"] * strategy.heat_weight +
            dims["setup_score"] * getattr(strategy, "setup_weight", 0)
        )
        return {**dims, "total_score": round(total, 2)}

    def run(self, session, today: str = None):
        """Score all stocks for today across all strategies. Returns count of score records written."""
        today = today or date.today().isoformat()
        records = session.query(DailyData).filter(DailyData.date == today).all()
        if not records:
            logger.warning(f"No daily data for {today}")
            return 0

        universe = [r.__dict__ for r in records]
        strategies = session.query(Strategy).all()
        scored = 0

        for record in records:
            dims = self._dimension_scores(record, universe)
            for strategy in strategies:
                total = (
                    dims["technical_score"] * strategy.technical_weight +
                    dims["capital_score"] * strategy.capital_weight +
                    dims["fundamental_score"] * strategy.fundamental_weight +
                    dims["news_score"] * strategy.news_weight +
                    dims["heat_score"] * strategy.heat_weight +
                    dims["setup_score"] * getattr(strategy, "setup_weight", 0)
                )
                score_record = {
                    "code": record.code, "date": today, "strategy": strategy.name,
                    "technical_score": dims["technical_score"],
                    "capital_score": dims["capital_score"],
                    "fundamental_score": dims["fundamental_score"],
                    "news_score": dims["news_score"],
                    "heat_score": dims["heat_score"],
                    "setup_score": dims["setup_score"],
                    "total_score": round(total, 2),
                }
                upsert(session, Score, score_record, ["code", "date", "strategy"])
                scored += 1

        session.commit()
        logger.info(f"Scoring complete: {scored} records")
        return scored
