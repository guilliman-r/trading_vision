"""Transparent validation and normalization for provider candle data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pandas as pd

INTERVAL_LENGTHS = {
    "5m": pd.Timedelta(minutes=5),
    "15m": pd.Timedelta(minutes=15),
    "1h": pd.Timedelta(hours=1),
    "1d": pd.Timedelta(days=1),
}

ISSUE_LABELS = {
    "invalid_timestamp": "invalid timestamp",
    "duplicate_timestamp": "duplicate timestamp",
    "missing_price": "missing or non-numeric price",
    "non_positive_price": "non-positive price",
    "high_below_price": "high below OHLC values",
    "low_above_price": "low above OHLC values",
    "invalid_volume": "non-numeric volume",
    "negative_volume": "negative volume",
}


@dataclass(frozen=True, slots=True)
class DataQualityReport:
    input_rows: int
    valid_rows: int
    quarantined_rows: int
    issue_counts: tuple[tuple[str, int], ...] = ()

    @property
    def has_warnings(self) -> bool:
        return self.quarantined_rows > 0

    def issue_count(self, issue: str) -> int:
        return dict(self.issue_counts).get(issue, 0)

    def summary(self) -> str:
        if not self.has_warnings:
            return "No provider rows were quarantined"
        reasons = ", ".join(
            f"{ISSUE_LABELS.get(issue, issue)} ({count})" for issue, count in self.issue_counts
        )
        return f"Quarantined {self.quarantined_rows} of {self.input_rows} provider rows: {reasons}"


@dataclass(frozen=True, slots=True)
class PreparedCandleBatch:
    candles: pd.DataFrame
    quality_report: DataQualityReport


class DataQualityError(ValueError):
    def __init__(self, message: str, quality_report: DataQualityReport) -> None:
        super().__init__(message)
        self.quality_report = quality_report


def prepare_candles(frame: pd.DataFrame, interval: str, source: str) -> pd.DataFrame:
    """Return sorted, validated candles in the application's storage schema."""

    return prepare_candles_with_report(frame, interval, source).candles


def prepare_candles_with_report(
    frame: pd.DataFrame,
    interval: str,
    source: str,
) -> PreparedCandleBatch:
    """Return valid candles plus a reasoned report for quarantined rows."""

    required = {"open", "high", "low", "close", "volume"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"Provider data is missing columns: {', '.join(sorted(missing))}")
    if interval not in INTERVAL_LENGTHS:
        raise ValueError(f"Unsupported interval: {interval}")

    clean = frame.copy()
    if "opened_at_utc" not in clean.columns:
        clean.index = clean.index.rename(None)
        clean["opened_at_utc"] = pd.to_datetime(clean.index, utc=True, errors="coerce")
    else:
        clean["opened_at_utc"] = pd.to_datetime(clean["opened_at_utc"], utc=True, errors="coerce")
    clean = clean.reset_index(drop=True)

    numeric_columns = ["open", "high", "low", "close", "volume"]
    supplied_volume = clean["volume"].notna()
    clean[numeric_columns] = clean[numeric_columns].apply(pd.to_numeric, errors="coerce")
    price_columns = ["open", "high", "low", "close"]
    prices_present = clean[price_columns].notna().all(axis=1)
    issues = {
        "invalid_timestamp": clean["opened_at_utc"].isna(),
        "duplicate_timestamp": clean["opened_at_utc"].duplicated(keep="last")
        & clean["opened_at_utc"].notna(),
        "missing_price": ~prices_present,
        "non_positive_price": prices_present & (clean[price_columns] <= 0).any(axis=1),
        "high_below_price": prices_present
        & (clean["high"] < clean[["open", "close", "low"]].max(axis=1)),
        "low_above_price": prices_present
        & (clean["low"] > clean[["open", "close", "high"]].min(axis=1)),
        "invalid_volume": supplied_volume & clean["volume"].isna(),
        "negative_volume": clean["volume"].notna() & (clean["volume"] < 0),
    }
    invalid = pd.Series(False, index=clean.index)
    for mask in issues.values():
        invalid |= mask.fillna(False)
    issue_counts = tuple(
        (issue, int(mask.sum())) for issue, mask in issues.items() if int(mask.sum()) > 0
    )
    report = DataQualityReport(
        input_rows=len(clean),
        valid_rows=int((~invalid).sum()),
        quarantined_rows=int(invalid.sum()),
        issue_counts=issue_counts,
    )
    clean = clean.loc[~invalid].sort_values("opened_at_utc").copy()
    if clean.empty:
        message = "Provider returned no rows" if frame.empty else report.summary()
        raise DataQualityError(f"Provider returned no valid candles. {message}", report)

    now = pd.Timestamp(datetime.now(UTC))
    clean["is_complete"] = clean["opened_at_utc"] + INTERVAL_LENGTHS[interval] <= now
    clean["is_adjusted"] = True
    clean["source"] = source
    clean["fetched_at_utc"] = now
    prepared = clean[
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
    return PreparedCandleBatch(prepared, report)
