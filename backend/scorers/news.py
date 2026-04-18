from backend.scorers.base import clamp, safe_float

RATING_SCORE = {"买入": 40, "增持": 35, "中性": 20, "减持": 5, "卖出": 0}

class NewsScorer:
    def score(self, data: dict) -> float:
        total = 0.0
        count = data.get("report_count")
        if count:
            count = int(count)
            if count >= 5:   total += 30
            elif count >= 3: total += 20
            elif count >= 1: total += 10
        rating = str(data.get("report_rating") or "")
        total += RATING_SCORE.get(rating, 20)
        sentiment = safe_float(data.get("news_sentiment"))
        if sentiment is not None:
            if sentiment >= 0.7:   total += 30
            elif sentiment >= 0.5: total += 20
            elif sentiment >= 0.3: total += 10
        else:
            total += 15
        return float(clamp(total, 0, 100))
