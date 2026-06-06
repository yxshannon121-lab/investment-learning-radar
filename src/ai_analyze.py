from __future__ import annotations

import json

from openai import OpenAI
from pydantic import ValidationError

from .config import Settings
from .database import json_loads
from .models import AIAnalysis


SYSTEM_PROMPT = """
你是投资学习助手，不是交易系统。你只能基于用户给出的新闻标题、来源、发布时间、原始链接和RSS摘要进行翻译、总结和影响分析。
硬性规则：
1. 禁止编造新闻事实、数字、人物表态、价格、公司动作或事件细节。
2. 原文没有的信息必须放到“不确定/待观察”中，不能写成已确认事实。
3. 必须明确区分已确认事实、AI分析、不确定部分。
4. 不提供投资建议，不给买卖指令。
5. 输出必须是合法 JSON，不要 Markdown。
""".strip()


def _fallback_analysis(reason: str) -> AIAnalysis:
    return AIAnalysis(
        confirmed_facts_zh=[reason],
        ai_analysis_zh="未进行 AI 影响分析。",
        affected_sectors=[],
        impact_direction="不确定",
        observed_etfs=[],
        observed_stocks=[],
        observation_reason_zh="缺少可靠分析输入或 API 配置，因此不列观察标的。",
        uncertainties_zh=["需要人工查看原文确认。"],
    )


def analyze_news_row(row, settings: Settings) -> AIAnalysis:
    if not settings.openai_api_key:
        return _fallback_analysis("未调用 AI：缺少 OPENAI_API_KEY。新闻事实请以原始链接为准。")

    payload = {
        "title": row["title"],
        "source": row["source"],
        "url": row["url"],
        "published_at": row["published_at"],
        "raw_summary": row["raw_summary"],
        "raw_content_excerpt": (row["raw_content"] or "")[:2500],
        "required_schema": {
            "confirmed_facts_zh": ["仅基于标题和RSS摘要确认的事实"],
            "ai_analysis_zh": "为什么可能影响市场；不能添加原文没有的事实",
            "affected_sectors": ["半导体", "AI", "能源", "银行", "军工", "加密货币", "消费", "医疗"],
            "impact_direction": "利好/利空/不确定",
            "observed_etfs": ["SPY", "QQQ", "SOXX", "XLE", "XLF", "KRE", "ARKK", "GLD", "TLT", "BTC-USD"],
            "observed_stocks": ["NVDA", "AMD", "TSM", "ASML", "AAPL", "MSFT", "TSLA", "JPM", "XOM"],
            "observation_reason_zh": "为什么观察这些标的",
            "uncertainties_zh": ["待观察事项"],
            "risk_note_zh": "这不是投资建议，只是学习和观察。",
        },
    }

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
    try:
        parsed = json.loads(content)
        return AIAnalysis.model_validate(parsed)
    except (json.JSONDecodeError, ValidationError) as exc:
        return _fallback_analysis(f"AI 返回格式无法验证：{exc}")


def row_list(row, key: str) -> list[str]:
    return json_loads(row[key], [])

