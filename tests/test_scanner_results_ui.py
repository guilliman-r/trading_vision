from __future__ import annotations

from tests.test_alerts import alert_scanner, fresh_breakout_fixture, stored_test_symbol
from tests.test_ui_endpoints import StaticProvider
from trading_vision.config import Settings
from trading_vision.database import connect
from trading_vision.ui.app import create_app


def test_scanner_workspace_callback_renders_filtered_result(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        alert_scanner(connection).scan(symbol, "1d", fresh_breakout_fixture())
    app = create_app(Settings(database_path=database_path), StaticProvider())
    response = app.server.test_client().post(
        "/_dash-update-component",
        json=_scanner_request(app),
    )
    payload = response.get_json()["response"]
    assert response.status_code == 200
    assert "TEST.IS" in str(payload["scanner-results-table"]["children"])
    assert "?symbol=TEST.IS" in str(payload["scanner-results-table"]["children"])
    assert payload["scanner-result-count"]["children"].endswith("results")
    assert len(payload["scanner-diagnostics"]["children"]) >= 10


def test_scanner_export_callback_downloads_current_filter(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        alert_scanner(connection).scan(symbol, "1d", fresh_breakout_fixture())
    app = create_app(Settings(database_path=database_path), StaticProvider())
    response = app.server.test_client().post(
        "/_dash-update-component",
        json=_export_request(app),
    )
    payload = response.get_json()["response"]["scanner-download"]["data"]
    assert response.status_code == 200
    assert payload["filename"] == "trading-vision-patterns.csv"
    assert "TEST.IS,1d,resistance_breakout" in payload["content"]


def _scanner_request(app) -> dict:
    output_key = next(key for key in app.callback_map if "scanner-results-table.children" in key)
    return {
        "output": output_key,
        "outputs": [
            {"id": "scanner-results-table", "property": "children"},
            {"id": "scanner-diagnostics", "property": "children"},
            {"id": "scanner-result-count", "property": "children"},
        ],
        "inputs": [
            {"id": "scanner-poll", "property": "n_intervals", "value": 1},
            {"id": "scanner-refresh", "property": "n_clicks", "value": None},
            {"id": "filter-symbol", "property": "value", "value": "TEST"},
            {"id": "filter-interval", "property": "value", "value": "1d"},
            {
                "id": "filter-pattern",
                "property": "value",
                "value": "resistance_breakout",
            },
            {"id": "filter-direction", "property": "value", "value": "bullish"},
            {"id": "filter-state", "property": "value", "value": "confirmed"},
            {"id": "filter-score", "property": "value", "value": 80},
            {"id": "filter-age", "property": "value", "value": 90},
        ],
        "state": [],
        "changedPropIds": ["scanner-poll.n_intervals"],
    }


def _export_request(app) -> dict:
    return {
        "output": "scanner-download.data",
        "outputs": {"id": "scanner-download", "property": "data"},
        "inputs": [{"id": "scanner-export", "property": "n_clicks", "value": 1}],
        "state": [
            {"id": "filter-symbol", "property": "value", "value": "TEST"},
            {"id": "filter-interval", "property": "value", "value": "1d"},
            {
                "id": "filter-pattern",
                "property": "value",
                "value": "resistance_breakout",
            },
            {"id": "filter-direction", "property": "value", "value": "bullish"},
            {"id": "filter-state", "property": "value", "value": "confirmed"},
            {"id": "filter-score", "property": "value", "value": 80},
            {"id": "filter-age", "property": "value", "value": 90},
        ],
        "changedPropIds": ["scanner-export.n_clicks"],
    }
