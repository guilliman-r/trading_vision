from __future__ import annotations

import pytest

from trading_vision.database import connect
from trading_vision.drawing_repository import (
    delete_drawing,
    delete_drawings,
    list_drawings,
    save_drawing,
)
from trading_vision.models import Symbol
from trading_vision.repositories import upsert_symbol


def test_drawing_save_list_update_and_delete(database_path) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("THYAO", "THYAO.IS", is_bist=True))
        drawing = save_drawing(
            connection,
            symbol.id,
            "1d",
            "line",
            {"type": "line", "x0": "2026-01-01", "x1": "2026-01-02", "y0": 10, "y1": 11},
        )
        updated = save_drawing(
            connection,
            symbol.id,
            "1d",
            "line",
            {"type": "line", "x0": "2026-01-01", "x1": "2026-01-03", "y0": 10, "y1": 12},
            drawing_id=drawing.id,
        )
        drawings = list_drawings(connection, symbol.id, "1d")
        deleted = delete_drawing(connection, drawing.id)
        missing = delete_drawing(connection, drawing.id)

    assert updated.id == drawing.id
    assert updated.created_at == drawing.created_at
    assert updated.updated_at >= drawing.updated_at
    assert drawings == (updated,)
    assert drawings[0].shape["y1"] == 12
    assert deleted is True
    assert missing is False


def test_drawing_delete_all_can_be_limited_to_interval(database_path) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("ASELS", "ASELS.IS", is_bist=True))
        save_drawing(connection, symbol.id, "1d", "line", {"type": "line"})
        save_drawing(connection, symbol.id, "1h", "rect", {"type": "rect"})

        deleted_daily = delete_drawings(connection, symbol.id, "1d")
        hourly = list_drawings(connection, symbol.id, "1h")
        deleted_rest = delete_drawings(connection, symbol.id)

    assert deleted_daily == 1
    assert len(hourly) == 1
    assert hourly[0].drawing_type == "rect"
    assert deleted_rest == 1


def test_drawing_rejects_empty_interval_and_type(database_path) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("GARAN", "GARAN.IS", is_bist=True))

        with pytest.raises(ValueError, match="interval"):
            save_drawing(connection, symbol.id, " ", "line", {"type": "line"})
        with pytest.raises(ValueError, match="drawing type"):
            save_drawing(connection, symbol.id, "1d", " ", {"type": "line"})


def test_drawing_update_rejects_wrong_symbol(database_path) -> None:
    with connect(database_path) as connection:
        thyao = upsert_symbol(connection, Symbol("THYAO", "THYAO.IS", is_bist=True))
        garan = upsert_symbol(connection, Symbol("GARAN", "GARAN.IS", is_bist=True))
        drawing = save_drawing(connection, thyao.id, "1d", "line", {"type": "line"})

        with pytest.raises(ValueError, match="Unknown drawing id"):
            save_drawing(connection, garan.id, "1d", "line", {"type": "line"}, drawing.id)


def test_drawing_rows_follow_symbol_delete_cascade(database_path) -> None:
    with connect(database_path) as connection:
        symbol = upsert_symbol(connection, Symbol("KCHOL", "KCHOL.IS", is_bist=True))
        save_drawing(connection, symbol.id, "1d", "line", {"type": "line"})

        connection.execute("DELETE FROM symbols WHERE id = ?", (symbol.id,))
        drawings = list_drawings(connection, symbol.id, "1d")

    assert drawings == ()
