from __future__ import annotations

import pytest

from trading_vision.database import connect
from trading_vision.models import Symbol
from trading_vision.repositories import upsert_symbol
from trading_vision.watchlist_repository import (
    add_watchlist_item,
    create_watchlist,
    list_watchlist_items,
    list_watchlists,
    remove_watchlist_item,
    reorder_watchlist_item,
)


def test_watchlist_create_and_list(database_path) -> None:
    with connect(database_path) as connection:
        watchlist = create_watchlist(connection, " BIST favorites ", "Most watched")
        same = create_watchlist(connection, "BIST favorites", "Updated description")
        watchlists = list_watchlists(connection)

    assert same.id == watchlist.id
    assert same.description == "Updated description"
    assert watchlists == (same,)


def test_watchlist_add_reorder_and_remove_items(database_path) -> None:
    with connect(database_path) as connection:
        thyao = upsert_symbol(connection, Symbol("THYAO", "THYAO.IS", is_bist=True))
        garan = upsert_symbol(connection, Symbol("GARAN", "GARAN.IS", is_bist=True))
        asels = upsert_symbol(connection, Symbol("ASELS", "ASELS.IS", is_bist=True))
        watchlist = create_watchlist(connection, "Trading candidates")

        add_watchlist_item(connection, watchlist.id, thyao.id, ("1d", "1h"))
        add_watchlist_item(connection, watchlist.id, garan.id, ("1d",))
        add_watchlist_item(connection, watchlist.id, asels.id, ("1h",))

        reordered = reorder_watchlist_item(connection, watchlist.id, asels.id, 1)
        removed = remove_watchlist_item(connection, watchlist.id, thyao.id)
        missing = remove_watchlist_item(connection, watchlist.id, thyao.id)
        remaining = list_watchlist_items(connection, watchlist.id)

    assert [item.symbol.provider_symbol for item in reordered] == [
        "ASELS.IS",
        "THYAO.IS",
        "GARAN.IS",
    ]
    assert [item.position for item in reordered] == [1, 2, 3]
    assert removed is True
    assert missing is False
    assert [item.symbol.provider_symbol for item in remaining] == ["ASELS.IS", "GARAN.IS"]
    assert [item.position for item in remaining] == [1, 2]
    assert remaining[0].scan_intervals == ("1h",)


def test_watchlist_rejects_empty_name_unknown_list_and_unsupported_scan_interval(
    database_path,
) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("THYAO", "THYAO.IS", is_bist=True))
        watchlist = create_watchlist(connection, "Safe list")

        with pytest.raises(ValueError, match="name"):
            create_watchlist(connection, " ")
        with pytest.raises(ValueError, match="Unsupported watchlist scan intervals"):
            add_watchlist_item(connection, watchlist.id, symbol.id, ("15m",))
        with pytest.raises(ValueError, match="Unknown watchlist"):
            add_watchlist_item(connection, 999, symbol.id)
