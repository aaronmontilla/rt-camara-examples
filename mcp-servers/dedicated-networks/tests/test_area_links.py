"""
tests/test_area_links.py
────────────────────────
Every service area the server returns must carry a GeoJSON map link (or an
explicit note saying why there is none), in every tool and output format, and
the model must be told to show it.
"""

import asyncio
import json
import urllib.parse

import pytest

from camara.geo import (
    GEOJSON_LINK_RULE,
    GEOJSON_UNAVAILABLE_NOTE,
    area_geojson_url,
    area_to_geojson,
    combined_geojson_url,
    geojson_url,
    with_geojson_url,
)
from camara.models import ResponseFormat
from camara.tools import areas as areas_module
from tests.tool_results import text_of

GEOJSON_PREFIX = "https://geojson.io/#data=data:application/json,"

CIRCLE_AREA = {
    "id": "625b2d4b-4da7-4f07-9169-e60ffdf76671",
    "name": "Roland Garros Tennis Courts",
    "area": {
        "areaType": "CIRCLE",
        "center": {"latitude": 48.845867, "longitude": 2.253156},
        "radius": 1000,
    },
}

POLYGON_AREA = {
    "id": "C9019B9D-FD78-497C-AE07-636CD60202AD",
    "name": "Stade de France",
    "area": {
        "areaType": "POLYGON",
        "boundary": [
            {"longitude": 2.35941, "latitude": 48.92493},
            {"longitude": 2.36100, "latitude": 48.92497},
            {"longitude": 2.36050, "latitude": 48.92600},
        ],
    },
}

BROKEN_AREA = {"id": "broken-1", "name": "No geometry", "area": {"areaType": "POLYGON", "boundary": []}}


def _decode(url: str) -> dict:
    assert url.startswith(GEOJSON_PREFIX)
    return json.loads(urllib.parse.unquote(url[len(GEOJSON_PREFIX):]))


def _tool(name: str):
    import server

    return next(t for t in server.mcp._tool_manager.list_tools() if t.name == name)


# ── geo helpers ────────────────────────────────────────────────────────────────

def test_circle_becomes_closed_64_point_polygon():
    feature = area_to_geojson(CIRCLE_AREA)
    ring = feature["geometry"]["coordinates"][0]

    assert feature["geometry"]["type"] == "Polygon"
    assert len(ring) == 65
    assert ring[0] == ring[-1]


def test_polygon_ring_is_closed_and_lon_lat_ordered():
    ring = area_to_geojson(POLYGON_AREA)["geometry"]["coordinates"][0]

    assert ring[0] == ring[-1]
    assert ring[0] == [2.35941, 48.92493]


def test_area_geojson_url_roundtrips_to_the_feature():
    feature = _decode(area_geojson_url(CIRCLE_AREA))

    assert feature["type"] == "Feature"
    assert feature["properties"]["id"] == CIRCLE_AREA["id"]


def test_malformed_geometry_has_no_url():
    assert area_geojson_url(BROKEN_AREA) is None
    assert area_geojson_url({"id": "x"}) is None


def test_with_geojson_url_adds_url_for_valid_area():
    out = with_geojson_url(CIRCLE_AREA)

    assert out["geojsonUrl"].startswith(GEOJSON_PREFIX)
    assert "geojsonNote" not in out
    assert "geojsonUrl" not in CIRCLE_AREA  # input is not mutated


def test_with_geojson_url_adds_note_for_malformed_area():
    out = with_geojson_url(BROKEN_AREA)

    assert out["geojsonNote"] == GEOJSON_UNAVAILABLE_NOTE
    assert "geojsonUrl" not in out


def test_combined_url_draws_every_drawable_area_and_skips_broken_ones():
    collection = _decode(combined_geojson_url([CIRCLE_AREA, BROKEN_AREA, POLYGON_AREA]))

    assert collection["type"] == "FeatureCollection"
    assert [f["properties"]["id"] for f in collection["features"]] == [
        CIRCLE_AREA["id"],
        POLYGON_AREA["id"],
    ]


def test_combined_url_is_none_when_nothing_is_drawable():
    assert combined_geojson_url([]) is None
    assert combined_geojson_url([BROKEN_AREA]) is None


def test_url_size_for_a_detailed_polygon_is_reported(capsys):
    """Not an assertion on a limit — documents how long links get for big polygons."""
    boundary = [
        {"longitude": 2.0 + i * 1e-4, "latitude": 48.0 + ((-1) ** i) * i * 1e-4}
        for i in range(500)
    ]
    url = area_geojson_url({"id": "big", "area": {"areaType": "POLYGON", "boundary": boundary}})

    assert url is not None
    print(f"\n500-vertex polygon -> URL of {len(url)} characters")


# ── area tools ─────────────────────────────────────────────────────────────────

def _patch_api(monkeypatch, payload):
    async def fake_api_request(*args, **kwargs):
        return payload

    monkeypatch.setattr(areas_module, "api_request", fake_api_request)


def test_retrieve_json_gives_each_area_a_url_and_a_combined_url(monkeypatch):
    _patch_api(monkeypatch, [CIRCLE_AREA, POLYGON_AREA])
    fn = text_of(_tool("camara_retrieve_service_areas").fn)

    result = json.loads(asyncio.run(fn(response_format=ResponseFormat.JSON)))

    assert all(a["geojsonUrl"].startswith(GEOJSON_PREFIX) for a in result["areas"])
    assert len(_decode(result["geojsonUrl"])["features"]) == 2


def test_retrieve_json_flags_areas_without_a_link(monkeypatch):
    _patch_api(monkeypatch, [CIRCLE_AREA, BROKEN_AREA])
    fn = text_of(_tool("camara_retrieve_service_areas").fn)

    result = json.loads(asyncio.run(fn(response_format=ResponseFormat.JSON)))

    by_id = {a["id"]: a for a in result["areas"]}
    assert "geojsonUrl" in by_id[CIRCLE_AREA["id"]]
    assert by_id["broken-1"]["geojsonNote"] == GEOJSON_UNAVAILABLE_NOTE


def test_retrieve_json_without_areas_has_no_combined_url(monkeypatch):
    _patch_api(monkeypatch, [])
    fn = text_of(_tool("camara_retrieve_service_areas").fn)

    result = json.loads(asyncio.run(fn(response_format=ResponseFormat.JSON)))

    assert result == {"areas": [], "count": 0}


def test_retrieve_markdown_links_every_area_and_the_combined_map(monkeypatch):
    _patch_api(monkeypatch, [CIRCLE_AREA, POLYGON_AREA])
    fn = text_of(_tool("camara_retrieve_service_areas").fn)

    out = asyncio.run(fn())

    assert out.count("**GeoJSON map**: [View area](") == 2
    assert "[View all areas](" in out


def test_retrieve_markdown_single_area_has_no_redundant_combined_link(monkeypatch):
    _patch_api(monkeypatch, [CIRCLE_AREA])
    fn = text_of(_tool("camara_retrieve_service_areas").fn)

    out = asyncio.run(fn())

    assert "[View area](" in out
    assert "[View all areas](" not in out


def test_retrieve_markdown_states_when_an_area_has_no_link(monkeypatch):
    _patch_api(monkeypatch, [BROKEN_AREA])
    fn = text_of(_tool("camara_retrieve_service_areas").fn)

    out = asyncio.run(fn())

    assert "unavailable" in out
    assert GEOJSON_UNAVAILABLE_NOTE in out


def test_get_area_json_and_markdown_both_carry_the_link(monkeypatch):
    _patch_api(monkeypatch, CIRCLE_AREA)
    fn = text_of(_tool("camara_get_area").fn)
    area_id = CIRCLE_AREA["id"]

    as_json = json.loads(
        asyncio.run(fn(areaId=area_id, response_format=ResponseFormat.JSON))
    )
    as_md = asyncio.run(fn(areaId=area_id))

    assert as_json["geojsonUrl"].startswith(GEOJSON_PREFIX)
    assert as_json["geojsonUrl"] in as_md


def test_get_area_json_flags_missing_link(monkeypatch):
    _patch_api(monkeypatch, BROKEN_AREA)
    fn = text_of(_tool("camara_get_area").fn)

    out = json.loads(
        asyncio.run(fn(areaId="broken-1", response_format=ResponseFormat.JSON))
    )

    assert out["geojsonNote"] == GEOJSON_UNAVAILABLE_NOTE


# ── picker tool (disabled by default, but must not break the rule if enabled) ──

def test_picker_areas_carry_links(monkeypatch):
    from mcp.server.apps import Apps

    from camara.tools import picker as picker_module

    async def fake_api_request(*args, **kwargs):
        return [CIRCLE_AREA, BROKEN_AREA]

    monkeypatch.setattr(picker_module, "api_request", fake_api_request)
    apps = Apps()
    apps.add_html_resource(picker_module.AREA_PICKER_URI, "<html></html>")
    picker_module.register_picker_tool(apps)
    fn = text_of(next(b.fn for b in apps.tools() if b.fn.__name__ == "camara_pick_location"))


    result = json.loads(asyncio.run(fn()))

    assert result["areas"][0]["geojsonUrl"].startswith(GEOJSON_PREFIX)
    assert result["areas"][1]["geojsonNote"] == GEOJSON_UNAVAILABLE_NOTE
    assert result["geojsonUrl"].startswith(GEOJSON_PREFIX)


# ── instructions to the model ─────────────────────────────────────────────────

def test_server_instructions_carry_the_rule():
    import server

    assert GEOJSON_LINK_RULE in server.SERVER_INSTRUCTIONS
    assert server.mcp.instructions == server.SERVER_INSTRUCTIONS


@pytest.mark.parametrize("name", ["camara_retrieve_service_areas", "camara_get_area"])
def test_area_tool_descriptions_tell_the_model_to_show_the_link(name):
    description = _tool(name).description

    assert "GeoJSON" in description
    assert "immediately preceding message" in description


def test_workflow_prompts_carry_the_rule():
    import server

    prompts = {p.name: p for p in server.mcp._prompt_manager.list_prompts()}
    for name in ("dedicated_network_workflow", "discover_profiles_and_areas"):
        text = prompts[name].fn()
        assert "GeoJSON map link" in text, name
        assert "immediately preceding message" in text, name
