import logging
from datetime import date
from backend.scorers.technical import TechnicalScorer
from backend.scorers.capital import CapitalScorer
from backend.scorers.fundamental import FundamentalScorer
from backend.scorers.news import NewsScorer
from backend.scorers.market_heat import HeatScorer
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

    def score_stock(self, data: dict, universe: list, strategy) -> dict:
        """Score a single stock across all dimensions. data/universe items can be dicts or ORM objects."""
        stats = self._build_universe_stats(universe)
        d = data if isinstance(data, dict) else data.__dict__

        t = self.technical.score(d)
        c = self.capital.score(d, stats)
        f = self.fundamental.score(d, stats)
        n = self.news.score(d)
        h = self.heat.score(d, stats)
        total = (
            t * strategy.technical_weight +
            c * strategy.capital_weight +
            f * strategy.fundamental_weight +
            n * strategy.news_weight +
            h * strategy.heat_weight
        )
        return {
            "technical_score": round(t, 2),
            "capital_score": round(c, 2),
            "fundamental_score": round(f, 2),
            "news_score": round(n, 2),
            "heat_score": round(h, 2),
            "total_score": round(total, 2),
        }

    def run(self, session):
        """Score all stocks for today across all strategies. Returns count of score records written."""
        today = date.today().isoformat()
        records = session.query(DailyData).filter(DailyData.date == today).all()
        if not records:
            logger.warning(f"No daily data for {today}")
            return 0

        universe = [r.__dict__ for r in records]
        strategies = session.query(Strategy).all()
        scored = 0

        for strategy in strategies:
            for record in records:
                scores = self.score_stock(record, universe, strategy)
                score_record = {
                    "code": record.code, "date": today, "strategy": strategy.name,
                    **scores,
                }
                upsert(session, Score, score_record, ["code", "date", "strategy"])
                scored += 1

        session.commit()
        logger.info(f"Scoring complete: {scored} records")
        return scored
