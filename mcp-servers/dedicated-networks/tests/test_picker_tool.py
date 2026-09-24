"""
tests/test_picker_tool.py
───────────────────────────
Exercises camara_pick_location itself (the plain async function — the
Apps.tool()/mcp.tool() decorators return fn unchanged, so it's callable
directly with asyncio.run, no test client needed).
"""

import asyncio
import json

import pytest

from camara.models import PickLocationInput
from camara.tools import picker as picker_module

CIRCLE_AREA = {
    "id": "625b2d4b-4da7-4f07-9169-e60ffdf76671",
    "name": "Roland Garros Tennis Courts",
    "area": {
        "areaType": "CIRCLE",
        "center": {"latitude": 48.845867, "longitude": 2.253156},
        "radius": 1000,
    },
    "networkProfiles": ["7e54f738-..."],
    "qosProfiles": ["QOS_S"],
}


def _register_and_get_tool():
    from mcp.server.apps import Apps

    apps = Apps()
    apps.add_html_resource(picker_module.AREA_PICKER_URI, "<html></html>")
    picker_module.register_picker_tool(apps)
    return next(b.fn for b in apps.tools() if b.fn.__name__ == "camara_pick_location")


def test_returns_areas_bounds_and_tile_url(monkeypatch):
    async def fake_api_request(api, path, method="GET", body=None, params=None):
        assert api == "areas"
        assert path == "/retrieve-service-areas"
        assert method == "POST"
        assert body == {}
        return [CIRCLE_AREA]

    monkeypatch.setattr(picker_module, "api_request", fake_api_request)
    tool = _register_and_get_tool()

    result = json.loads(asyncio.run(tool(PickLocationInput())))

    assert result["areas"] == [CIRCLE_AREA]
    assert result["bounds"] is not None
    assert result["tileUrl"] == picker_module.MAP_TILE_URL
    assert "center" not in result
    assert "zoom" not in result


def test_passes_through_explicit_center_and_zoom(monkeypatch):
    async def fake_api_request(*args, **kwargs):
        return [CIRCLE_AREA]

    monkeypatch.setattr(picker_module, "api_request", fake_api_request)
    tool = _register_and_get_tool()

    result = json.loads(asyncio.run(tool(PickLocationInput(latitude=48.8, longitude=2.3, zoom=14))))

    assert result["center"] == {"latitude": 48.8, "longitude": 2.3}
    assert result["zoom"] == 14


def test_forwards_profile_filters_in_request_body(monkeypatch):
    seen_body = {}

    async def fake_api_request(api, path, method="GET", body=None, params=None):
        seen_body.update(body or {})
        return []

    monkeypatch.setattr(picker_module, "api_request", fake_api_request)
    tool = _register_and_get_tool()

    asyncio.run(tool(PickLocationInput(byNetworkProfileId="abc", byQosProfileName="QOS_S")))

    assert seen_body == {"byNetworkProfileId": "abc", "byQosProfileName": "QOS_S"}


def test_empty_areas_returns_message_not_an_error(monkeypatch):
    async def fake_api_request(*args, **kwargs):
        return []

    monkeypatch.setattr(picker_module, "api_request", fake_api_request)
    tool = _register_and_get_tool()

    result = json.loads(asyncio.run(tool(PickLocationInput())))

    assert result["areas"] == []
    assert result["bounds"] is None
    assert "message" in result


def test_connection_error_is_handled_not_raised(monkeypatch):
    import httpx

    async def fake_api_request(*args, **kwargs):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(picker_module, "api_request", fake_api_request)
    tool = _register_and_get_tool()

    output = asyncio.run(tool(PickLocationInput()))

    assert "Cannot connect" in output
