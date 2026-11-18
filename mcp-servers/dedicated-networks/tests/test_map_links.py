"""
tests/test_map_links.py
───────────────────────
Short map links (CAMARA_MAP_LINKS=local, camara/maplinks.py): the tools return
http://127.0.0.1:<port>/map/<areaId>, and the gateway resolves it on demand
from the API and redirects to the geojson.io view with the geometry.
"""

import asyncio
import json
import socket
import urllib.parse

import httpx
import pytest

import server
from camara import geo, maplinks
from camara.tools import areas as areas_module

AREA_ID = "625b2d4b-4da7-4f07-9169-e60ffdf76671"
CIRCLE_AREA = {
    "id": AREA_ID,
    "name": "Roland Garros Tennis Courts",
    "area": {"areaType": "CIRCLE", "center": {"latitude": 48.845867, "longitude": 2.253156}, "radius": 1000},
}
POLYGON_AREA = {
    "id": "b1",
    "name": "Polygon",
    "area": {"areaType": "POLYGON", "boundary": [
        {"latitude": 48.0, "longitude": 2.0}, {"latitude": 48.1, "longitude": 2.0},
        {"latitude": 48.1, "longitude": 2.1}]},
}
BROKEN_AREA = {"id": "x9", "name": "Broken", "area": {"areaType": "CIRCLE"}}


@pytest.fixture
def local_links():
    url = maplinks.start(host="127.0.0.1", port=0)
    yield url
    maplinks.stop()


def _get(url):
    return httpx.get(url, follow_redirects=False, timeout=10)


def _decode(geojson_url):
    return json.loads(urllib.parse.unquote(geojson_url.split("#data=data:application/json,", 1)[1]))


def test_embedded_links_by_default():
    assert maplinks.base_url() is None
    assert geo.area_geojson_url(CIRCLE_AREA).startswith("https://geojson.io/#data=")


def test_local_mode_gives_short_links(local_links):
    assert geo.area_geojson_url(CIRCLE_AREA) == f"{local_links}/map/{AREA_ID}"
    assert geo.combined_geojson_url([CIRCLE_AREA, POLYGON_AREA]) == f"{local_links}/map?ids={AREA_ID},b1"
    assert geo.with_geojson_url(CIRCLE_AREA)["geojsonUrl"] == f"{local_links}/map/{AREA_ID}"


def test_an_area_without_geometry_still_gets_a_note_and_no_link(local_links):
    assert geo.area_geojson_url(BROKEN_AREA) is None
    assert "geojsonNote" in geo.with_geojson_url(BROKEN_AREA)
    assert geo.combined_geojson_url([CIRCLE_AREA, BROKEN_AREA]) == f"{local_links}/map?ids={AREA_ID}"


def test_the_tool_result_carries_the_short_link(local_links, monkeypatch):
    async def fake_api_request(*args, **kwargs):
        return [CIRCLE_AREA]

    monkeypatch.setattr(areas_module, "api_request", fake_api_request)
    result = asyncio.run(server.mcp.call_tool("camara_retrieve_service_areas", {"response_format": "json"}))
    body = json.loads(result.content[0].text)
    assert body["areas"][0]["geojsonUrl"] == f"{local_links}/map/{AREA_ID}"


def test_the_link_redirects_to_the_geometry_fetched_on_demand(local_links, monkeypatch):
    fetched = []

    def fake_fetch(area_id):
        fetched.append(area_id)
        return CIRCLE_AREA

    monkeypatch.setattr(maplinks, "fetch_area", fake_fetch)
    response = _get(f"{local_links}/map/{AREA_ID}")

    assert response.status_code == 302
    assert response.headers["location"] == geo.embedded_area_url(CIRCLE_AREA)
    assert _decode(response.headers["location"])["properties"]["id"] == AREA_ID
    assert fetched == [AREA_ID]


def test_several_areas_redirect_to_one_combined_view(local_links, monkeypatch):
    monkeypatch.setattr(maplinks, "fetch_area", lambda i: {AREA_ID: CIRCLE_AREA, "b1": POLYGON_AREA}[i])
    response = _get(f"{local_links}/map?ids={AREA_ID},b1")
    assert response.status_code == 302
    assert len(_decode(response.headers["location"])["features"]) == 2


@pytest.mark.parametrize("path", ["/map/..%2Fnetworks", "/map/a%20b", "/map?ids=", "/map/" + "a" * 65,
                                  "/map?ids=abc%0A"])
def test_bad_identifiers_are_refused_without_calling_the_api(local_links, monkeypatch, path):
    monkeypatch.setattr(maplinks, "fetch_area", lambda i: pytest.fail("the API must not be called"))
    assert _get(local_links + path).status_code == 400


def test_an_unknown_area_is_a_404(local_links, monkeypatch):
    def not_found(area_id):
        request = httpx.Request("GET", "http://api/areas/x")
        raise httpx.HTTPStatusError("nf", request=request, response=httpx.Response(404, request=request))

    monkeypatch.setattr(maplinks, "fetch_area", not_found)
    assert _get(f"{local_links}/map/{AREA_ID}").status_code == 404


def test_an_unreachable_api_is_a_502(local_links, monkeypatch):
    def down(area_id):
        raise httpx.ConnectError("down")

    monkeypatch.setattr(maplinks, "fetch_area", down)
    response = _get(f"{local_links}/map/{AREA_ID}")
    assert response.status_code == 502 and "ConnectError" in response.text


def test_fetch_area_asks_the_areas_api_for_that_identifier(monkeypatch):
    import http.server
    import threading

    from camara import client as client_module
    from camara.auth import TokenProvider

    seen = []

    class API(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            seen.append(self.path)
            data = json.dumps(CIRCLE_AREA).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    api = http.server.ThreadingHTTPServer(("127.0.0.1", 0), API)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(client_module, "API_ROOT", f"http://127.0.0.1:{api.server_address[1]}/")
        monkeypatch.setattr(maplinks, "_provider", TokenProvider())  # the link server's own provider
        assert maplinks.fetch_area(AREA_ID) == CIRCLE_AREA
    finally:
        api.shutdown()
        api.server_close()
    assert seen == [f"/dedicated-network-areas/v0.1-wip/areas/{AREA_ID}"]


def test_a_taken_port_falls_back_to_embedded_links():
    try:
        with socket.socket() as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen()
            port = busy.getsockname()[1]
            assert maplinks.start(host="127.0.0.1", port=port) is None
        assert maplinks.base_url() is None
        assert geo.area_geojson_url(CIRCLE_AREA).startswith("https://geojson.io/#data=")
    finally:
        maplinks.stop()


def test_two_servers_cannot_share_a_port(local_links):
    port = int(local_links.rsplit(":", 1)[1])
    first = maplinks._server
    try:
        assert maplinks.start(host="127.0.0.1", port=port) is None
    finally:
        maplinks._server = first  # keep the fixture's server for its own stop()


@pytest.mark.parametrize("host", ["0.0.0.0", "", "192.168.1.10", "example.com"])
def test_only_loopback_hosts_are_accepted(host):
    try:
        assert maplinks.start(host=host, port=0) is None
        assert maplinks.base_url() is None
    finally:
        maplinks.stop()


@pytest.mark.parametrize("port", [-1, 70000])
def test_a_port_out_of_range_falls_back(port):
    try:
        assert maplinks.start(host="127.0.0.1", port=port) is None
    finally:
        maplinks.stop()


def test_requests_for_another_host_name_are_refused(local_links, monkeypatch):
    monkeypatch.setattr(maplinks, "fetch_area", lambda i: pytest.fail("the API must not be called"))
    response = httpx.get(f"{local_links}/map/{AREA_ID}", headers={"Host": "attacker.example:80"},
                         follow_redirects=False, timeout=10)
    assert response.status_code == 403


def test_a_combined_link_never_drops_areas(local_links):
    odd = {**POLYGON_AREA, "id": "zone_2"}  # an id the short link cannot carry
    assert geo.combined_geojson_url([CIRCLE_AREA, odd]).startswith("https://geojson.io/#data=")


def test_an_area_with_another_id_is_refused(local_links, monkeypatch):
    monkeypatch.setattr(maplinks, "fetch_area", lambda i: {**CIRCLE_AREA, "id": "other"})
    assert _get(f"{local_links}/map/{AREA_ID}").status_code == 502


def test_an_unexpected_api_answer_is_a_502(local_links, monkeypatch):
    monkeypatch.setattr(maplinks, "fetch_area", lambda i: [CIRCLE_AREA])
    assert _get(f"{local_links}/map/{AREA_ID}").status_code == 502
