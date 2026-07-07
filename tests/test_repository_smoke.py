from __future__ import annotations

from datetime import UTC, datetime

import pandas as pd

from trading_vision.alert_repository import (
    ensure_default_rule,
    insert_alert_event,
    list_recent_alerts,
    unread_alert_count,
)
from trading_vision.data_quality import prepare_candles
from trading_vision.database import connect
from trading_vision.drawing_repository import list_drawings, save_drawing
from trading_vision.models import PatternMatch, PatternPoint, Symbol
from trading_vision.pattern_repository import get_pattern, upsert_pattern
from trading_vision.repositories import upsert_candles, upsert_symbol
from trading_vision.scanner_repository import (
    count_candles,
    finish_scan_run,
    get_heartbeat,
    list_active_bist_symbols,
    start_scan_run,
    update_heartbeat,
)
from trading_vision.scanner_results import PatternResultFilters
from trading_vision.scanner_results_repository import (
    recent_scan_errors,
    recent_scan_warnings,
    search_pattern_results,
)
from trading_vision.watchlist_repository import (
    add_watchlist_item,
    create_watchlist,
    list_watchlist_items,
)


def test_every_repository_module_smokes_against_fresh_database(database_path) -> None:
    now = datetime(2026, 7, 7, 12, tzinfo=UTC)
    with connect(database_path) as connection:
        symbol = upsert_symbol(
            connection,
            Symbol("SMOKE", "SMOKE.IS", "Smoke Test", "XIST", "TRY", True),
        )
        candles = prepare_candles(
            pd.DataFrame(
                {
                    "open": [10, 11],
                    "high": [11, 12],
                    "low": [9, 10],
                    "close": [10.5, 11.5],
                    "volume": [1_000, 1_100],
                },
                index=pd.to_datetime(["2026-07-06", "2026-07-07"], utc=True),
            ),
            "1d",
            "fixture",
        )
        upsert_candles(connection, symbol.id, "1d", candles)

        point = PatternPoint("breakout", 1, now, 11.5)
        match = PatternMatch(
            pattern_type="resistance_breakout",
            direction="bullish",
            state="confirmed",
            started_at=now,
            ended_at=now,
            confirmed_at=now,
            score=82,
            boundary_price=11,
            target_price=13,
            invalidation_price=10,
            points=(point,),
            reasons=("repository smoke",),
            parameters={"source": "test"},
            detector_version="test",
        )
        transition = upsert_pattern(connection, "smoke-pattern", symbol.id, "1d", match)
        assert transition is not None
        rule = ensure_default_rule(connection, 70, ("resistance_breakout",))
        inserted_alert = insert_alert_event(
            connection,
            "smoke-alert",
            rule,
            transition,
            symbol,
            "1d",
            match,
        )

        run_id = start_scan_run(connection, now, "1d", "fixture", 1, False)
        finish_scan_run(
            connection,
            run_id,
            now,
            succeeded=1,
            failed=0,
            candles_added=2,
            patterns_added=1,
            status="completed",
            errors=[],
            warnings=["SMOKE.IS: synthetic warning"],
        )
        update_heartbeat(connection, "sleeping", 123, now, now, last_run_id=run_id)

        watchlist = create_watchlist(connection, "Repository smoke")
        add_watchlist_item(connection, watchlist.id, symbol.id, ("1d",))
        drawing = save_drawing(connection, symbol.id, "1d", "line", {"type": "line", "y0": 10})

        results = search_pattern_results(
            connection,
            PatternResultFilters(symbol="SMOKE", pattern_type="resistance_breakout"),
        )

        assert list_active_bist_symbols(connection) == [symbol]
        assert count_candles(connection, symbol.id, "1d") == 2
        assert get_pattern(connection, "smoke-pattern")["state"] == "confirmed"
        assert inserted_alert is True
        assert unread_alert_count(connection) == 1
        assert list_recent_alerts(connection)[0].fingerprint == "smoke-alert"
        assert get_heartbeat(connection)["last_run_id"] == run_id
        assert recent_scan_errors(connection) == []
        assert recent_scan_warnings(connection) == ["SMOKE.IS: synthetic warning"]
        assert list_watchlist_items(connection, watchlist.id)[0].symbol == symbol
        assert list_drawings(connection, symbol.id, "1d") == (drawing,)
        assert results[0].pattern_id == "smoke-pattern"
