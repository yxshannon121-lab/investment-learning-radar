from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import ROOT_DIR, Settings
from .database import Database, dt_from_db, json_loads
from .rule_analyze import RISK_NOTE, analyze_news_row_rules


DISCLAIMER = RISK_NOTE


def _local_time(value: str | None, settings: Settings) -> str:
    parsed = dt_from_db(value)
    if not parsed:
        return value or "未知"
    return parsed.astimezone(ZoneInfo(settings.timezone)).strftime("%Y-%m-%d %H:%M %Z")


def _list_text(values: list[str]) -> str:
    return "、".join(values) if values else "不确定/待观察"


def _pct(value) -> str:
    if value is None:
        return "待观察"
    return f"{float(value):+.2f}%"


def _price(value) -> str:
    if value is None:
        return "待获取"
    return f"{float(value):.2f}"


def _analysis_for_display(row) -> dict[str, object]:
    rule_fallback = analyze_news_row_rules(row)
    title_zh = row["title_zh"] or rule_fallback.title_zh
    summary_zh = json_loads(row["summary_zh"], []) or rule_fallback.summary_zh
    facts = json_loads(row["confirmed_facts"], []) or summary_zh
    sectors = json_loads(row["affected_sectors"], []) or rule_fallback.affected_sectors
    etfs = json_loads(row["observed_etfs"], []) or rule_fallback.observed_etfs
    stocks = json_loads(row["observed_stocks"], []) or rule_fallback.observed_stocks
    uncertainties = json_loads(row["uncertainties"], []) or rule_fallback.uncertainties_zh
    return {
        "title_zh": title_zh,
        "summary_zh": summary_zh,
        "facts": facts,
        "sectors": sectors,
        "etfs": etfs,
        "stocks": stocks,
        "uncertainties": uncertainties,
        "analysis": row["ai_analysis"] or rule_fallback.ai_analysis_zh,
        "direction": row["impact_direction"] or rule_fallback.impact_direction,
        "reason": row["observation_reason"] or rule_fallback.observation_reason_zh,
        "method": row["analysis_method"] or rule_fallback.analysis_method,
    }


def _market_table(db: Database, news_id: int) -> str:
    rows = db.market_snapshots_for_news(news_id)
    if not rows:
        return '<p class="muted">暂无行情追踪数据。价格必须来自真实行情数据源，不由系统猜测。</p>'
    body = []
    for row in rows:
        body.append(
            "<tr>"
            f"<td>{html.escape(row['symbol'])}</td>"
            f"<td>{html.escape(row['asset_type'])}</td>"
            f"<td>{_price(row['event_price'])}</td>"
            f"<td>{_pct(row['pct_1d'])}</td>"
            f"<td>{_pct(row['pct_5d'])}</td>"
            f"<td>{_pct(row['pct_20d'])}</td>"
            "</tr>"
        )
    return (
        '<div class="table-wrap"><table>'
        "<thead><tr><th>标的</th><th>类型</th><th>事件价格</th><th>1天后</th><th>5天后</th><th>20天后</th></tr></thead>"
        f"<tbody>{''.join(body)}</tbody></table></div>"
    )


def _news_card(row, db: Database, settings: Settings) -> str:
    display = _analysis_for_display(row)
    summary_items = "".join(f"<li>{html.escape(item)}</li>" for item in display["summary_zh"])
    uncertainty_items = "".join(f"<li>{html.escape(item)}</li>" for item in display["uncertainties"]) or "<li>待观察。</li>"

    return f"""
    <article class="news-card">
      <div class="card-head">
        <h3>{html.escape(str(display['title_zh']))}</h3>
        <span class="score">重要性 {float(row['score'] or 0):.1f}</span>
      </div>
      <dl class="meta">
        <div><dt>来源</dt><dd>{html.escape(row['source'])}</dd></div>
        <div><dt>发布时间</dt><dd>{html.escape(_local_time(row['published_at'], settings))}</dd></div>
        <div class="wide"><dt>原文链接</dt><dd><a href="{html.escape(row['url'])}" target="_blank" rel="noopener noreferrer">打开原文</a></dd></div>
      </dl>

      <section class="summary">
        <h4>新闻摘要（中文）</h4>
        <ul>{summary_items}</ul>
      </section>

      <div class="chips">
        <div><span>可能影响板块</span><b>{html.escape(_list_text(display['sectors']))}</b></div>
        <div><span>影响方向</span><b>{html.escape(str(display['direction']))}</b></div>
        <div><span>观察 ETF/资产</span><b>{html.escape(_list_text(display['etfs']))}</b></div>
        <div><span>观察个股</span><b>{html.escape(_list_text(display['stocks']))}</b></div>
      </div>

      <section>
        <h4>规则分析</h4>
        <p>{html.escape(str(display['analysis']))}</p>
      </section>

      <section>
        <h4>观察原因</h4>
        <p>{html.escape(str(display['reason']))}</p>
      </section>

      <section>
        <h4>不确定部分</h4>
        <ul>{uncertainty_items}</ul>
      </section>

      <section>
        <h4>1天、5天、20天后涨跌追踪</h4>
        {_market_table(db, row['id'])}
      </section>
    </article>
    """


def _section(title: str, description: str, rows, db: Database, settings: Settings) -> str:
    if not rows:
        content = '<p class="empty">当前窗口内没有来自可靠 RSS/API 来源的新闻记录。系统不会编造新闻。</p>'
    else:
        content = "\n".join(_news_card(row, db, settings) for row in rows)
    return f"""
    <section class="page-section" id="{html.escape(title)}">
      <div class="section-title">
        <h2>{html.escape(title)}</h2>
        <p>{html.escape(description)}</p>
      </div>
      {content}
    </section>
    """


def _weekly_review(rows, db: Database, settings: Settings) -> str:
    if not rows:
        return '<p class="empty">本周暂无可复盘的可靠新闻记录。</p>'
    items = []
    for row in rows:
        display = _analysis_for_display(row)
        snapshots = db.market_snapshots_for_news(row["id"])
        moves = [
            snap
            for snap in snapshots
            if snap["pct_1d"] is not None or snap["pct_5d"] is not None or snap["pct_20d"] is not None
        ]
        if not moves:
            review = "后续涨跌数据仍不足，暂不能判断影响是否明显。"
        else:
            visible = any(abs(float(snap["pct_1d"] or snap["pct_5d"] or snap["pct_20d"] or 0)) >= 2 for snap in moves)
            review = "已有较明显价格反应，适合复盘新闻与市场表现的关系。" if visible else "价格反应暂不明显，可能属于噪音或已被市场提前消化。"
        items.append(
            f"""
            <article class="review-item">
              <h3>{html.escape(str(display['title_zh']))}</h3>
              <p><b>当时分析：</b>{html.escape(str(display['direction']))}；{html.escape(str(display['reason']))}</p>
              <p><b>对应 ETF/资产：</b>{html.escape(_list_text(display['etfs']))}</p>
              <p><b>对应个股：</b>{html.escape(_list_text(display['stocks']))}</p>
              {_market_table(db, row['id'])}
              <p><b>复盘结论：</b>{html.escape(review)}</p>
            </article>
            """
        )
    return "".join(items)


def build_dashboard_html(settings: Settings, db: Database) -> str:
    now = datetime.now(ZoneInfo(settings.timezone))
    generated_at = now.strftime("%Y-%m-%d %H:%M %Z")
    daily_limit = settings.max_report_items
    morning_rows = db.top_news_for_report(settings.report_lookback_hours, daily_limit)
    premarket_rows = db.top_news_for_report(settings.report_lookback_hours, daily_limit)
    weekly_rows = db.weekly_news(limit=10)

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>中文投资学习雷达（免费版）</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f5f7fa;
      --panel: #ffffff;
      --text: #172033;
      --muted: #5c667a;
      --line: #d8dee9;
      --accent: #0f766e;
      --accent-soft: #e7f5f3;
      --warn: #8a4b00;
      --warn-soft: #fff4df;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }}
    header {{
      background: #ffffff;
      border-bottom: 1px solid var(--line);
    }}
    .wrap {{
      width: min(1160px, calc(100% - 32px));
      margin: 0 auto;
    }}
    .hero {{ padding: 28px 0 20px; }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(26px, 4vw, 38px);
      letter-spacing: 0;
    }}
    .subhead {{
      margin: 0;
      color: var(--muted);
      max-width: 820px;
    }}
    .notice {{
      margin-top: 18px;
      padding: 12px 14px;
      border: 1px solid #f1c987;
      background: var(--warn-soft);
      color: var(--warn);
      border-radius: 8px;
      font-weight: 700;
    }}
    nav {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      padding: 0 0 18px;
    }}
    nav a {{
      color: var(--accent);
      background: var(--accent-soft);
      border: 1px solid #b8dfd9;
      border-radius: 8px;
      padding: 8px 10px;
      text-decoration: none;
      font-weight: 700;
    }}
    main {{ padding: 22px 0 38px; }}
    .page-section {{ margin-bottom: 34px; }}
    .section-title {{ margin-bottom: 14px; }}
    .section-title h2 {{
      margin: 0 0 4px;
      font-size: 24px;
    }}
    .section-title p {{
      margin: 0;
      color: var(--muted);
    }}
    .news-card, .review-item {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      margin-bottom: 14px;
      box-shadow: 0 1px 2px rgba(23, 32, 51, 0.05);
    }}
    .card-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 10px;
    }}
    .card-head h3, .review-item h3 {{
      margin: 0 0 8px;
      font-size: 20px;
      line-height: 1.35;
    }}
    .score {{
      flex: 0 0 auto;
      background: #eef2ff;
      color: #3730a3;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 13px;
      font-weight: 700;
    }}
    .meta {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px 14px;
      margin: 0 0 14px;
      padding: 12px;
      background: #f9fafb;
      border-radius: 8px;
    }}
    .meta .wide {{ grid-column: 1 / -1; }}
    dt {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    dd {{
      margin: 2px 0 0;
      overflow-wrap: anywhere;
    }}
    a {{ color: #0b66c3; }}
    h4 {{
      margin: 12px 0 6px;
      font-size: 15px;
    }}
    p, ul {{ margin-top: 0; }}
    .summary ul {{ padding-left: 20px; }}
    .chips {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin: 12px 0;
    }}
    .chips div {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: #fcfdff;
    }}
    .chips span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
      margin-bottom: 4px;
    }}
    .chips b {{
      display: block;
      font-size: 14px;
      overflow-wrap: anywhere;
    }}
    .table-wrap {{
      overflow-x: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      min-width: 620px;
      background: #fff;
    }}
    th, td {{
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      white-space: nowrap;
    }}
    th {{
      background: #f9fafb;
      color: var(--muted);
      font-size: 12px;
    }}
    .muted, .empty {{ color: var(--muted); }}
    footer {{
      border-top: 1px solid var(--line);
      background: #ffffff;
      padding: 18px 0;
      color: var(--muted);
      font-size: 14px;
    }}
    @media (max-width: 820px) {{
      .chips, .meta {{ grid-template-columns: 1fr; }}
      .card-head {{ display: block; }}
      .score {{
        display: inline-block;
        margin-top: 8px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap hero">
      <h1>中文投资学习雷达（免费版）</h1>
      <p class="subhead">每天用中文整理真实财经新闻，观察新闻如何影响板块、ETF、个股和后续市场表现。生成时间：{html.escape(generated_at)}</p>
      <div class="notice">{DISCLAIMER}</div>
    </div>
    <nav class="wrap" aria-label="页面导航">
      <a href="#今日晨报">今日晨报</a>
      <a href="#美股盘前观察">美股盘前观察</a>
      <a href="#本周复盘">本周复盘</a>
    </nav>
  </header>
  <main class="wrap">
    {_section("今日晨报", "过去观察窗口内评分最高的全球市场新闻。", morning_rows, db, settings)}
    {_section("美股盘前观察", "美股开盘前重点观察的宏观、行业和公司新闻。", premarket_rows, db, settings)}
    <section class="page-section" id="本周复盘">
      <div class="section-title">
        <h2>本周复盘</h2>
        <p>本周重要新闻、当时分析、对应ETF和个股，以及后续涨跌是否明显。</p>
      </div>
      {_weekly_review(weekly_rows, db, settings)}
    </section>
  </main>
  <footer>
    <div class="wrap">
      {DISCLAIMER} 新闻事实来自RSS/API原始来源；规则分析只用于学习整理。禁止自动交易，禁止连接IBKR下单接口。
    </div>
  </footer>
</body>
</html>
"""


def write_dashboard(settings: Settings, db: Database, output_path: Path | None = None) -> Path:
    path = output_path or ROOT_DIR / "docs" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    html_doc = build_dashboard_html(settings, db)
    path.write_text(html_doc, encoding="utf-8")
    if output_path is None:
        (path.parent / "dashboard.html").write_text(html_doc, encoding="utf-8")
    return path

