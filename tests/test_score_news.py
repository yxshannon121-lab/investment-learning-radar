from datetime import UTC, datetime

from src.models import NewsItem
from src.score_news import score_item


def item(title: str, source: str = "Federal Reserve") -> NewsItem:
    return NewsItem(
        title=title,
        source=source,
        url="https://example.com/news",
        published_at=datetime(2026, 1, 1, tzinfo=UTC),
        raw_summary="",
    )


def test_authoritative_source_and_keyword_raise_score():
    scored = score_item(item("Federal Reserve discusses inflation and interest rate outlook"))
    assert scored.score >= 12
    assert any("source:Federal Reserve" in reason for reason in scored.reasons)
    assert any("keyword:inflation" in reason for reason in scored.reasons)


def test_lower_priority_source_scores_lower_without_keywords():
    scored = score_item(item("Company announces routine product update", source="Cointelegraph"))
    assert scored.score < 3

