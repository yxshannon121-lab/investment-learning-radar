from __future__ import annotations

from datetime import UTC, datetime, timedelta
from math import isfinite

import pandas as pd
import yfinance as yf

from .database import Database, dt_from_db, json_loads, utc_now


CHECKPOINTS = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "5d": timedelta(days=5),
    "20d": timedelta(days=20),
}


def _safe_float(value) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric if isfinite(numeric) else None


def _download_history(symbol: str, start: datetime, end: datetime, interval: str) -> pd.DataFrame:
    data = yf.download(
        symbol,
        start=start.date().isoformat(),
        end=(end.date() + timedelta(days=1)).isoformat(),
        interval=interval,
        progress=False,
        auto_adjust=True,
        threads=False,
    )
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data


def price_near(symbol: str, when: datetime, prefer_intraday: bool = False) -> float | None:
    when = when.astimezone(UTC)
    interval = "1h" if prefer_intraday else "1d"
    window_before = timedelta(days=3)
    window_after = timedelta(days=7)
    try:
        data = _download_history(symbol, when - window_before, when + window_after, interval)
    except Exception:
        return None
    if data.empty or "Close" not in data:
        return None

    closes = data["Close"].dropna()
    if closes.empty:
        return None

    index = closes.index
    try:
        if getattr(index, "tz", None) is None:
            index = index.tz_localize(UTC)
        else:
            index = index.tz_convert(UTC)
    except (TypeError, AttributeError):
        pass

    future_positions = [i for i, ts in enumerate(index) if getattr(ts, "to_pydatetime", lambda: ts)() >= when]
    if future_positions:
        return _safe_float(closes.iloc[future_positions[0]])
    return _safe_float(closes.iloc[-1])


def pct_change(start: float | None, end: float | None) -> float | None:
    if start in (None, 0) or end is None:
        return None
    return round(((end - start) / start) * 100, 2)


def symbols_for_row(row) -> tuple[list[str], list[str]]:
    etfs = json_loads(row["observed_etfs"], [])
    stocks = json_loads(row["observed_stocks"], [])
    return sorted(set(etfs)), sorted(set(stocks))


def create_initial_snapshots(db: Database, row) -> None:
    published_at = dt_from_db(row["published_at"])
    if not published_at:
        return
    etfs, stocks = symbols_for_row(row)
    for symbol in etfs:
        event_price = price_near(symbol, published_at, prefer_intraday=True)
        db.upsert_market_snapshot(row["id"], symbol, "ETF", {"event_price": event_price})
    for symbol in stocks:
        event_price = price_near(symbol, published_at, prefer_intraday=True)
        db.upsert_market_snapshot(row["id"], symbol, "stock", {"event_price": event_price})


def update_due_snapshots(db: Database) -> int:
    updated = 0
    now = utc_now()
    for row in db.rows_for_tracking(days_back=35):
        published_at = dt_from_db(row["published_at"])
        if not published_at:
            continue
        event_price = row["event_price"] or price_near(row["symbol"], published_at, prefer_intraday=True)
        values: dict[str, float | None] = {"event_price": event_price}

        for label, delta in CHECKPOINTS.items():
            price_key = f"price_{label}"
            pct_key = f"pct_{label}"
            if row[price_key] is not None or now < published_at + delta:
                continue
            checkpoint_price = price_near(row["symbol"], published_at + delta, prefer_intraday=(label == "1h"))
            values[price_key] = checkpoint_price
            values[pct_key] = pct_change(event_price, checkpoint_price)

        if len(values) > 1 or row["event_price"] is None:
            db.upsert_market_snapshot(row["id"], row["symbol"], row["asset_type"], values)
            updated += 1
    return updated

