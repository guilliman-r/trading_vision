from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from trading_vision.config import Settings
from trading_vision.data_quality import prepare_candles
from trading_vision.providers.base import FetchResult, MarketDataProvider
from trading_vision.ui.app import create_app


class StaticProvider(MarketDataProvider):
    name = "fixture"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        frame = pd.DataFrame(
            {
                "open": [100.0, 102.0],
                "high": [104.0, 106.0],
                "low": [99.0, 101.0],
                "close": [102.0, 105.0],
                "volume": [1000.0, 1200.0],
            },
            index=pd.to_datetime(["2025-01-01", "2025-01-02"], utc=True),
        )
        return FetchResult(symbol=symbol, candles=prepare_candles(frame, interval, self.name))


def test_dash_page_layout_dependencies_and_css_are_served(database_path) -> None:
    app = create_app(Settings(database_path=database_path), StaticProvider())
    client = app.server.test_client()

    page = client.get("/")
    layout = client.get("/_dash-layout")
    dependencies = client.get("/_dash-dependencies")
    stylesheet = client.get("/assets/app.css")

    assert page.status_code == 200
    assert b"Trading Vision" in page.data
    assert layout.status_code == 200
    assert b'"app-root"' in layout.data
    assert dependencies.status_code == 200
    assert b"price-chart.figure" in dependencies.data
    assert stylesheet.status_code == 200
    assert b".workspace" in stylesheet.data


def test_load_button_callback_returns_chart_and_snapshot(database_path) -> None:
    app = create_app(Settings(database_path=database_path), StaticProvider())
    client = app.server.test_client()
    response = client.post(
        "/_dash-update-component",
        json=_load_callback_request(app),
    )
    payload = response.get_json()["response"]
    assert response.status_code == 200
    assert payload["chart-title"]["children"] == "THYAO.IS"
    assert payload["data-status"]["children"] == "Live · 0 patterns"
    assert len(payload["price-chart"]["figure"]["data"]) == 2
    assert payload["symbol-input"]["value"] == "THYAO.IS"


def test_chart_callback_can_run_in_a_different_thread(database_path) -> None:
    app = create_app(Settings(database_path=database_path), StaticProvider())
    creating_thread = threading.get_ident()

    def post_from_worker_thread():
        with app.server.test_client() as client:
            response = client.post(
                "/_dash-update-component",
                json=_load_callback_request(app),
            )
            return threading.get_ident(), response.status_code, response.get_json()

    with ThreadPoolExecutor(max_workers=1) as executor:
        callback_thread, status_code, payload = executor.submit(post_from_worker_thread).result()

    assert callback_thread != creating_thread
    assert status_code == 200
    assert payload["response"]["chart-title"]["children"] == "THYAO.IS"


def test_theme_button_callback_toggles_to_light(database_path) -> None:
    app = create_app(Settings(database_path=database_path), StaticProvider())
    client = app.server.test_client()
    output_key = next(key for key in app.callback_map if "app-root.className" in key)
    response = client.post(
        "/_dash-update-component",
        json={
            "output": output_key,
            "outputs": [
                {"id": "app-root", "property": "className"},
                {"id": "theme-button", "property": "children"},
            ],
            "inputs": [{"id": "theme-button", "property": "n_clicks", "value": 1}],
            "state": [],
            "changedPropIds": ["theme-button.n_clicks"],
        },
    )
    payload = response.get_json()["response"]
    assert response.status_code == 200
    assert payload["app-root"]["className"] == "app-shell theme-light"
    assert payload["theme-button"]["children"] == "Dark mode"


def _load_callback_request(app) -> dict:
    output_key = next(key for key in app.callback_map if "price-chart.figure" in key)
    return {
        "output": output_key,
        "outputs": [
            {"id": "price-chart", "property": "figure"},
            {"id": "chart-title", "property": "children"},
            {"id": "data-status", "property": "children"},
            {"id": "data-status", "property": "className"},
            {"id": "chart-details", "property": "children"},
            {"id": "symbol-input", "property": "value"},
        ],
        "inputs": [
            {"id": "load-button", "property": "n_clicks", "value": 1},
            {"id": "symbol-input", "property": "n_submit", "value": None},
            {"id": "refresh-button", "property": "n_clicks", "value": None},
            {"id": "interval-select", "property": "value", "value": "1d"},
            {
                "id": json.dumps({"symbol": ["ALL"], "type": "quick-symbol"}),
                "property": "n_clicks",
                "value": [None, None, None, None, None, None],
            },
        ],
        "state": [{"id": "symbol-input", "property": "value", "value": "THYAO"}],
        "changedPropIds": ["load-button.n_clicks"],
    }
