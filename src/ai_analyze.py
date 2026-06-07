from __future__ import annotations

import json

from pydantic import ValidationError

from .config import Settings
from .database import json_loads
from .models import AIAnalysis
from .rule_analyze import analyze_news_row_rules


SYSTEM_PROMPT = """
你是投资学习助手，不是交易系统。你只能基于用户给出的新闻标题、来源、发布时间、原始链接和RSS摘要进行翻译、总结和影响分析。
硬性规则：
1. 禁止编造新闻事实、数字、人物表态、价格、公司动作或事件细节。
2. 原文没有的信息必须放到“不确定/待观察”中，不能写成已确认事实。
3. 必须明确区分已确认事实、AI分析、不确定部分。
4. 不提供投资建议，不给买卖指令。
5. title_zh 和 summary_zh 必须是中文，不要直接输出英文标题或英文摘要。
6. 输出必须是合法 JSON，不要 Markdown。
""".strip()


def _fallback_analysis(reason: str) -> AIAnalysis:
    analysis = AIAnalysis(
        confirmed_facts_zh=[reason],
        summary_zh=[reason],
        ai_analysis_zh="已切换到规则分析模式。",
        affected_sectors=[],
        impact_direction="不确定",
        observed_etfs=[],
        observed_stocks=[],
        observation_reason_zh="OpenAI 不可用时，系统使用免费规则库分析。",
        uncertainties_zh=["需要人工查看原文确认。"],
        analysis_method="规则分析",
    )
    return analysis


def analyze_news_row(row, settings: Settings) -> AIAnalysis:
    if not settings.openai_api_key:
        return analyze_news_row_rules(row, fetch_article=True)
    if not settings.enable_openai_analysis:
        return analyze_news_row_rules(row, fetch_article=True)

    payload = {
        "title": row["title"],
        "source": row["source"],
        "url": row["url"],
        "published_at": row["published_at"],
        "raw_summary": row["raw_summary"],
        "raw_content_excerpt": (row["raw_content"] or "")[:2500],
            "required_schema": {
                "title_zh": "中文新闻标题，不显示英文原题",
                "summary_zh": ["3到5条中文摘要，只基于原始标题和RSS摘要"],
                "content_zh": ["中文正文翻译段落；只能基于原始内容"],
                "content_status": "rss_content/rss_summary/article_page/unavailable",
                "confirmed_facts_zh": ["仅基于标题和RSS摘要确认的事实"],
                "ai_analysis_zh": "为什么可能影响市场；不能添加原文没有的事实",
            "affected_sectors": ["半导体", "AI", "能源", "银行", "军工", "加密货币", "消费", "医疗"],
            "impact_direction": "利好/利空/中性/不确定",
            "observed_etfs": ["SPY", "QQQ", "SOXX", "XLE", "XLF", "KRE", "ARKK", "GLD", "TLT", "BTC-USD"],
            "observed_stocks": ["NVDA", "AMD", "TSM", "ASML", "AAPL", "MSFT", "TSLA", "JPM", "XOM"],
            "observation_reason_zh": "为什么观察这些标的",
            "uncertainties_zh": ["待观察事项"],
            "risk_note_zh": "这不是投资建议，只是学习和观察。",
        },
    }

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.openai_api_key)
        response = client.chat.completions.create(
            model=settings.openai_model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        analysis = AIAnalysis.model_validate(parsed)
        analysis.analysis_method = "AI增强分析"
        if not analysis.title_zh or not analysis.summary_zh or not analysis.content_zh:
            rule_analysis = analyze_news_row_rules(row, fetch_article=True)
            analysis.title_zh = analysis.title_zh or rule_analysis.title_zh
            analysis.summary_zh = analysis.summary_zh or rule_analysis.summary_zh
            analysis.content_zh = analysis.content_zh or rule_analysis.content_zh
            analysis.content_status = analysis.content_status or rule_analysis.content_status
        return analysis
    except (ImportError, Exception, json.JSONDecodeError, ValidationError):
        return analyze_news_row_rules(row, fetch_article=True)


def row_list(row, key: str) -> list[str]:
    return json_loads(row[key], [])
