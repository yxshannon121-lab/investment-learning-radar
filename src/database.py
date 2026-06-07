from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Iterator

from .config import Settings
from .models import AIAnalysis, NewsItem


def utc_now() -> datetime:
    return datetime.now(UTC)


def dt_to_db(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def dt_from_db(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


class Database:
    def __init__(self, settings: Settings):
        self.path = settings.sqlite_path
        self.path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def init(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    published_at TEXT NOT NULL,
                    raw_summary TEXT DEFAULT '',
                    raw_content TEXT DEFAULT '',
                    score REAL DEFAULT 0,
                    score_reasons TEXT DEFAULT '[]',
                    title_zh TEXT,
                    summary_zh TEXT DEFAULT '[]',
                    content_zh TEXT DEFAULT '[]',
                    content_status TEXT DEFAULT 'unavailable',
                    analysis_method TEXT DEFAULT '规则分析',
                    ai_summary TEXT,
                    confirmed_facts TEXT,
                    ai_analysis TEXT,
                    affected_sectors TEXT DEFAULT '[]',
                    impact_direction TEXT DEFAULT '不确定',
                    observed_etfs TEXT DEFAULT '[]',
                    observed_stocks TEXT DEFAULT '[]',
                    observation_reason TEXT,
                    uncertainties TEXT DEFAULT '[]',
                    analyzed_at TEXT,
                    created_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_news_published_at ON news(published_at);
                CREATE INDEX IF NOT EXISTS idx_news_score ON news(score);

                CREATE TABLE IF NOT EXISTS market_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    news_id INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    asset_type TEXT NOT NULL,
                    event_price REAL,
                    price_1h REAL,
                    pct_1h REAL,
                    price_1d REAL,
                    pct_1d REAL,
                    price_5d REAL,
                    pct_5d REAL,
                    price_20d REAL,
                    pct_20d REAL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(news_id, symbol),
                    FOREIGN KEY(news_id) REFERENCES news(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS sent_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_type TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    item_ids TEXT DEFAULT '[]',
                    sent_at TEXT NOT NULL,
                    dry_run INTEGER NOT NULL
                );
                """
            )
            self._ensure_columns(conn)

    def _ensure_columns(self, conn: sqlite3.Connection) -> None:
        existing = {row["name"] for row in conn.execute("PRAGMA table_info(news)").fetchall()}
        columns = {
            "title_zh": "TEXT",
            "summary_zh": "TEXT DEFAULT '[]'",
            "content_zh": "TEXT DEFAULT '[]'",
            "content_status": "TEXT DEFAULT 'unavailable'",
            "analysis_method": "TEXT DEFAULT '规则分析'",
        }
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f"ALTER TABLE news ADD COLUMN {name} {definition}")

    def recent_titles(self, hours: int = 72) -> list[str]:
        threshold = dt_to_db(utc_now() - timedelta(hours=hours))
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT title FROM news WHERE published_at >= ? ORDER BY published_at DESC",
                (threshold,),
            ).fetchall()
        return [row["title"] for row in rows]

    def url_exists(self, url: str) -> bool:
        with self.connect() as conn:
            row = conn.execute("SELECT 1 FROM news WHERE url = ?", (url,)).fetchone()
        return row is not None

    def upsert_news(self, item: NewsItem, score: float, reasons: list[str]) -> int | None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO news
                (title, source, url, published_at, raw_summary, raw_content, score, score_reasons, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.title,
                    item.source,
                    str(item.url),
                    dt_to_db(item.published_at),
                    item.raw_summary,
                    item.raw_content,
                    score,
                    json_dumps(reasons),
                    dt_to_db(utc_now()),
                ),
            )
            row = conn.execute("SELECT id FROM news WHERE url = ?", (str(item.url),)).fetchone()
        return int(row["id"]) if row else None

    def update_ai_analysis(self, news_id: int, analysis: AIAnalysis) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE news
                SET ai_summary = ?,
                    title_zh = ?,
                    summary_zh = ?,
                    content_zh = ?,
                    content_status = ?,
                    analysis_method = ?,
                    confirmed_facts = ?,
                    ai_analysis = ?,
                    affected_sectors = ?,
                    impact_direction = ?,
                    observed_etfs = ?,
                    observed_stocks = ?,
                    observation_reason = ?,
                    uncertainties = ?,
                    analyzed_at = ?
                WHERE id = ?
                """,
                (
                    "\n".join(analysis.confirmed_facts_zh),
                    analysis.title_zh,
                    json_dumps(analysis.summary_zh),
                    json_dumps(analysis.content_zh),
                    analysis.content_status,
                    analysis.analysis_method,
                    json_dumps(analysis.confirmed_facts_zh),
                    analysis.ai_analysis_zh,
                    json_dumps(analysis.affected_sectors),
                    analysis.impact_direction,
                    json_dumps(analysis.observed_etfs),
                    json_dumps(analysis.observed_stocks),
                    analysis.observation_reason_zh,
                    json_dumps(analysis.uncertainties_zh),
                    dt_to_db(utc_now()),
                    news_id,
                ),
            )

    def top_news_for_report(self, lookback_hours: int, limit: int) -> list[sqlite3.Row]:
        threshold = dt_to_db(utc_now() - timedelta(hours=lookback_hours))
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM news
                WHERE published_at >= ?
                ORDER BY score DESC, published_at DESC
                LIMIT ?
                """,
                (threshold, limit),
            ).fetchall()

    def high_score_unanalyzed(
        self,
        min_score: float,
        lookback_hours: int,
        limit: int,
        retry_missing_key_fallbacks: bool = False,
    ) -> list[sqlite3.Row]:
        threshold = dt_to_db(utc_now() - timedelta(hours=lookback_hours))
        if retry_missing_key_fallbacks:
            analyzed_filter = """
                  AND (
                    analyzed_at IS NULL
                    OR title_zh IS NULL
                    OR title_zh = ''
                    OR summary_zh IS NULL
                    OR summary_zh = '[]'
                    OR content_zh IS NULL
                    OR content_zh = '[]'
                    OR confirmed_facts LIKE '%缺少 OPENAI_API_KEY%'
                    OR ai_summary LIKE '%缺少 OPENAI_API_KEY%'
                  )
            """
        else:
            analyzed_filter = "AND analyzed_at IS NULL"
        with self.connect() as conn:
            return conn.execute(
                f"""
                SELECT * FROM news
                WHERE published_at >= ?
                  AND score >= ?
                  {analyzed_filter}
                ORDER BY score DESC, published_at DESC
                LIMIT ?
                """,
                (threshold, min_score, limit),
            ).fetchall()

    def upsert_market_snapshot(
        self,
        news_id: int,
        symbol: str,
        asset_type: str,
        values: dict[str, float | None],
    ) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO market_snapshots
                (news_id, symbol, asset_type, event_price, price_1h, pct_1h,
                 price_1d, pct_1d, price_5d, pct_5d, price_20d, pct_20d, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(news_id, symbol) DO UPDATE SET
                    event_price = COALESCE(excluded.event_price, market_snapshots.event_price),
                    price_1h = COALESCE(excluded.price_1h, market_snapshots.price_1h),
                    pct_1h = COALESCE(excluded.pct_1h, market_snapshots.pct_1h),
                    price_1d = COALESCE(excluded.price_1d, market_snapshots.price_1d),
                    pct_1d = COALESCE(excluded.pct_1d, market_snapshots.pct_1d),
                    price_5d = COALESCE(excluded.price_5d, market_snapshots.price_5d),
                    pct_5d = COALESCE(excluded.pct_5d, market_snapshots.pct_5d),
                    price_20d = COALESCE(excluded.price_20d, market_snapshots.price_20d),
                    pct_20d = COALESCE(excluded.pct_20d, market_snapshots.pct_20d),
                    updated_at = excluded.updated_at
                """,
                (
                    news_id,
                    symbol,
                    asset_type,
                    values.get("event_price"),
                    values.get("price_1h"),
                    values.get("pct_1h"),
                    values.get("price_1d"),
                    values.get("pct_1d"),
                    values.get("price_5d"),
                    values.get("pct_5d"),
                    values.get("price_20d"),
                    values.get("pct_20d"),
                    dt_to_db(utc_now()),
                ),
            )

    def market_snapshots_for_news(self, news_id: int) -> list[sqlite3.Row]:
        with self.connect() as conn:
            return conn.execute(
                "SELECT * FROM market_snapshots WHERE news_id = ? ORDER BY symbol",
                (news_id,),
            ).fetchall()

    def rows_for_tracking(self, days_back: int = 30) -> list[sqlite3.Row]:
        threshold = dt_to_db(utc_now() - timedelta(days=days_back))
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT n.*, m.symbol, m.asset_type, m.event_price, m.price_1h, m.price_1d, m.price_5d, m.price_20d
                FROM news n
                JOIN market_snapshots m ON m.news_id = n.id
                WHERE n.published_at >= ?
                ORDER BY n.published_at DESC
                """,
                (threshold,),
            ).fetchall()

    def weekly_news(self, limit: int = 10) -> list[sqlite3.Row]:
        threshold = dt_to_db(utc_now() - timedelta(days=7))
        with self.connect() as conn:
            return conn.execute(
                """
                SELECT * FROM news
                WHERE published_at >= ?
                ORDER BY score DESC, published_at DESC
                LIMIT ?
                """,
                (threshold, limit),
            ).fetchall()

    def record_sent_report(self, report_type: str, subject: str, item_ids: list[int], dry_run: bool) -> None:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO sent_reports (report_type, subject, item_ids, sent_at, dry_run)
                VALUES (?, ?, ?, ?, ?)
                """,
                (report_type, subject, json_dumps(item_ids), dt_to_db(utc_now()), int(dry_run)),
            )


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
