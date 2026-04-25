import logging
from datetime import date
from backend.scorers.technical import TechnicalScorer
from backend.scorers.capital import CapitalScorer
from backend.scorers.fundamental import FundamentalScorer
from backend.scorers.news import NewsScorer
from backend.scorers.market_heat import HeatScorer
from backend.scorers.base import percentile_score
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

    def _dimension_scores(self, data, universe: list) -> dict:
        """Compute raw dimension scores for a single stock."""
        stats = self._build_universe_stats(universe)
        d = data if isinstance(data, dict) else data.__dict__
        return {
            "technical_score": self.technical.score(d),
            "capital_score": self.capital.score(d, stats),
            "fundamental_score": self.fundamental.score(d, stats),
            "news_score": self.news.score(d),
            "heat_score": self.heat.score(d, stats),
        }

    def score_stock(self, data, universe: list, strategy) -> dict:
        """Score a single stock with percentile ranking against a universe. Used by collect_single."""
        dims = self._dimension_scores(data, universe)
        # Build lists for percentile — with single stock in universe, percentile defaults to 50
        all_vals = {k: [v] for k, v in dims.items()}
        pcts = {k.replace("_score", "_pct"): percentile_score(v, vs) for k, v, vs in
                ((k, v, [v]) for k, v in dims.items())}
        total = (
            pcts["technical_pct"] * strategy.technical_weight +
            pcts["capital_pct"] * strategy.capital_weight +
            pcts["fundamental_pct"] * strategy.fundamental_weight +
            pcts["news_pct"] * strategy.news_weight +
            pcts["heat_pct"] * strategy.heat_weight
        )
        return {
            "technical_score": pcts["technical_pct"],
            "capital_score": pcts["capital_pct"],
            "fundamental_score": pcts["fundamental_pct"],
            "news_score": pcts["news_pct"],
            "heat_score": pcts["heat_pct"],
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

        # Step 1: compute raw dimension scores for all stocks
        raw_scores = []
        for record in records:
            dim = self._dimension_scores(record, universe)
            raw_scores.append({"code": record.code, **dim})

        # Step 2: percentile rank each dimension
        tech_all = [s["technical_score"] for s in raw_scores]
        cap_all = [s["capital_score"] for s in raw_scores]
        fund_all = [s["fundamental_score"] for s in raw_scores]
        news_all = [s["news_score"] for s in raw_scores]
        heat_all = [s["heat_score"] for s in raw_scores]

        for s in raw_scores:
            s["technical_pct"] = percentile_score(s["technical_score"], tech_all)
            s["capital_pct"] = percentile_score(s["capital_score"], cap_all)
            s["fundamental_pct"] = percentile_score(s["fundamental_score"], fund_all)
            s["news_pct"] = percentile_score(s["news_score"], news_all)
            s["heat_pct"] = percentile_score(s["heat_score"], heat_all)

        # Step 3: compute per-strategy totals using percentile scores
        strategies = session.query(Strategy).all()
        scored = 0
        pct_map = {s["code"]: s for s in raw_scores}

        for strategy in strategies:
            for record in records:
                p = pct_map[record.code]
                total = (
                    p["technical_pct"] * strategy.technical_weight +
                    p["capital_pct"] * strategy.capital_weight +
                    p["fundamental_pct"] * strategy.fundamental_weight +
                    p["news_pct"] * strategy.news_weight +
                    p["heat_pct"] * strategy.heat_weight
                )
                score_record = {
                    "code": record.code, "date": today, "strategy": strategy.name,
                    "technical_score": p["technical_pct"],
                    "capital_score": p["capital_pct"],
                    "fundamental_score": p["fundamental_pct"],
                    "news_score": p["news_pct"],
                    "heat_score": p["heat_pct"],
                    "total_score": round(total, 2),
                }
                upsert(session, Score, score_record, ["code", "date", "strategy"])
                scored += 1

        session.commit()
        logger.info(f"Scoring complete: {scored} records")
        return scored
