from __future__ import annotations

import re
from dataclasses import dataclass

from .article_extractor import best_available_text
from .models import AIAnalysis
from .translation_utils import TRANSLATION_FALLBACK, clean_text, split_paragraphs, translate_paragraphs, translate_title


RISK_NOTE = "本页面仅用于投资学习和信息整理，不构成任何投资建议。市场有风险，投资需谨慎。"


@dataclass(frozen=True)
class Rule:
    name_zh: str
    keywords: tuple[str, ...]
    sectors: tuple[str, ...]
    etfs: tuple[str, ...]
    stocks: tuple[str, ...]
    direction: str
    reason: str


RULES = [
    Rule(
        name_zh="美联储、通胀与利率",
        keywords=("federal reserve", "fed", "fomc", "cpi", "inflation", "rate cut", "interest rate", "jobs report"),
        sectors=("科技", "银行", "债券"),
        etfs=("SPY", "QQQ", "XLF", "TLT"),
        stocks=("AAPL", "MSFT", "JPM", "BAC"),
        direction="不确定",
        reason="利率和通胀会影响估值、融资成本、银行净息差和债券价格，需要观察市场对政策预期的重新定价。",
    ),
    Rule(
        name_zh="半导体与人工智能",
        keywords=("nvidia", "amd", "tsm", "asml", "semiconductor", "chip", "gpu"),
        sectors=("半导体", "AI"),
        etfs=("SOXX", "SMH", "QQQ"),
        stocks=("NVDA", "AMD", "TSM", "ASML"),
        direction="不确定",
        reason="芯片和AI相关消息常影响半导体链条、成长股风险偏好和纳斯达克权重股表现。",
    ),
    Rule(
        name_zh="AI算力与数据中心",
        keywords=(
            "nvidia",
            "amd",
            "tsmc",
            "asml",
            "broadcom",
            "blackwell",
            "h100",
            "h200",
            "b200",
            "ai datacenter",
            "data center",
            "cloud",
            "inference",
            "training",
            "liquid cooling",
        ),
        sectors=("AI", "半导体", "云计算", "数据中心"),
        etfs=("SOXX", "SMH", "QQQ", "IGV"),
        stocks=("NVDA", "AMD", "AVGO", "TSM", "ASML", "MSFT", "AMZN", "META", "SMCI", "DELL"),
        direction="不确定",
        reason="AI算力、GPU和数据中心消息会影响芯片需求、云厂商资本开支、服务器供应链和科技股估值。",
    ),
    Rule(
        name_zh="原油与能源",
        keywords=("oil", "crude", "opec", "energy"),
        sectors=("能源",),
        etfs=("XLE", "USO"),
        stocks=("XOM", "CVX", "SHEL"),
        direction="不确定",
        reason="油价和供需变化会影响能源企业盈利、通胀预期和部分周期行业成本。",
    ),
    Rule(
        name_zh="加密货币",
        keywords=("bitcoin", "ethereum", "crypto", "stablecoin"),
        sectors=("加密货币",),
        etfs=("BTC-USD", "ETH-USD"),
        stocks=("COIN", "MSTR", "MARA", "RIOT"),
        direction="不确定",
        reason="加密资产消息会影响数字资产价格、交易平台和持有加密资产公司的股价波动。",
    ),
    Rule(
        name_zh="关税、制裁与中美风险",
        keywords=("tariff", "sanctions", "china", "taiwan"),
        sectors=("半导体", "工业", "出口"),
        etfs=("SOXX", "QQQ", "FXI", "KWEB"),
        stocks=("NVDA", "AMD", "TSM", "AAPL", "BABA"),
        direction="不确定",
        reason="贸易限制和地缘政治会影响供应链、出口需求、科技硬件和中国资产风险溢价。",
    ),
    Rule(
        name_zh="战争与地缘冲突",
        keywords=("war", "russia", "ukraine", "nato", "middle east"),
        sectors=("军工", "能源", "黄金"),
        etfs=("ITA", "XLE", "GLD"),
        stocks=("LMT", "RTX", "XOM", "CVX"),
        direction="不确定",
        reason="冲突风险通常会影响避险资产、能源价格、军工订单预期和市场风险偏好。",
    ),
    Rule(
        name_zh="航天与空间技术",
        keywords=(
            "spacex",
            "starship",
            "falcon 9",
            "starlink",
            "rocket lab",
            "rklb",
            "blue origin",
            "satellite",
            "launch",
            "rocket",
            "spacecraft",
            "space force",
        ),
        sectors=("航天", "卫星", "军工航天"),
        etfs=("UFO", "ITA"),
        stocks=("RKLB", "LMT", "RTX", "NOC", "BA", "PL"),
        direction="不确定",
        reason="航天发射、卫星网络和军工航天消息会影响商业航天、国防承包商和空间基础设施相关公司。",
    ),
    Rule(
        name_zh="电力与能源基础设施",
        keywords=(
            "nuclear",
            "smr",
            "power grid",
            "electricity demand",
            "utility",
            "data center power",
            "energy infrastructure",
        ),
        sectors=("核电", "电网", "能源基础设施", "数据中心供电"),
        etfs=("XLU", "XLE"),
        stocks=("CEG", "VST", "NEE", "OKLO", "SMR", "XOM", "CVX"),
        direction="不确定",
        reason="AI数据中心和电力需求增长会影响公用事业、核电、电网投资和能源基础设施公司。",
    ),
    Rule(
        name_zh="欧洲央行与欧洲市场",
        keywords=("ecb", "europe", "eurozone"),
        sectors=("欧洲银行", "欧洲市场"),
        etfs=("VGK", "FEZ", "EUFN"),
        stocks=("ASML", "SAP", "DB", "BNP"),
        direction="不确定",
        reason="欧洲利率、经济和政策变化会影响欧洲银行、欧股指数和大型欧洲公司估值。",
    ),
]


POSITIVE_WORDS = ("beats", "beat", "surge", "rises", "rise", "gain", "gains", "approval", "record", "growth")
NEGATIVE_WORDS = ("misses", "miss", "falls", "fall", "drops", "drop", "warning", "cuts", "lawsuit", "probe", "risk")


def _text(row) -> str:
    return f"{row['title']} {row['raw_summary'] or ''} {row['raw_content'] or ''}".lower()


def matched_rules(row) -> list[Rule]:
    text = _text(row)
    return [rule for rule in RULES if any(keyword in text for keyword in rule.keywords)]


def _unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _direction(row, rules: list[Rule]) -> str:
    text = _text(row)
    positive = any(word in text for word in POSITIVE_WORDS)
    negative = any(word in text for word in NEGATIVE_WORDS)
    if positive and not negative:
        return "利好"
    if negative and not positive:
        return "利空"
    if rules:
        return "不确定"
    return "中性"


def _title_zh(row, rules: list[Rule]) -> str:
    return translate_title(row["title"])


def _summary_zh(row, rules: list[Rule]) -> list[str]:
    title = translate_title(row["title"])
    if title:
        return [title]
    return ["该来源未提供可翻译摘要，请点击原文链接查看。"]


def _translated_summary(row, rules: list[Rule]) -> list[str]:
    source_text = clean_text(row["raw_summary"] or row["raw_content"] or "")
    translated = translate_paragraphs(split_paragraphs(source_text, max_paragraphs=3), max_chars=1600)
    if translated:
        return translated[:3]
    if source_text:
        return [TRANSLATION_FALLBACK]
    title_summary = _summary_zh(row, rules)
    return title_summary[:1]


def _translated_content(row, fetch_article: bool) -> tuple[list[str], str]:
    if not fetch_article:
        return [], "not_fetched"
    source_text, source = best_available_text(row)
    paragraphs = split_paragraphs(source_text, max_paragraphs=80)
    if not paragraphs:
        return [], source
    translated = translate_paragraphs(paragraphs)
    if translated:
        return translated, source
    summary_translation = translate_paragraphs(paragraphs[:3], max_chars=1800)
    if summary_translation:
        return summary_translation, f"{source}_summary_only"
    return [], "translation_failed"


def _uncertainties(row, rules: list[Rule]) -> list[str]:
    items = ["实际市场影响需要等待价格数据验证。"]
    if not row["raw_summary"]:
        items.append("RSS源未提供摘要，具体新闻细节需要查看原文。")
    if not rules:
        items.append("未匹配到核心关键词，板块和标的影响不明确。")
    return items


def analyze_news_row_rules(row, fetch_article: bool = False) -> AIAnalysis:
    rules = matched_rules(row)
    sectors = _unique([sector for rule in rules for sector in rule.sectors])
    etfs = _unique([etf for rule in rules for etf in rule.etfs])
    stocks = _unique([stock for rule in rules for stock in rule.stocks])
    if not rules:
        sectors = ["综合市场"]
        etfs = ["SPY", "QQQ"]
        stocks = []

    reasons = [rule.reason for rule in rules]
    if not reasons:
        reasons = ["未匹配到明确主题，先观察大盘ETF表现，避免过度解读单条新闻。"]

    summary = _translated_summary(row, rules)
    content_zh, content_status = _translated_content(row, fetch_article=fetch_article)
    return AIAnalysis(
        title_zh=_title_zh(row, rules),
        summary_zh=summary,
        content_zh=content_zh,
        content_status=content_status,
        confirmed_facts_zh=summary,
        ai_analysis_zh="；".join(reasons),
        affected_sectors=sectors,
        impact_direction=_direction(row, rules),
        observed_etfs=etfs,
        observed_stocks=stocks,
        observation_reason_zh="；".join(reasons),
        uncertainties_zh=_uncertainties(row, rules),
        analysis_method="规则分析",
        risk_note_zh=RISK_NOTE,
    )


def contains_latin_text(value: str) -> bool:
    return bool(re.search(r"[A-Za-z]{3,}", value))
