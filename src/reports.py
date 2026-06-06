from __future__ import annotations

import html
from datetime import datetime
from zoneinfo import ZoneInfo

from .ai_analyze import analyze_news_row
from .config import ROOT_DIR, Settings
from .database import Database, dt_from_db, json_loads
from .email_sender import send_email
from .fetch_news import fetch_and_store
from .market_data import create_initial_snapshots, update_due_snapshots


REPORT_SUBJECTS = {
    "morning": "Global Market Morning Brief",
    "premarket": "US Market Pre-Market Brief",
    "weekly": "Weekly Review",
}


def _local_time(value: str, settings: Settings) -> str:
    parsed = dt_from_db(value)
    if not parsed:
        return value
    return parsed.astimezone(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d %H:%M %Z")


def _list_text(values: list[str]) -> str:
    return ", ".join(values) if values else "不确定/待观察"


def _snapshots_html(db: Database, news_id: int) -> str:
    rows = db.market_snapshots_for_news(news_id)
    if not rows:
        return "<p>暂无行情追踪数据。</p>"
    lines = [
        "<table><thead><tr><th>标的</th><th>事件价</th><th>1小时</th><th>1天</th><th>5天</th><th>20天</th></tr></thead><tbody>"
    ]
    for row in rows:
        def cell(label: str) -> str:
            price = row[f"price_{label}"]
            pct = row[f"pct_{label}"]
            if price is None:
                return "待观察"
            return f"{price:.2f} ({pct:+.2f}%)" if pct is not None else f"{price:.2f}"

        event = f"{row['event_price']:.2f}" if row["event_price"] is not None else "待获取"
        lines.append(
            "<tr>"
            f"<td>{html.escape(row['symbol'])}</td>"
            f"<td>{event}</td>"
            f"<td>{cell('1h')}</td>"
            f"<td>{cell('1d')}</td>"
            f"<td>{cell('5d')}</td>"
            f"<td>{cell('20d')}</td>"
            "</tr>"
        )
    lines.append("</tbody></table>")
    return "\n".join(lines)


def _news_block_html(row, db: Database, settings: Settings) -> str:
    facts = json_loads(row["confirmed_facts"], [])
    sectors = json_loads(row["affected_sectors"], [])
    etfs = json_loads(row["observed_etfs"], [])
    stocks = json_loads(row["observed_stocks"], [])
    uncertainties = json_loads(row["uncertainties"], [])
    fact_html = "".join(f"<li>{html.escape(fact)}</li>" for fact in facts) or "<li>未进行 AI 总结，请查看原始链接。</li>"
    uncertainty_html = "".join(f"<li>{html.escape(item)}</li>" for item in uncertainties) or "<li>待观察。</li>"

    return f"""
    <section>
      <h2>{html.escape(row['title'])}</h2>
      <p><b>来源：</b>{html.escape(row['source'])}<br>
      <b>发布时间：</b>{html.escape(_local_time(row['published_at'], settings))}<br>
      <b>原始链接：</b><a href="{html.escape(row['url'])}">{html.escape(row['url'])}</a></p>

      <h3>已确认事实</h3>
      <ul>{fact_html}</ul>

      <h3>AI 分析</h3>
      <p>{html.escape(row['ai_analysis'] or '未进行 AI 分析。')}</p>

      <p><b>可能影响板块：</b>{html.escape(_list_text(sectors))}<br>
      <b>影响方向：</b>{html.escape(row['impact_direction'] or '不确定')}<br>
      <b>观察 ETF：</b>{html.escape(_list_text(etfs))}<br>
      <b>观察个股：</b>{html.escape(_list_text(stocks))}</p>

      <h3>为什么观察这些标的</h3>
      <p>{html.escape(row['observation_reason'] or '待观察。')}</p>

      <h3>不确定/待观察部分</h3>
      <ul>{uncertainty_html}</ul>

      <h3>市场表现追踪</h3>
      {_snapshots_html(db, row['id'])}

      <p><b>风险提示：</b>这不是投资建议，只是学习和观察。</p>
    </section>
    """


def _news_block_text(row, db: Database, settings: Settings) -> str:
    facts = json_loads(row["confirmed_facts"], []) or ["未进行 AI 总结，请查看原始链接。"]
    sectors = json_loads(row["affected_sectors"], [])
    etfs = json_loads(row["observed_etfs"], [])
    stocks = json_loads(row["observed_stocks"], [])
    uncertainties = json_loads(row["uncertainties"], []) or ["待观察。"]
    snapshots = db.market_snapshots_for_news(row["id"])
    snapshot_lines = []
    for snap in snapshots:
        snapshot_lines.append(
            f"{snap['symbol']}: event={snap['event_price']}, 1h={snap['pct_1h']}%, "
            f"1d={snap['pct_1d']}%, 5d={snap['pct_5d']}%, 20d={snap['pct_20d']}%"
        )
    return f"""
【{row['title']}】

来源：{row['source']}
发布时间：{_local_time(row['published_at'], settings)}
原始链接：{row['url']}

已确认事实：
{chr(10).join('- ' + fact for fact in facts)}

AI 分析：
{row['ai_analysis'] or '未进行 AI 分析。'}

可能影响板块：{_list_text(sectors)}
影响方向：{row['impact_direction'] or '不确定'}
观察 ETF：{_list_text(etfs)}
观察个股：{_list_text(stocks)}

为什么观察这些标的：
{row['observation_reason'] or '待观察。'}

不确定/待观察部分：
{chr(10).join('- ' + item for item in uncertainties)}

市场表现追踪：
{chr(10).join(snapshot_lines) if snapshot_lines else '暂无行情追踪数据。'}

风险提示：
这不是投资建议，只是学习和观察。
""".strip()


def analyze_due_news(settings: Settings, db: Database) -> int:
    analysis_lookback_hours = max(settings.report_lookback_hours, 24 * 7)
    analysis_limit = max(settings.max_report_items, 20)
    rows = db.high_score_unanalyzed(
        settings.min_ai_score,
        analysis_lookback_hours,
        analysis_limit,
        retry_missing_key_fallbacks=True,
    )
    analyzed = 0
    for row in rows:
        analysis = analyze_news_row(row, settings)
        db.update_ai_analysis(row["id"], analysis)
        refreshed = db.top_news_for_report(settings.report_lookback_hours, settings.max_report_items * 2)
        refreshed_row = next((item for item in refreshed if item["id"] == row["id"]), None)
        if refreshed_row:
            create_initial_snapshots(db, refreshed_row)
        analyzed += 1
    return analyzed


def build_daily_report(report_type: str, settings: Settings, db: Database) -> tuple[str, str, str, list[int]]:
    subject = REPORT_SUBJECTS[report_type]
    rows = db.top_news_for_report(settings.report_lookback_hours, settings.max_report_items)
    now_local = datetime.now(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d %H:%M %Z")
    item_ids = [row["id"] for row in rows]
    if not rows:
        body = "过去观察窗口内没有来自可靠 RSS/API 来源的新闻记录。系统不会编造新闻。"
        return subject, f"<p>{html.escape(body)}</p>", body, item_ids

    html_blocks = "\n".join(_news_block_html(row, db, settings) for row in rows)
    text_blocks = "\n\n---\n\n".join(_news_block_text(row, db, settings) for row in rows)
    html_doc = f"""
    <html>
    <head>
      <meta charset="utf-8">
      <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.5; color: #111827; }}
        section {{ border-top: 1px solid #d1d5db; padding: 18px 0; }}
        h1 {{ font-size: 22px; }}
        h2 {{ font-size: 18px; }}
        h3 {{ font-size: 15px; margin-bottom: 6px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #d1d5db; padding: 6px; text-align: left; }}
      </style>
    </head>
    <body>
      <h1>{html.escape(subject)}</h1>
      <p>生成时间：{html.escape(now_local)}</p>
      <p>本邮件只用于投资学习和观察；新闻均来自已配置 RSS/API 来源，AI 不负责生成新闻事实。</p>
      {html_blocks}
    </body>
    </html>
    """
    text_doc = f"{subject}\n生成时间：{now_local}\n\n{text_blocks}"
    return subject, html_doc, text_doc, item_ids


def build_weekly_report(settings: Settings, db: Database) -> tuple[str, str, str, list[int]]:
    rows = db.weekly_news(limit=10)
    subject = REPORT_SUBJECTS["weekly"]
    item_ids = [row["id"] for row in rows]
    if not rows:
        body = "本周没有可复盘的可靠新闻记录。系统不会编造新闻。"
        return subject, f"<p>{html.escape(body)}</p>", body, item_ids

    sections = []
    text_sections = []
    for row in rows:
        snapshots = db.market_snapshots_for_news(row["id"])
        moves = []
        for snap in snapshots:
            available = [snap[key] for key in ("pct_1h", "pct_1d", "pct_5d", "pct_20d") if snap[key] is not None]
            if available:
                moves.append(f"{snap['symbol']} 已有表现记录：{available}")
        conclusion = "市场反应仍需观察。"
        if moves:
            conclusion = "已有部分行情数据，可对照 AI 判断方向复盘。"
        sections.append(
            f"""
            <section>
              <h2>{html.escape(row['title'])}</h2>
              <p><b>来源：</b>{html.escape(row['source'])}<br>
              <b>发布时间：</b>{html.escape(_local_time(row['published_at'], settings))}<br>
              <b>AI 当时判断：</b>{html.escape(row['impact_direction'] or '不确定')}</p>
              {_snapshots_html(db, row['id'])}
              <p><b>复盘判断：</b>{html.escape(conclusion)}</p>
            </section>
            """
        )
        text_sections.append(
            f"{row['title']}\n来源：{row['source']}\nAI 当时判断：{row['impact_direction'] or '不确定'}\n复盘：{conclusion}"
        )

    learning = (
        "新手复盘重点：先看新闻是否来自权威来源，再看市场反应是否持续；"
        "如果 1天、5天、20天表现没有延续，可能说明这条新闻只是短期噪音或已被市场提前定价。"
    )
    html_doc = f"<html><body><h1>{subject}</h1>{''.join(sections)}<h2>学习总结</h2><p>{html.escape(learning)}</p></body></html>"
    text_doc = f"{subject}\n\n" + "\n\n---\n\n".join(text_sections) + f"\n\n学习总结：{learning}"
    return subject, html_doc, text_doc, item_ids


def run_report(report_type: str, settings: Settings, db: Database) -> dict[str, object]:
    db.init()
    fetch_result = fetch_and_store(settings, db)
    analyzed = analyze_due_news(settings, db)
    tracked = update_due_snapshots(db)

    if report_type == "weekly":
        subject, html_doc, text_doc, item_ids = build_weekly_report(settings, db)
    else:
        subject, html_doc, text_doc, item_ids = build_daily_report(report_type, settings, db)

    send_result = send_email(settings, subject, html_doc, text_doc)
    db.record_sent_report(report_type, subject, item_ids, bool(send_result.get("dry_run")))
    return {
        "report_type": report_type,
        "fetch": fetch_result,
        "analyzed": analyzed,
        "tracked": tracked,
        "items": len(item_ids),
        "send": send_result,
        "database": str(settings.sqlite_path),
        "outputs": str(ROOT_DIR / "outputs"),
    }
