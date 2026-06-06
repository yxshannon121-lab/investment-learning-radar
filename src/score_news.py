from __future__ import annotations

from collections import Counter

from .deduplicate import title_similarity
from .models import NewsItem, ScoredNews


SOURCE_WEIGHTS = {
    "Federal Reserve": 5,
    "European Central Bank": 5,
    "SEC": 4,
    "White House": 4,
    "US Treasury": 4,
    "IMF": 4,
    "World Bank": 4,
    "NATO": 4,
    "Associated Press": 3,
    "Reuters": 3,
    "Financial Times": 3,
    "CNBC": 2,
    "Yahoo Finance": 2,
    "MarketWatch": 2,
    "CoinDesk": 2,
    "Cointelegraph": 1.5,
}

KEYWORD_WEIGHTS = {
    "federal reserve": 4,
    "fed": 3,
    "ecb": 4,
    "inflation": 3,
    "cpi": 3,
    "interest rate": 4,
    "rate cut": 4,
    "tariff": 3,
    "sanctions": 3,
    "war": 3,
    "china": 2,
    "taiwan": 3,
    "trump": 2,
    "nvidia": 3,
    "tesla": 3,
    "ai": 2,
    "semiconductor": 3,
    "bitcoin": 3,
    "ethereum": 3,
    "oil": 3,
    "energy": 2,
    "earnings": 2,
    "guidance": 2,
}


def score_item(item: NewsItem, recent_items: list[NewsItem] | None = None) -> ScoredNews:
    text = f"{item.title} {item.raw_summary} {item.raw_content}".lower()
    score = SOURCE_WEIGHTS.get(item.source, 1.0)
    reasons = [f"source:{item.source}={score:g}"]

    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in text:
            score += weight
            reasons.append(f"keyword:{keyword}=+{weight:g}")

    if recent_items:
        similar_sources = {
            other.source
            for other in recent_items
            if other.source != item.source and title_similarity(item.title, other.title) >= 0.72
        }
        if similar_sources:
            bonus = min(3, len(similar_sources))
            score += bonus
            reasons.append(f"multi_source_bonus:{','.join(sorted(similar_sources))}=+{bonus:g}")

    return ScoredNews(item=item, score=score, reasons=reasons)


def score_batch(items: list[NewsItem]) -> list[ScoredNews]:
    title_counts = Counter(item.title.lower().strip() for item in items)
    scored: list[ScoredNews] = []
    for item in items:
        peers = [other for other in items if other is not item]
        result = score_item(item, peers)
        if title_counts[item.title.lower().strip()] > 1:
            result.score += 1
            result.reasons.append("same_title_seen_multiple_times=+1")
        scored.append(result)
    return sorted(scored, key=lambda item: item.score, reverse=True)

