from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from trading_vision.config import Settings
from trading_vision.data_quality import prepare_candles, prepare_candles_with_report
from trading_vision.models import PatternMatch, PatternPoint, Symbol
from trading_vision.providers.base import FetchResult, MarketDataProvider
from trading_vision.services.market_data import ChartLoadResult
from trading_vision.ui.app import create_app
from trading_vision.ui.callbacks import _successful_chart_result


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


class CountingProvider(StaticProvider):
    def __init__(self) -> None:
        self.requests = 0

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        self.requests += 1
        return super().fetch_history(symbol, interval)


class GapProvider(MarketDataProvider):
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
            index=pd.to_datetime(["2026-01-02", "2026-01-06"], utc=True),
        )
        return FetchResult(symbol=symbol, candles=prepare_candles(frame, interval, self.name))


class QuarantineProvider(MarketDataProvider):
    name = "fixture"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        frame = pd.DataFrame(
            {
                "open": [100.0, 102.0],
                "high": [104.0, 106.0],
                "low": [99.0, 101.0],
                "close": [102.0, 105.0],
                "volume": [-1.0, 1200.0],
            },
            index=pd.to_datetime(["2025-01-01", "2025-01-02"], utc=True),
        )
        prepared = prepare_candles_with_report(frame, interval, self.name)
        return FetchResult(
            symbol=symbol,
            candles=prepared.candles,
            quality_report=prepared.quality_report,
        )


class FutureCandleProvider(MarketDataProvider):
    name = "fixture"

    def fetch_history(self, symbol: str, interval: str) -> FetchResult:
        frame = pd.DataFrame(
            {
                "open": [100.0],
                "high": [104.0],
                "low": [99.0],
                "close": [102.0],
                "volume": [1000.0],
            },
            index=pd.to_datetime(["2099-01-05"], utc=True),
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
    assert b'"scanner-results-table"' in layout.data
    assert b'"responsive":true' in layout.data
    assert b'"height":"680px"' in layout.data
    assert dependencies.status_code == 200
    assert b"price-chart.figure" in dependencies.data
    assert stylesheet.status_code == 200
    assert b".workspace" in stylesheet.data
    assert b".chart { height: 680px" in stylesheet.data
    assert b".interval-select .Select-control" in stylesheet.data
    assert b"background: var(--panel-raised) !important" in stylesheet.data


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
    assert "Fixture" in payload["chart-meta"]["children"]
    assert "Latest" in payload["chart-meta"]["children"]
    assert "Stale feed" in payload["chart-meta"]["children"]
    assert payload["data-status"]["children"] == "Live · 0 active patterns"
    assert len(payload["price-chart"]["figure"]["data"]) == 2
    assert payload["symbol-input"]["value"] == "THYAO.IS"


def test_successful_chart_result_keeps_patterns_out_of_default_plot() -> None:
    times = pd.date_range("2026-01-01", periods=4, freq="D", tz="UTC")
    candles = pd.DataFrame(
        {
            "opened_at_utc": times,
            "open": [100.0, 101.0, 102.0, 103.0],
            "high": [102.0, 103.0, 104.0, 105.0],
            "low": [99.0, 100.0, 101.0, 102.0],
            "close": [101.0, 102.0, 103.0, 104.0],
            "volume": [1000.0, 1100.0, 1200.0, 1300.0],
            "source": ["fixture"] * 4,
            "is_complete": [True] * 4,
        }
    )
    pattern = PatternMatch(
        pattern_type="resistance_breakout",
        direction="bullish",
        state="forming",
        started_at=times[1].to_pydatetime(),
        ended_at=None,
        confirmed_at=None,
        score=82,
        boundary_price=104.0,
        target_price=110.0,
        invalidation_price=100.0,
        points=(
            PatternPoint("touch_1", 1, times[1].to_pydatetime(), 104.0),
            PatternPoint("touch_2", 2, times[2].to_pydatetime(), 104.0),
        ),
        reasons=("active but not painted on the main chart",),
        parameters={},
        detector_version="test-v1",
    )
    result = ChartLoadResult(
        symbol=Symbol("TEST", "TEST.IS", currency="TRY", is_bist=False),
        candles=candles,
        patterns=(pattern,),
    )

    figure, _title, _meta, status, _class_name, details, _symbol = _successful_chart_result(
        result,
        "1d",
        provider_delay_seconds=60,
    )

    assert [trace.type for trace in figure.data] == ["candlestick", "bar"]
    assert status == "Live · 1 active pattern"
    rendered_details = repr(details)
    assert "Resistance Breakout" in rendered_details
    assert "Zoom" in rendered_details
    assert "Invalidation 100.00" in rendered_details
    assert "R/R 1.50" in rendered_details
    assert "?symbol=TEST.IS" in rendered_details
    assert "pattern=resistance_breakout" in rendered_details
    assert "range_from=" in rendered_details
    assert "range_to=" in rendered_details


def test_focused_chart_result_explains_and_can_clear_focus() -> None:
    times = pd.date_range("2026-01-01", periods=12, freq="D", tz="UTC")
    candles = pd.DataFrame(
        {
            "opened_at_utc": times,
            "open": [100.0] * 12,
            "high": [105.0] * 12,
            "low": [95.0] * 12,
            "close": [102.0] * 12,
            "volume": [1000.0] * 12,
            "source": ["fixture"] * 12,
            "is_complete": [True] * 12,
        }
    )
    focus_range = (times[3].to_pydatetime(), times[7].to_pydatetime())
    result = ChartLoadResult(
        symbol=Symbol("TEST", "TEST.IS", currency="TRY", is_bist=False),
        candles=candles,
    )

    figure, _title, meta, _status, _class_name, details, _symbol = _successful_chart_result(
        result,
        "1d",
        provider_delay_seconds=60,
        focus_range=focus_range,
    )

    assert figure.layout.xaxis.range[0] == focus_range[0]
    assert figure.layout.xaxis.range[1] == focus_range[1]
    assert "Focused signal" in meta
    rendered_details = repr(details)
    assert "Focused on selected signal" in rendered_details
    assert "Clear focus" in rendered_details
    assert "?symbol=TEST.IS&interval=1d" in rendered_details


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


def test_repeated_chart_load_uses_cooldown_and_refresh_bypasses_it(database_path) -> None:
    provider = CountingProvider()
    app = create_app(
        Settings(database_path=database_path, provider_cooldown_seconds=30),
        provider,
    )
    client = app.server.test_client()

    first = client.post("/_dash-update-component", json=_load_callback_request(app))
    repeated = client.post("/_dash-update-component", json=_load_callback_request(app))
    refresh_request = _load_callback_request(app)
    refresh_input = next(
        item for item in refresh_request["inputs"] if item["id"] == "refresh-button"
    )
    refresh_input["value"] = 1
    refresh_request["changedPropIds"] = ["refresh-button.n_clicks"]
    refreshed = client.post("/_dash-update-component", json=refresh_request)

    assert first.status_code == repeated.status_code == refreshed.status_code == 200
    assert provider.requests == 2


def test_chart_reuses_persisted_candles_until_explicit_refresh(database_path) -> None:
    provider = CountingProvider()
    app = create_app(
        Settings(database_path=database_path, provider_cooldown_seconds=0),
        provider,
    )
    client = app.server.test_client()

    first = client.post("/_dash-update-component", json=_load_callback_request(app))
    cached = client.post("/_dash-update-component", json=_load_callback_request(app))
    refresh_request = _load_callback_request(app)
    refresh_input = next(
        item for item in refresh_request["inputs"] if item["id"] == "refresh-button"
    )
    refresh_input["value"] = 1
    refresh_request["changedPropIds"] = ["refresh-button.n_clicks"]
    refreshed = client.post("/_dash-update-component", json=refresh_request)

    assert first.status_code == cached.status_code == refreshed.status_code == 200
    assert provider.requests == 2
    assert cached.get_json()["response"]["data-status"]["children"].startswith("Cached")


def test_chart_callback_makes_bist_candle_gap_visible(database_path) -> None:
    app = create_app(Settings(database_path=database_path), GapProvider())
    response = app.server.test_client().post(
        "/_dash-update-component",
        json=_load_callback_request(app),
    )
    payload = response.get_json()["response"]

    assert response.status_code == 200
    assert "1 data gap" in payload["chart-meta"]["children"]
    assert "1 missing completed candle" in json.dumps(payload["chart-details"]["children"])


def test_chart_callback_makes_quarantined_provider_rows_visible(database_path) -> None:
    app = create_app(Settings(database_path=database_path), QuarantineProvider())
    response = app.server.test_client().post(
        "/_dash-update-component",
        json=_load_callback_request(app),
    )
    payload = response.get_json()["response"]

    assert response.status_code == 200
    assert "1 quarantined row" in payload["chart-meta"]["children"]
    details = json.dumps(payload["chart-details"]["children"])
    assert "Quarantined 1 of 2 provider rows" in details
    assert "negative volume (1)" in details


def test_chart_callback_labels_still_forming_bist_candle(database_path) -> None:
    app = create_app(Settings(database_path=database_path), FutureCandleProvider())
    response = app.server.test_client().post(
        "/_dash-update-component",
        json=_load_callback_request(app),
    )
    payload = response.get_json()["response"]

    assert response.status_code == 200
    assert "forming candle" in payload["chart-meta"]["children"]


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
            {"id": "chart-meta", "property": "children"},
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
            {"id": "app-url", "property": "search", "value": ""},
        ],
        "state": [{"id": "symbol-input", "property": "value", "value": "THYAO"}],
        "changedPropIds": ["load-button.n_clicks"],
    }
