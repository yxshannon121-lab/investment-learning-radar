from datetime import UTC, datetime

from src.rule_analyze import analyze_news_row_rules


class Row(dict):
    def __getitem__(self, key):
        return self.get(key)


def row(title: str, summary: str = "") -> Row:
    return Row(
        title=title,
        source="测试来源",
        url="https://example.com/news",
        published_at=datetime(2026, 1, 1, tzinfo=UTC).isoformat(),
        raw_summary=summary,
        raw_content="",
    )


def test_semiconductor_rule_maps_to_expected_assets():
    analysis = analyze_news_row_rules(row("Nvidia and AMD chip demand rises"))
    assert "半导体" in analysis.affected_sectors
    assert "SOXX" in analysis.observed_etfs
    assert "NVDA" in analysis.observed_stocks
    assert analysis.title_zh


def test_macro_rule_maps_to_rates_assets():
    analysis = analyze_news_row_rules(row("Federal Reserve watches CPI and interest rate outlook"))
    assert "银行" in analysis.affected_sectors
    assert "TLT" in analysis.observed_etfs
    assert analysis.impact_direction in {"利好", "利空", "中性", "不确定"}

