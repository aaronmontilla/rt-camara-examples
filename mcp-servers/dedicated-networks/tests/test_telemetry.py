"""
tests/test_telemetry.py
───────────────────────
Every tool result carries, in _meta, what the call spent on the CAMARA APIs
(camara/telemetry.py), and API requests reuse one connection between tool
calls (camara/client.py). The API is a local HTTP server; no external network
is used.
"""

import asyncio
import gzip as gzip_module
import http.server
import json
import threading

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError

import server
from camara import client as client_module
from camara.auth import TokenProvider

SERVICE_TIME = {"start": "2026-11-05T10:00:00Z", "end": "2026-11-05T12:00:00Z"}


class LocalAPI:
    """A keep-alive HTTP/1.1 server that answers every request with the next queued response.

    Requests whose number (1-based) is in `drop` are read and then the connection is closed
    without an answer, as a server does when it drops an idle connection just as it is reused.
    With gzip=True bodies are sent compressed.
    """

    def __init__(self, close_after_each=False, gzip=False):
        self.responses = []
        self.connections = 0
        self.requests = []
        self.drop = set()
        api = self

        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def setup(self):
                super().setup()
                api.connections += 1

            def _answer(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                api.requests.append((self.command, self.path, body))
                if len(api.requests) in api.drop:
                    self.close_connection = True
                    return
                status, payload = api.responses.pop(0) if api.responses else (200, [])
                data = b"" if status == 204 else json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                if gzip and data:
                    data = gzip_module.compress(data)
                    self.send_header("Content-Encoding", "gzip")
                self.send_header("Content-Length", str(len(data)))
                if close_after_each:
                    self.send_header("Connection", "close")
                    self.close_connection = True
                self.end_headers()
                self.wfile.write(data)

            do_GET = do_POST = do_DELETE = _answer

            def log_message(self, *args):
                pass

        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_address[1]}/"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def local_api(monkeypatch):
    api = LocalAPI()
    monkeypatch.setattr(client_module, "API_ROOT", api.url)
    monkeypatch.setattr(client_module, "_token_provider", TokenProvider())  # no authentication
    yield api
    api.close()


def _calls(*calls):
    """Run several tool calls in one event loop, as one server process does."""
    async def run():
        return [await server.mcp.call_tool(name, args) for name, args in calls]
    return asyncio.run(run())


def test_a_successful_call_reports_its_api_request(local_api):
    local_api.responses = [(200, [{"id": "p1", "name": "profile1"}])]
    (result,) = _calls(("camara_list_profiles", {"response_format": "json"}))

    assert not result.is_error
    meta = result.meta
    (call,) = meta["backend_calls"]
    assert call["method"] == "GET"
    assert call["url"].startswith(local_api.url) and call["url"].endswith("/profiles")
    assert call["http_status"] == 200
    assert call["response_bytes"] == len(json.dumps([{"id": "p1", "name": "profile1"}]))
    assert call["request_bytes"] > 0 and call["response_headers_bytes"] > 0
    assert call["attempt"] == 1
    assert meta["backend_total_latency_sec"] == call["latency_sec"]
    assert meta["backend_retries"] == 0 and meta["backend_rate_limited"] is False
    assert meta["gateway_latency_sec"] >= meta["backend_total_latency_sec"]
    assert "token_call" not in meta


def test_the_text_and_structured_content_are_unchanged(local_api):
    local_api.responses = [(200, [])]
    (result,) = _calls(("camara_list_networks", {}))
    assert result.content[0].text == "No dedicated networks found."
    assert result.structured_content == {"result": "No dedicated networks found."}


def test_tool_calls_reuse_one_connection(local_api):
    local_api.responses = [(200, []), (200, []), (200, [])]
    results = _calls(("camara_list_profiles", {}), ("camara_list_networks", {}), ("camara_list_profiles", {}))

    assert [r.meta["backend_new_connections"] for r in results] == [1, 0, 0]
    assert results[0].meta["backend_connect_sec"] > 0
    assert results[1].meta["backend_connect_sec"] == 0
    assert local_api.connections == 1


def test_a_server_that_closes_connections_still_works(monkeypatch):
    api = LocalAPI(close_after_each=True)
    monkeypatch.setattr(client_module, "API_ROOT", api.url)
    monkeypatch.setattr(client_module, "_token_provider", TokenProvider())
    try:
        api.responses = [(200, []), (200, [])]
        results = _calls(("camara_list_profiles", {}), ("camara_list_profiles", {}))
    finally:
        api.close()
    assert not any(r.is_error for r in results)
    assert [r.meta["backend_new_connections"] for r in results] == [1, 1]


def test_a_failed_call_is_an_error_with_the_same_text_and_telemetry(local_api):
    local_api.responses = [(404, {"code": "NOT_FOUND", "message": "The specified resource is not found."})]
    (result,) = _calls(("camara_get_network", {"networkId": "n1"}))

    assert result.is_error
    assert result.content[0].text == (
        "Error executing tool camara_get_network: "
        "Error 404 Not Found — The specified resource is not found. Verify the ID is correct."
    )
    assert result.meta["backend_calls"][0]["http_status"] == 404


def test_a_post_is_reported_with_its_body_size(local_api):
    local_api.responses = [(201, {"id": "n1", "status": "REQUESTED"})]
    (result,) = _calls(("camara_create_network", {
        "serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "networkProfileId": "p1"}))

    (call,) = result.meta["backend_calls"]
    sent_body = local_api.requests[0][2]
    assert call["method"] == "POST" and call["http_status"] == 201
    assert call["request_bytes"] > len(sent_body) > 0


def test_a_token_request_is_reported_without_secrets(local_api, monkeypatch):
    def token_endpoint(request):
        return httpx.Response(200, json={"access_token": "the-token-value", "expires_in": 3600})

    monkeypatch.setattr(client_module, "_token_provider", TokenProvider(
        token_url="https://auth.example.com/token", client_id="the-client", client_secret="the-secret",
        transport=httpx.MockTransport(token_endpoint)))
    local_api.responses = [(200, []), (200, [])]
    first, second = _calls(("camara_list_profiles", {}), ("camara_list_profiles", {}))

    assert first.meta["token_call"]["url"] == "https://auth.example.com/token"
    assert first.meta["token_call"]["http_status"] == 200
    assert "token_call" not in second.meta  # the token is reused
    dumped = json.dumps(first.meta)
    for secret in ("the-token-value", "the-secret"):
        assert secret not in dumped


def test_an_unreachable_api_is_reported(monkeypatch):
    monkeypatch.setattr(client_module, "API_ROOT", "http://127.0.0.1:9/")
    monkeypatch.setattr(client_module, "_token_provider", TokenProvider())
    (result,) = _calls(("camara_get_network", {"networkId": "n1"}))

    assert result.is_error
    (call,) = result.meta["backend_calls"]
    assert call["http_status"] is None and call["error"] == "ConnectError"


def test_an_input_check_error_has_the_mcp_prefix_once():
    with pytest.raises(ToolError) as info:
        _calls(("camara_create_network", {
            "serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "networkProfileId": "p1", "qosProfileName": "Q"}))
    assert str(info.value).count("Error executing tool") == 1


# ── a connection dropped by the server as it is reused ────────────────────────

def test_a_get_on_a_dropped_connection_is_sent_again(local_api):
    local_api.drop = {2}  # the second request, on the reused connection, gets no answer
    local_api.responses = [(200, []), (200, [])]
    first, second = _calls(("camara_list_profiles", {}), ("camara_list_networks", {}))

    assert not first.is_error and not second.is_error
    assert second.content[0].text == "No dedicated networks found."
    assert [c["attempt"] for c in second.meta["backend_calls"]] == [1, 2]
    assert second.meta["backend_calls"][0]["error"] == "RemoteProtocolError"
    assert second.meta["backend_retries"] == 1


def test_a_read_only_post_on_a_dropped_connection_is_sent_again(local_api):
    local_api.drop = {2}
    local_api.responses = [(200, []), (200, [])]
    _, areas = _calls(("camara_list_profiles", {}), ("camara_retrieve_service_areas", {}))

    assert not areas.is_error
    assert [c["method"] for c in areas.meta["backend_calls"]] == ["POST", "POST"]


def test_a_post_that_creates_is_not_sent_again(local_api):
    local_api.drop = {2}
    local_api.responses = [(200, [])]
    _, created = _calls(("camara_list_profiles", {}), ("camara_create_network", {
        "serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "networkProfileId": "p1"}))

    assert created.is_error
    assert len(created.meta["backend_calls"]) == 1
    assert [r[0] for r in local_api.requests] == ["GET", "POST"]  # one POST only


def test_a_delete_whose_answer_was_lost_is_not_reported_as_404(local_api):
    local_api.drop = {2}  # the delete reaches the server, the answer is lost
    local_api.responses = [(200, []), (404, {"code": "NOT_FOUND", "message": "Gone."})]
    _, deleted = _calls(("camara_list_profiles", {}), ("camara_delete_network", {"networkId": "n1"}))

    assert not deleted.is_error
    assert "successfully deleted" in deleted.content[0].text


def test_compressed_responses_count_the_bytes_transferred(monkeypatch):
    payload = [{"id": f"p{i}", "name": "profile", "description": "x" * 50} for i in range(40)]
    api = LocalAPI(gzip=True)
    monkeypatch.setattr(client_module, "API_ROOT", api.url)
    monkeypatch.setattr(client_module, "_token_provider", TokenProvider())
    try:
        api.responses = [(200, payload)]
        (result,) = _calls(("camara_list_profiles", {"response_format": "json"}))
    finally:
        api.close()
    (call,) = result.meta["backend_calls"]
    assert call["response_bytes"] == len(gzip_module.compress(json.dumps(payload).encode()))
    assert call["response_bytes"] < len(json.dumps(payload))
