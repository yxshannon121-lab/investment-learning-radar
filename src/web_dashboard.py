from __future__ import annotations

import html
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import ROOT_DIR, Settings
from .database import Database, dt_from_db, json_loads
from .rule_analyze import RISK_NOTE, analyze_news_row_rules


DISCLAIMER = RISK_NOTE
NEWS_DIR = "news"

CATEGORY_ORDER = ["宏观经济", "科技/AI", "半导体", "能源", "加密货币", "地缘政治", "欧洲市场", "综合市场"]
SECTOR_TO_CATEGORY = {
    "科技": "科技/AI",
    "AI": "科技/AI",
    "半导体": "半导体",
    "能源": "能源",
    "加密货币": "加密货币",
    "军工": "地缘政治",
    "黄金": "地缘政治",
    "工业": "地缘政治",
    "出口": "地缘政治",
    "欧洲银行": "欧洲市场",
    "欧洲市场": "欧洲市场",
    "银行": "宏观经济",
    "债券": "宏观经济",
    "云计算": "科技/AI",
    "数据中心": "科技/AI",
    "航天": "地缘政治",
    "卫星": "地缘政治",
    "军工航天": "地缘政治",
    "核电": "能源",
    "电网": "能源",
    "能源基础设施": "能源",
    "数据中心供电": "能源",
}

SOURCE_RATING = {
    "Federal Reserve": 5,
    "European Central Bank": 5,
    "SEC": 5,
    "US Treasury": 5,
    "IMF": 5,
    "World Bank": 5,
    "Eurostat": 5,
    "European Commission": 5,
    "Reuters": 5,
    "Associated Press": 5,
    "CNBC": 4,
    "CNBC Markets": 4,
    "CNBC Economy": 4,
    "Financial Times": 4,
    "Financial Times Europe": 4,
    "Yahoo Finance": 4,
    "MarketWatch": 4,
    "SpaceNews": 4,
    "NASA": 5,
    "ESA": 5,
    "US Space Force": 5,
}


def _local_time(value: str | None, settings: Settings, include_tz: bool = True) -> str:
    parsed = dt_from_db(value)
    if not parsed:
        return value or "未知"
    fmt = "%Y-%m-%d %H:%M %Z" if include_tz else "%Y-%m-%d %H:%M"
    return parsed.astimezone(ZoneInfo(settings.timezone)).strftime(fmt)


def _date_slug(value: str | None, settings: Settings) -> str:
    parsed = dt_from_db(value)
    if not parsed:
        return "unknown"
    return parsed.astimezone(ZoneInfo(settings.timezone)).strftime("%Y%m%d")


def _news_filename(row, settings: Settings) -> str:
    return f"news_{_date_slug(row['published_at'], settings)}_{int(row['id']):03d}.html"


def _news_href(row, settings: Settings, from_detail: bool = False) -> str:
    prefix = "" if from_detail else f"{NEWS_DIR}/"
    return f"{prefix}{_news_filename(row, settings)}"


def _list_text(values: list[str]) -> str:
    return "、".join(values) if values else "不确定/待观察"


def _badge_list(values: list[str]) -> str:
    if not values:
        return '<span class="muted">不确定/待观察</span>'
    return "".join(f'<span class="badge">{html.escape(value)}</span>' for value in values)


def _pct(value) -> str:
    if value is None:
        return "待观察"
    return f"{float(value):+.2f}%"


def _price(value) -> str:
    if value is None:
        return "待获取"
    return f"{float(value):.2f}"


def _importance(score: float | None) -> str:
    score = float(score or 0)
    if score >= 12:
        return "高"
    if score >= 8:
        return "中"
    return "低"


def _importance_class(label: str) -> str:
    return {"高": "high", "中": "medium", "低": "low"}.get(label, "low")


def _source_rating(source: str) -> str:
    stars = SOURCE_RATING.get(source, 3)
    return "★" * stars + "☆" * (5 - stars)


def _short_summary(summary: list[str], limit: int = 2) -> list[str]:
    clean = [item.strip() for item in summary if item and item.strip()]
    return clean[:limit] or ["暂无可展示的中文摘要，请点击原文链接核对新闻。"]


def _analysis_for_display(row) -> dict[str, object]:
    rule_fallback = analyze_news_row_rules(row)
    title_zh = row["title_zh"] or rule_fallback.title_zh
    summary_zh = json_loads(row["summary_zh"], []) or rule_fallback.summary_zh
    facts = json_loads(row["confirmed_facts"], []) or summary_zh
    content_zh = json_loads(row["content_zh"], [])
    sectors = json_loads(row["affected_sectors"], []) or rule_fallback.affected_sectors
    etfs = json_loads(row["observed_etfs"], []) or rule_fallback.observed_etfs
    stocks = json_loads(row["observed_stocks"], []) or rule_fallback.observed_stocks
    uncertainties = json_loads(row["uncertainties"], []) or rule_fallback.uncertainties_zh
    return {
        "title_zh": title_zh,
        "summary_zh": summary_zh,
        "facts": facts,
        "content_zh": content_zh,
        "content_status": row["content_status"] or "unavailable",
        "sectors": sectors,
        "etfs": etfs,
        "stocks": stocks,
        "uncertainties": uncertainties,
        "analysis": row["ai_analysis"] or rule_fallback.ai_analysis_zh,
        "direction": row["impact_direction"] or rule_fallback.impact_direction,
        "reason": row["observation_reason"] or rule_fallback.observation_reason_zh,
        "method": row["analysis_method"] or rule_fallback.analysis_method,
        "importance": _importance(row["score"]),
    }


def _category_for_sectors(sectors: list[str]) -> str:
    for sector in sectors:
        category = SECTOR_TO_CATEGORY.get(sector)
        if category:
            return category
    return "综合市场"


def _importance_weight(row) -> int:
    label = _importance(row["score"])
    return {"高": 3, "中": 2, "低": 1}.get(label, 1)


def _overview(rows) -> tuple[list[str], list[str]]:
    etfs: Counter = Counter()
    stocks: Counter = Counter()
    for row in rows:
        display = _analysis_for_display(row)
        weight = _importance_weight(row)
        for symbol in display["etfs"]:
            etfs[str(symbol)] += weight
        for symbol in display["stocks"]:
            stocks[str(symbol)] += weight
    top_etfs = [symbol for symbol, _ in etfs.most_common(8)]
    top_stocks = [symbol for symbol, _ in stocks.most_common(12)]
    return top_etfs, top_stocks


def _track_counts(rows) -> Counter:
    counts: Counter = Counter()
    for row in rows:
        display = _analysis_for_display(row)
        weight = _importance_weight(row)
        for sector in display["sectors"]:
            counts[str(sector)] += weight
    return counts


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


def _homepage_news_item(row, settings: Settings) -> str:
    display = _analysis_for_display(row)
    importance = str(display["importance"])
    summary = " ".join(html.escape(item) for item in _short_summary(display["summary_zh"], 2))
    return f"""
    <article class="news-row">
      <div class="news-row-main">
        <h3><a href="{html.escape(_news_href(row, settings))}">{html.escape(str(display['title_zh']))}</a></h3>
        <div class="meta-line">
          <span class="importance {html.escape(_importance_class(importance))}">重要性：{html.escape(importance)}</span>
          <span>来源：{html.escape(row['source'])} {html.escape(_source_rating(row['source']))}</span>
          <span>发布时间：{html.escape(_local_time(row['published_at'], settings, include_tz=False))}</span>
        </div>
        <p class="summary-text">{summary}</p>
        <div class="compact-grid">
          <div><b>可能影响板块</b>{_badge_list(display['sectors'])}</div>
          <div><b>观察 ETF</b>{_badge_list(display['etfs'])}</div>
          <div><b>观察个股</b>{_badge_list(display['stocks'])}</div>
        </div>
      </div>
      <a class="detail-link" href="{html.escape(_news_href(row, settings))}">查看全文 →</a>
    </article>
    """


def _homepage_section(title: str, rows, settings: Settings, empty_text: str, section_id: str) -> str:
    content = "\n".join(_homepage_news_item(row, settings) for row in rows) if rows else f'<p class="empty">{html.escape(empty_text)}</p>'
    return f"""
    <section class="page-section" id="{html.escape(section_id)}">
      <div class="section-title">
        <h2>{html.escape(title)}</h2>
      </div>
      {content}
    </section>
    """


def _translation_block(row, display: dict[str, object]) -> str:
    content = [str(item) for item in display.get("content_zh", []) if str(item).strip()]
    summary_items = "".join(f"<li>{html.escape(item)}</li>" for item in display["summary_zh"])
    if content:
        first = content[:4]
        rest = content[4:]
        first_html = "".join(f"<p>{html.escape(item)}</p>" for item in first)
        if rest:
            rest_html = "".join(f"<p>{html.escape(item)}</p>" for item in rest)
            more = f"<details><summary>展开全文</summary>{rest_html}</details>"
        else:
            more = ""
        return f"""
        <section class="panel">
          <h2>中文全文翻译</h2>
          {first_html}
          {more}
        </section>
        """

    status = str(display.get("content_status") or "unavailable")
    if status == "paywall":
        message = "该来源正文受付费墙或登录限制，暂时无法获取全文，请点击原文查看。"
    elif status in {"none", "unavailable"}:
        message = "该来源未提供可翻译摘要，请点击原文链接查看。"
    else:
        message = "暂时无法生成中文翻译，请点击原文查看"
    return f"""
    <section class="panel">
      <h2>中文全文翻译</h2>
      <p>{html.escape(message)}</p>
      <h3>中文摘要</h3>
      <ul>{summary_items}</ul>
    </section>
    """


def _detail_page(row, db: Database, settings: Settings) -> str:
    display = _analysis_for_display(row)
    importance = str(display["importance"])
    uncertainty_items = "".join(f"<li>{html.escape(item)}</li>" for item in display["uncertainties"]) or "<li>待观察。</li>"
    title = html.escape(str(display["title_zh"]))
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} - 中文投资学习雷达</title>
  <style>{_styles()}</style>
</head>
<body>
  <header class="site-header">
    <div class="wrap hero compact">
      <a class="back-link" href="../index.html">← 返回首页</a>
      <h1>{title}</h1>
      <p class="subhead">来源：{html.escape(row['source'])} {html.escape(_source_rating(row['source']))} ｜ 发布时间：{html.escape(_local_time(row['published_at'], settings))}</p>
      <p><a class="source-link" href="{html.escape(row['url'])}" target="_blank" rel="noopener noreferrer">打开原文链接</a></p>
    </div>
  </header>
  <main class="wrap">
    {_translation_block(row, display)}
    <section class="panel">
      <h2>规则分析</h2>
      <div class="detail-grid">
        <div><b>重要性</b><span class="importance {html.escape(_importance_class(importance))}">{html.escape(importance)}</span></div>
        <div><b>可能影响板块</b>{_badge_list(display['sectors'])}</div>
        <div><b>影响方向</b><span>{html.escape(str(display['direction']))}</span></div>
        <div><b>观察 ETF/资产</b>{_badge_list(display['etfs'])}</div>
        <div><b>观察个股</b>{_badge_list(display['stocks'])}</div>
      </div>
      <h3>为什么观察</h3>
      <p>{html.escape(str(display['reason']))}</p>
      <h3>不确定部分</h3>
      <ul>{uncertainty_items}</ul>
    </section>
    <details class="panel">
      <summary>查看后续涨跌追踪</summary>
      {_market_table(db, row['id'])}
    </details>
  </main>
  <footer>
    <div class="wrap">{DISCLAIMER}</div>
  </footer>
</body>
</html>
"""


def _styles() -> str:
    return """
    :root {
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
      --high: #b91c1c;
      --medium: #9a5b00;
      --low: #475569;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Microsoft YaHei", Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }
    .wrap { width: min(1120px, calc(100% - 32px)); margin: 0 auto; }
    .site-header { background: #fff; border-bottom: 1px solid var(--line); }
    .hero { padding: 28px 0 20px; }
    .hero.compact { padding-bottom: 24px; }
    h1 { margin: 0 0 8px; font-size: clamp(26px, 4vw, 40px); letter-spacing: 0; }
    h2 { margin: 0 0 8px; font-size: 24px; }
    h3 { margin: 0 0 8px; font-size: 18px; }
    .subhead { margin: 0; color: var(--muted); max-width: 820px; }
    .notice { margin-top: 18px; padding: 12px 14px; border: 1px solid #f1c987; background: var(--warn-soft); color: var(--warn); border-radius: 8px; font-weight: 700; }
    nav { display: flex; gap: 10px; flex-wrap: wrap; padding: 0 0 18px; }
    nav a, .source-link, .detail-link, .back-link { color: var(--accent); font-weight: 700; text-decoration: none; }
    nav a { background: var(--accent-soft); border: 1px solid #b8dfd9; border-radius: 8px; padding: 8px 10px; }
    main { padding: 22px 0 38px; }
    .page-section, .panel { margin-bottom: 24px; }
    .panel, .overview-card, .news-row, .review-item {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      box-shadow: 0 1px 2px rgba(23, 32, 51, 0.05);
    }
    .overview-grid { display: grid; grid-template-columns: 1.2fr 1fr; gap: 14px; margin: 18px 0 24px; }
    .count-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 10px; margin-top: 12px; }
    .count-card { background: #f9fafb; border: 1px solid var(--line); border-radius: 8px; padding: 10px; }
    .count-card b { display: block; font-size: 22px; }
    .watch-list { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-top: 12px; }
    .section-title { margin-bottom: 12px; }
    .news-row { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 16px; align-items: center; margin-bottom: 12px; }
    .news-row h3 { margin-bottom: 8px; line-height: 1.35; }
    .news-row h3 a { color: var(--text); text-decoration: none; }
    .meta-line { display: flex; flex-wrap: wrap; gap: 8px 14px; color: var(--muted); font-size: 14px; margin-bottom: 8px; }
    .summary-text { margin: 0 0 10px; }
    .compact-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 10px; }
    .compact-grid b, .detail-grid b { display: block; color: var(--muted); font-size: 12px; margin-bottom: 4px; }
    .badge { display: inline-block; margin: 2px 4px 2px 0; padding: 3px 8px; border-radius: 999px; background: var(--accent-soft); color: #0f5f59; font-weight: 700; font-size: 13px; }
    .importance { display: inline-block; border-radius: 999px; padding: 3px 8px; font-size: 13px; font-weight: 800; background: #f1f5f9; }
    .importance.high { color: var(--high); background: #fee2e2; }
    .importance.medium { color: var(--medium); background: #fef3c7; }
    .importance.low { color: var(--low); background: #e2e8f0; }
    .detail-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin-bottom: 16px; }
    details summary { cursor: pointer; font-weight: 800; color: var(--accent); }
    .table-wrap { overflow-x: auto; border: 1px solid var(--line); border-radius: 8px; margin-top: 12px; }
    table { border-collapse: collapse; width: 100%; min-width: 620px; background: #fff; }
    th, td { padding: 9px 10px; border-bottom: 1px solid var(--line); text-align: left; white-space: nowrap; }
    th { background: #f9fafb; color: var(--muted); font-size: 12px; }
    .muted, .empty { color: var(--muted); }
    footer { border-top: 1px solid var(--line); background: #fff; padding: 18px 0; color: var(--muted); font-size: 14px; }
    @media (max-width: 820px) {
      .overview-grid, .watch-list, .compact-grid, .detail-grid, .news-row { grid-template-columns: 1fr; }
      .count-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .detail-link { justify-self: start; }
    }
    """


def build_dashboard_html(settings: Settings, db: Database) -> str:
    now = datetime.now(ZoneInfo(settings.timezone))
    generated_at = now.strftime("%Y-%m-%d %H:%M %Z")
    rows = db.top_news_for_report(settings.report_lookback_hours, max(settings.max_report_items, 24))
    top_etfs, top_stocks = _overview(rows)
    tracks = _track_counts(rows)
    top_rows = rows[:3]
    rest_rows = rows[3:]

    category_cards = "".join(
        f'<div class="count-card"><span>{html.escape(name)}</span><b>{count}</b></div>'
        for name, count in tracks.most_common(16)
    )
    if not category_cards:
        category_cards = '<p class="empty">当前窗口内暂无可统计新闻。</p>'

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>中文投资学习雷达</title>
  <style>{_styles()}</style>
</head>
<body>
  <header class="site-header">
    <div class="wrap hero">
      <h1>Investment Learning Radar<br>中文投资学习雷达</h1>
      <p class="subhead">最后更新时间：{html.escape(generated_at)}</p>
      <div class="notice">本页面仅用于投资学习和信息整理，不构成任何投资建议。</div>
    </div>
    <nav class="wrap" aria-label="页面导航">
      <a href="#overview">今日市场概览</a>
      <a href="#top">今日最重要新闻</a>
      <a href="#all">全部新闻</a>
    </nav>
  </header>
  <main class="wrap">
    <section id="overview" class="overview-grid">
      <div class="overview-card">
        <h2>今日市场概览</h2>
        <p class="muted">今日重点新闻数量：{len(rows)}</p>
        <div class="count-grid">{category_cards}</div>
      </div>
      <div class="overview-card">
        <h2>今日重点观察</h2>
        <div class="watch-list">
          <div><h3>ETF/资产</h3>{_badge_list(top_etfs)}</div>
          <div><h3>个股</h3>{_badge_list(top_stocks)}</div>
        </div>
      </div>
    </section>
    <section class="page-section">
      <div class="section-title">
        <h2>今日重点赛道</h2>
      </div>
      {_badge_list([f"{name}（{count}条）" for name, count in tracks.most_common(10)])}
    </section>
    {_homepage_section("🔥 今日最重要新闻", top_rows, settings, "当前没有可展示的重要新闻。", "top")}
    {_homepage_section("📰 全部新闻", rest_rows, settings, "当前没有更多新闻。", "all")}
  </main>
  <footer>
    <div class="wrap">{DISCLAIMER}</div>
  </footer>
</body>
</html>
"""


def _write_detail_pages(settings: Settings, db: Database, rows) -> None:
    news_dir = ROOT_DIR / "docs" / NEWS_DIR
    news_dir.mkdir(parents=True, exist_ok=True)
    for path in news_dir.glob("news_*.html"):
        path.unlink()
    for row in rows:
        path = news_dir / _news_filename(row, settings)
        path.write_text(_detail_page(row, db, settings), encoding="utf-8")


def write_dashboard(settings: Settings, db: Database, output_path: Path | None = None) -> Path:
    path = output_path or ROOT_DIR / "docs" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = db.top_news_for_report(settings.report_lookback_hours, max(settings.max_report_items, 24))
    _write_detail_pages(settings, db, rows)
    html_doc = build_dashboard_html(settings, db)
    path.write_text(html_doc, encoding="utf-8")
    if output_path is None:
        (path.parent / "dashboard.html").write_text(html_doc, encoding="utf-8")
    return path
