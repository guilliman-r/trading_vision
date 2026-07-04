from __future__ import annotations

import json

from tests.test_alerts import alert_scanner, fresh_breakout_fixture, stored_test_symbol
from tests.test_ui_endpoints import StaticProvider
from trading_vision.config import Settings
from trading_vision.database import connect
from trading_vision.ui.app import create_app


def test_alert_callback_displays_and_acknowledges_unread_event(database_path) -> None:
    with connect(database_path) as connection:
        symbol = stored_test_symbol(connection)
        alert_scanner(connection).scan(symbol, "1d", fresh_breakout_fixture())

    app = create_app(Settings(database_path=database_path), StaticProvider())
    client = app.server.test_client()
    initial = client.post("/_dash-update-component", json=_alert_request(app, "alert-poll"))
    initial_payload = initial.get_json()["response"]
    assert initial.status_code == 200
    assert initial_payload["alert-count"]["children"] == "1"
    assert "TEST.IS" in json.dumps(initial_payload["alert-list"])

    acknowledged = client.post("/_dash-update-component", json=_alert_request(app, "alert-ack-all"))
    acknowledged_payload = acknowledged.get_json()["response"]
    assert acknowledged.status_code == 200
    assert acknowledged_payload["alert-count"]["children"] == "0"


def test_alert_chart_link_loads_its_symbol_context(database_path) -> None:
    with connect(database_path) as connection:
        stored_test_symbol(connection)
        connection.commit()
    app = create_app(Settings(database_path=database_path), StaticProvider())
    request = _chart_link_request(app)
    response = app.server.test_client().post("/_dash-update-component", json=request)
    payload = response.get_json()["response"]
    assert response.status_code == 200
    assert payload["chart-title"]["children"] == "TEST.IS"
    assert payload["symbol-input"]["value"] == "TEST.IS"


def _alert_request(app, triggered_id: str) -> dict:
    output_key = next(key for key in app.callback_map if "alert-count.children" in key)
    return {
        "output": output_key,
        "outputs": [
            {"id": "alert-count", "property": "children"},
            {"id": "alert-list", "property": "children"},
        ],
        "inputs": [
            {"id": "alert-poll", "property": "n_intervals", "value": 1},
            {"id": "alert-ack-all", "property": "n_clicks", "value": None},
            {
                "id": json.dumps({"alert_id": ["ALL"], "type": "alert-ack"}),
                "property": "n_clicks",
                "value": [],
            },
            {
                "id": json.dumps({"alert_id": ["ALL"], "type": "alert-mute"}),
                "property": "n_clicks",
                "value": [],
            },
        ],
        "state": [],
        "changedPropIds": [f"{triggered_id}.n_clicks"],
    }


def _chart_link_request(app) -> dict:
    from tests.test_ui_endpoints import _load_callback_request

    request = _load_callback_request(app)
    request["inputs"][-1]["value"] = "?symbol=TEST.IS&interval=1d"
    request["changedPropIds"] = ["app-url.search"]
    return request
