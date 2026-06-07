from __future__ import annotations

from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import requests

from .config import Settings
from .database import Database
from .deduplicate import is_duplicate_title
from .models import NewsItem
from .score_news import score_batch


RSS_SOURCES: list[dict[str, str]] = [
    {"source": "Federal Reserve", "url": "https://www.federalreserve.gov/feeds/press_all.xml"},
    {"source": "Federal Reserve", "url": "https://www.federalreserve.gov/feeds/speeches.xml"},
    {"source": "European Central Bank", "url": "https://www.ecb.europa.eu/rss/press.html"},
    {"source": "SEC", "url": "https://www.sec.gov/news/pressreleases.rss"},
    {"source": "White House", "url": "https://www.whitehouse.gov/briefing-room/feed/"},
    {"source": "US Treasury", "url": "https://home.treasury.gov/news/press-releases/rss"},
    {"source": "IMF", "url": "https://www.imf.org/en/News/RSS"},
    {"source": "World Bank", "url": "https://www.worldbank.org/en/news/all?format=rss"},
    {"source": "NATO", "url": "https://www.nato.int/cps/en/natohq/rss.xml"},
    {"source": "Associated Press", "url": "https://apnews.com/hub/business?output=1"},
    {"source": "CNBC", "url": "https://www.cnbc.com/id/10000664/device/rss/rss.html"},
    {"source": "CNBC Markets", "url": "https://www.cnbc.com/id/100003114/device/rss/rss.html"},
    {"source": "CNBC Economy", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html"},
    {"source": "Financial Times", "url": "https://www.ft.com/?format=rss"},
    {"source": "Financial Times Europe", "url": "https://www.ft.com/europe?format=rss"},
    {"source": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex"},
    {"source": "MarketWatch", "url": "https://feeds.content.dowjones.io/public/rss/mw_topstories"},
    {"source": "Investing.com", "url": "https://www.investing.com/rss/news_25.rss"},
    {"source": "Investing.com Economy", "url": "https://www.investing.com/rss/news_95.rss"},
    {"source": "Eurostat", "url": "https://ec.europa.eu/eurostat/api/dissemination/rss/news.xml"},
    {"source": "European Commission", "url": "https://ec.europa.eu/commission/presscorner/api/rss"},
    {"source": "NASA", "url": "https://www.nasa.gov/rss/dyn/breaking_news.rss"},
    {"source": "ESA", "url": "https://www.esa.int/rss/TopNews.xml"},
    {"source": "SpaceNews", "url": "https://spacenews.com/feed/"},
    {"source": "Space.com", "url": "https://www.space.com/feeds/all"},
    {"source": "US Space Force", "url": "https://www.spaceforce.mil/DesktopModules/ArticleCS/RSS.ashx?ContentType=1&Site=905&Category=20737&max=20"},
    {"source": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"source": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
]


def _parse_date(entry: Any) -> datetime:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if value:
            try:
                parsed = parsedate_to_datetime(value)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=UTC)
                return parsed.astimezone(UTC)
            except (TypeError, ValueError):
                continue
    if entry.get("published_parsed"):
        parsed_struct = entry.published_parsed
        return datetime(*parsed_struct[:6], tzinfo=UTC)
    if entry.get("updated_parsed"):
        parsed_struct = entry.updated_parsed
        return datetime(*parsed_struct[:6], tzinfo=UTC)
    return datetime.now(UTC)


def _entry_content(entry: Any) -> str:
    if entry.get("content"):
        chunks = [part.get("value", "") for part in entry.content if isinstance(part, dict)]
        return "\n".join(chunk for chunk in chunks if chunk)
    return ""


def fetch_source(source: str, url: str, settings: Settings) -> list[NewsItem]:
    headers = {"User-Agent": "investment-learning-radar/0.1 (+learning project)"}
    response = requests.get(url, headers=headers, timeout=settings.fetch_timeout_seconds)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)
    items: list[NewsItem] = []
    for entry in parsed.entries:
        title = (entry.get("title") or "").strip()
        link = (entry.get("link") or entry.get("id") or "").strip()
        if not title or not link:
            continue
        summary = (entry.get("summary") or entry.get("description") or "").strip()
        try:
            items.append(
                NewsItem(
                    title=title,
                    source=source,
                    url=link,
                    published_at=_parse_date(entry),
                    raw_summary=summary,
                    raw_content=_entry_content(entry),
                )
            )
        except ValueError:
            continue
    return items


def fetch_all(settings: Settings) -> tuple[list[NewsItem], list[str]]:
    items: list[NewsItem] = []
    errors: list[str] = []
    for feed in RSS_SOURCES:
        try:
            items.extend(fetch_source(feed["source"], feed["url"], settings))
        except requests.RequestException as exc:
            errors.append(f"{feed['source']}: {exc}")
    return items, errors


def fetch_and_store(settings: Settings, db: Database) -> dict[str, int | list[str]]:
    db.init()
    items, errors = fetch_all(settings)
    recent_titles = db.recent_titles(hours=72)
    skipped = 0
    inserted = 0

    for scored in score_batch(items):
        item = scored.item
        if db.url_exists(str(item.url)) or is_duplicate_title(item.title, recent_titles):
            skipped += 1
            continue
        news_id = db.upsert_news(scored.item, scored.score, scored.reasons)
        if news_id:
            inserted += 1
        recent_titles.append(item.title)

    return {
        "fetched": len(items),
        "inserted": inserted,
        "skipped_duplicates": skipped,
        "errors": errors,
    }
