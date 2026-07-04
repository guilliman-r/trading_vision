"""Transparent validation and normalization for provider candle data."""

from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

INTERVAL_LENGTHS = {
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "1d": pd.Timedelta(days=1),
}


def prepare_candles(frame: pd.DataFrame, interval: str, source: str) -> pd.DataFrame:
    """Return sorted, validated candles in the application's storage schema."""

    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Provider data is missing columns: {', '.join(sorted(missing))}")
    if interval not in INTERVAL_LENGTHS:
        raise ValueError(f"Unsupported interval: {interval}")

    clean = frame.copy()
    if "opened_at_utc" not in clean.columns:
        clean.index = clean.index.rename(None)
        clean["opened_at_utc"] = pd.to_datetime(clean.index, utc=True)
    else:
        clean["opened_at_utc"] = pd.to_datetime(clean["opened_at_utc"], utc=True)
    clean = clean.sort_values("opened_at_utc").drop_duplicates("opened_at_utc", keep="last")

    numeric_columns = ["open", "high", "low", "close", "volume"]
    clean[numeric_columns] = clean[numeric_columns].apply(pd.to_numeric, errors="coerce")
    valid = (
        clean[["open", "high", "low", "close"]].notna().all(axis=1)
        & (clean[["open", "high", "low", "close"]] > 0).all(axis=1)
        & (clean["high"] >= clean[["open", "close", "low"]].max(axis=1))
        & (clean["low"] <= clean[["open", "close", "high"]].min(axis=1))
        & (clean["volume"].isna() | (clean["volume"] >= 0))
    )
    clean = clean.loc[valid].copy()
    if clean.empty:
        raise ValueError("Provider returned no valid candles")

    now = pd.Timestamp(datetime.now(UTC))
    clean["is_complete"] = clean["opened_at_utc"] + INTERVAL_LENGTHS[interval] <= now
    clean["is_adjusted"] = True
    clean["source"] = source
    clean["fetched_at_utc"] = now
    return clean[
        [
            "opened_at_utc",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "is_complete",
            "is_adjusted",
            "source",
            "fetched_at_utc",
        ]
    ].reset_index(drop=True)
