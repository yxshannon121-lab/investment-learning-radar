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
    "Financial Times Europe": 3,
    "CNBC": 2,
    "CNBC Markets": 2.5,
    "CNBC Economy": 2.5,
    "Yahoo Finance": 2,
    "MarketWatch": 2,
    "Investing.com": 1.5,
    "Investing.com Economy": 1.5,
    "Eurostat": 3,
    "European Commission": 3,
    "NASA": 3,
    "ESA": 3,
    "SpaceNews": 2.5,
    "Space.com": 2,
    "US Space Force": 3,
    "CoinDesk": 2,
    "Cointelegraph": 1.5,
}

KEYWORD_WEIGHTS = {
    "federal reserve": 4,
    "fomc": 4,
    "fed": 3,
    "ecb": 4,
    "europe": 2,
    "eurozone": 3,
    "inflation": 3,
    "cpi": 3,
    "jobs report": 3,
    "interest rate": 4,
    "rate cut": 4,
    "tariff": 3,
    "sanctions": 3,
    "war": 3,
    "russia": 2,
    "ukraine": 2,
    "nato": 3,
    "middle east": 3,
    "china": 2,
    "taiwan": 3,
    "trump": 2,
    "nvidia": 3,
    "amd": 3,
    "tsm": 3,
    "tsmc": 3,
    "asml": 3,
    "broadcom": 3,
    "blackwell": 4,
    "h100": 3,
    "h200": 3,
    "b200": 3,
    "ai datacenter": 4,
    "data center": 3,
    "cloud": 2,
    "inference": 2,
    "training": 2,
    "tesla": 3,
    "ai": 2,
    "semiconductor": 3,
    "chip": 3,
    "bitcoin": 3,
    "ethereum": 3,
    "crypto": 3,
    "stablecoin": 3,
    "oil": 3,
    "crude": 3,
    "opec": 3,
    "nuclear": 3,
    "smr": 3,
    "power grid": 3,
    "electricity demand": 3,
    "utility": 2,
    "data center power": 4,
    "spacex": 3,
    "starship": 3,
    "falcon 9": 3,
    "starlink": 3,
    "rocket lab": 3,
    "rklb": 3,
    "blue origin": 3,
    "satellite": 3,
    "launch": 2,
    "rocket": 3,
    "spacecraft": 3,
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
