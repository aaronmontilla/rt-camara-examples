"""
tests/test_tool_errors.py
─────────────────────────
A failed API call is reported to the MCP client as a tool error (isError set), with the readable message from
handle_error() as its text. Before, the message came back as an ordinary result, so clients that measure success
counted the failure as a successful call.
"""

import asyncio
import json
import os
import pathlib
import subprocess
import sys
import threading

import httpx
import pytest
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import LATEST_PROTOCOL_VERSION

import server
from camara.tools import accesses, areas, networks, profiles

SERVER_DIR = pathlib.Path(__file__).resolve().parent.parent
TOOL_MODULES = (accesses, areas, networks, profiles)
SERVICE_TIME = {"start": "2026-11-05T10:00:00Z", "end": "2026-11-05T12:00:00Z"}

# Minimal valid arguments for every registered tool.
TOOL_ARGUMENTS = {
    "camara_list_profiles": {},
    "camara_get_profile": {"profileId": "p1"},
    "camara_retrieve_service_areas": {},
    "camara_get_area": {"areaId": "a1"},
    "camara_list_networks": {},
    "camara_get_network": {"networkId": "n1"},
    "camara_create_network": {"serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "networkProfileId": "p1"},
    "camara_delete_network": {"networkId": "n1"},
    "camara_list_accesses": {},
    "camara_get_access": {"accessId": "x1"},
    "camara_create_access": {"networkId": "n1", "device": {"phoneNumber": "+34600123456"}},
    "camara_delete_access": {"accessId": "x1"},
}


def _not_found() -> httpx.HTTPStatusError:
    request = httpx.Request("GET", "https://api.example.com/x")
    response = httpx.Response(
        404, json={"code": "NOT_FOUND", "message": "The specified resource is not found."}, request=request
    )
    return httpx.HTTPStatusError("not found", request=request, response=response)


@pytest.fixture
def failing_api(monkeypatch):
    async def fake_api_request(*args, **kwargs):
        raise _not_found()

    for module in TOOL_MODULES:
        monkeypatch.setattr(module, "api_request", fake_api_request)


def test_every_registered_tool_has_arguments_in_this_test():
    registered = {t.name for t in server.mcp._tool_manager.list_tools()}
    assert registered == set(TOOL_ARGUMENTS)


@pytest.mark.parametrize("tool_name", sorted(TOOL_ARGUMENTS))
def test_api_errors_are_raised_as_tool_errors_with_the_readable_message(failing_api, tool_name):
    with pytest.raises(ToolError) as info:
        asyncio.run(server.mcp.call_tool(tool_name, {"params": TOOL_ARGUMENTS[tool_name]}))
    assert "Error 404 Not Found — The specified resource is not found. Verify the ID is correct." in str(info.value)


def test_a_successful_call_is_not_an_error(monkeypatch):
    async def fake_api_request(*args, **kwargs):
        return []

    monkeypatch.setattr(networks, "api_request", fake_api_request)
    result = asyncio.run(server.mcp.call_tool("camara_list_networks", {"params": {}}))
    assert not result.is_error


# ── over the MCP protocol (stdio), as a real client sees it ───────────────────

class StdioServer:
    """server.py as a subprocess, spoken to in JSON-RPC over stdin/stdout."""

    def __init__(self, env: dict):
        self.process = subprocess.Popen(
            [sys.executable, "server.py"], cwd=SERVER_DIR, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
        )
        self._timer = threading.Timer(30, self.process.kill)  # never hang the test run
        self._timer.start()

    def send(self, message: dict) -> None:
        self.process.stdin.write(json.dumps(message) + "\n")
        self.process.stdin.flush()

    def response(self, request_id: int) -> dict:
        for line in self.process.stdout:
            message = json.loads(line)
            if message.get("id") == request_id:
                return message
        raise AssertionError(f"no response to request {request_id}")

    def close(self) -> None:
        self._timer.cancel()
        self.process.kill()
        self.process.wait()


def test_over_stdio_a_failed_call_comes_back_with_is_error_set():
    env = {k: v for k, v in os.environ.items() if not k.startswith("CAMARA_")}
    env["CAMARA_API_ROOT"] = "http://127.0.0.1:9"  # nothing listens there: connection refused
    srv = StdioServer(env)
    try:
        srv.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"}}})
        assert "result" in srv.response(1)
        srv.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        srv.send({"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {
            "name": "camara_get_network", "arguments": {"params": {"networkId": "n1"}}}})
        result = srv.response(2)["result"]
    finally:
        srv.close()
    assert result["isError"] is True
    assert "Cannot connect to http://127.0.0.1:9/" in result["content"][0]["text"]
