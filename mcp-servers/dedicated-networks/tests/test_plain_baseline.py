"""
tests/test_plain_baseline.py
────────────────────────────
Evaluation baselines (camara/plain.py): CAMARA_CONTRACT=plain approximates a
wrapper generated from the OpenAPI operations; CAMARA_ERRORS=raw returns API
errors as they came. The default (full) contract is unchanged.
"""

import asyncio
import json
import os
import subprocess
import sys

import pytest
from mcp.server.mcpserver import MCPServer
from mcp.types import LATEST_PROTOCOL_VERSION

import server
from camara import client as client_module
from camara import config, plain
from camara.auth import TokenProvider
from camara.tools.accesses import register_access_tools
from camara.tools.areas import register_area_tools
from camara.tools.networks import register_network_tools
from camara.tools.profiles import register_profile_tools
from camara.flat import forbid_unknown_arguments
from tests.test_telemetry import LocalAPI
from tests.test_tool_errors import SERVER_DIR, StdioServer

SERVICE_TIME = {"start": "2026-11-05T10:00:00Z", "end": "2026-11-05T12:00:00Z"}
NETWORK = {"id": "n1", "status": "REQUESTED", "serviceAreaId": "a1", "networkProfileId": "p1"}


@pytest.fixture
def local_api(monkeypatch):
    api = LocalAPI()
    monkeypatch.setattr(client_module, "API_ROOT", api.url)
    monkeypatch.setattr(client_module, "_token_provider", TokenProvider())
    yield api
    api.close()


def _call(name, args):
    return asyncio.run(server.mcp.call_tool(name, args))


def _fresh_plain_tools():
    """The twelve tools registered on a new server and rewritten to the plain contract."""
    mcp = MCPServer("test")
    for register in (register_network_tools, register_profile_tools, register_access_tools, register_area_tools):
        register(mcp)
    tools = mcp._tool_manager.list_tools()
    forbid_unknown_arguments(tools)
    plain.apply(tools)
    return tools


def _texts(schema):
    """Every description and title in a schema."""
    out = []
    if isinstance(schema, dict):
        for k, v in schema.items():
            if k in ("description", "title") and isinstance(v, str):
                out.append(v)
            else:
                out.extend(_texts(v))
    elif isinstance(schema, list):
        for v in schema:
            out.extend(_texts(v))
    return out


def _spec_texts():
    texts = set(plain.PLAIN_SUMMARIES.values())
    for props in list(plain.SPEC_PROPERTIES.values()) + list(plain.SPEC_REPLACED.values()):
        for keywords in props.values():
            texts |= set(_texts(keywords))
    return texts


def test_plain_tools_carry_only_the_specification_texts():
    tools = _fresh_plain_tools()
    assert len(tools) == 12
    allowed = _spec_texts()
    for tool in tools:
        assert tool.description == plain.PLAIN_SUMMARIES[tool.name]
        assert set(_texts(tool.parameters)) <= allowed, tool.name   # no gateway text, no pydantic titles
        text = json.dumps(tool.parameters)
        assert "response_format" not in text and "ResponseFormat" not in text
        assert "camara_" not in text                                  # no cross-tool guidance
        assert tool.parameters["additionalProperties"] is False
        assert tool.annotations is None or tool.annotations.title is None


def test_plain_has_the_specification_constraints():
    tools = {t.name: t.parameters for t in _fresh_plain_tools()}
    net = tools["camara_create_network"]
    assert net["properties"]["serviceAreaId"]["format"] == "uuid"
    assert net["properties"]["serviceAreaId"]["maxLength"] == 36
    service_time = net["$defs"]["ServiceTimeInput"]["properties"]
    assert service_time["start"]["format"] == "date-time" and service_time["end"]["maxLength"] == 64
    qos = net["properties"]["qosProfileName"]["anyOf"][0]
    assert (qos["minLength"], qos["maxLength"], qos["pattern"]) == (3, 256, "^[a-zA-Z0-9_.-]+$")
    assert net["properties"]["qosProfileName"]["description"].endswith("by means of the QoS Profile API.")
    sink = net["properties"]["sink"]["anyOf"][0]
    assert sink["maxLength"] == 2048 and "https" in sink["pattern"]
    assert net["$defs"]["SinkCredentialInput"]["properties"]["credentialType"]["enum"] == ["ACCESSTOKEN", "PRIVATE_KEY_JWT"]
    access = tools["camara_create_access"]
    device = access["$defs"]["DeviceInput"]
    assert device["minProperties"] == 1 and device["required"] == ["phoneNumber"]
    assert "only option" in access["properties"]["device"]["description"]
    assert device["properties"]["phoneNumber"]["anyOf"][0]["maxLength"] == 16
    assert device["properties"]["networkAccessIdentifier"]["description"].startswith("A public identifier")
    ipv4 = access["$defs"]["DeviceIpv4Input"]
    assert len(ipv4["anyOf"]) == 2 and ipv4["properties"]["publicPort"]["anyOf"][0]["minimum"] == 1
    profiles = access["properties"]["qosProfiles"]["anyOf"][0]
    assert profiles["maxItems"] == 32 and profiles["items"]["maxLength"] == 256
    assert tools["camara_get_access"]["properties"]["accessId"]["format"] == "uuid"
    area = tools["camara_retrieve_service_areas"]["properties"]["overlappingArea"]
    circle, polygon = area["anyOf"]
    assert circle["properties"]["radius"]["minimum"] == 1
    assert (polygon["properties"]["boundary"]["minItems"], polygon["properties"]["boundary"]["maxItems"]) == (3, 15)
    assert circle["properties"]["areaType"]["enum"] == ["CIRCLE"]
    assert polygon["properties"]["areaType"]["enum"] == ["POLYGON"]


def test_plain_schemas_are_accepted_by_the_claude_api():
    """The Claude API rejects oneOf/allOf/anyOf at the top level of a tool's input schema."""
    for tool in _fresh_plain_tools():
        assert tool.parameters["type"] == "object"
        assert not {"oneOf", "allOf", "anyOf"} & set(tool.parameters), tool.name


def test_a_specification_path_missing_from_the_schema_is_an_error(monkeypatch):
    monkeypatch.setitem(plain.SPEC_PROPERTIES, "camara_get_area", {"areaIdentifier": {"description": "x"}})
    with pytest.raises(KeyError):
        _fresh_plain_tools()


def test_plain_returns_responses_the_formatter_would_not_handle(local_api, monkeypatch):
    """The response goes back before the tool formats it, so an unexpected shape cannot break the call."""
    monkeypatch.setattr(config, "CONTRACT", "plain")
    odd = {"unexpected": ["shape", "ñ"]}
    local_api.responses = [(200, odd)]
    result = _call("camara_get_network", {"networkId": "n1"})
    assert not result.is_error
    assert json.loads(result.content[0].text) == odd and "ñ" in result.content[0].text


def test_the_plain_contract_implies_raw_errors_unless_told_otherwise():
    code = "from camara import config; print(config.CONTRACT, config.ERRORS)"
    def run(**env):
        e = {k: v for k, v in os.environ.items() if not k.startswith("CAMARA_")} | env
        return subprocess.run([sys.executable, "-c", code], cwd=SERVER_DIR, env=e,
                              capture_output=True, text=True, check=True).stdout.split()
    assert run(CAMARA_CONTRACT="plain") == ["plain", "raw"]
    assert run(CAMARA_CONTRACT="plain", CAMARA_ERRORS="translated") == ["plain", "translated"]
    assert run() == ["full", "translated"]


def test_plain_cross_field_check_gives_a_neutral_message(monkeypatch):
    from mcp.server.mcpserver.exceptions import ToolError
    monkeypatch.setattr(config, "CONTRACT", "plain")
    with pytest.raises(ToolError) as info:
        _call("camara_create_network", {"serviceAreaId": "a1", "serviceTime": SERVICE_TIME,
                                        "networkProfileId": "p1", "qosProfileName": "Q"})
    assert plain.ONEOF_MESSAGE in str(info.value)
    assert "Provide exactly one" not in str(info.value)


def test_plain_resent_delete_returns_the_api_outcome(local_api, monkeypatch):
    monkeypatch.setattr(config, "CONTRACT", "plain")
    local_api.drop = {2}
    local_api.responses = [(200, []), (404, {"code": "NOT_FOUND"})]
    _, deleted = asyncio.run(_two_calls(("camara_list_profiles", {}), ("camara_delete_network", {"networkId": "n1"})))
    assert deleted.content[0].text == "HTTP 204 No Content"


async def _two_calls(a, b):
    return [await server.mcp.call_tool(*a), await server.mcp.call_tool(*b)]


def test_full_contract_keeps_descriptions_and_prompts():
    tools = {t.name: t for t in server.mcp._tool_manager.list_tools()}
    assert "camara_retrieve_service_areas" in tools["camara_create_network"].parameters["properties"]["serviceAreaId"]["description"]
    assert "response_format" in tools["camara_get_network"].parameters["properties"]
    assert len(server.mcp._prompt_manager.list_prompts()) == 4


def test_plain_returns_the_api_response_as_it_came(local_api, monkeypatch):
    monkeypatch.setattr(config, "CONTRACT", "plain")
    local_api.responses = [(201, NETWORK), (204, None)]
    created = _call("camara_create_network",
                    {"serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "networkProfileId": "p1"})
    deleted = _call("camara_delete_network", {"networkId": "n1"})

    assert json.loads(created.content[0].text) == NETWORK  # no Markdown, no next step
    assert deleted.content[0].text == "HTTP 204 No Content"


def test_plain_area_results_carry_no_map_links(local_api, monkeypatch):
    monkeypatch.setattr(config, "CONTRACT", "plain")
    area = {"id": "a1", "name": "A", "area": {"areaType": "CIRCLE",
                                              "center": {"latitude": 48.8, "longitude": 2.2}, "radius": 500}}
    local_api.responses = [(200, [area])]
    result = _call("camara_retrieve_service_areas", {})
    assert json.loads(result.content[0].text) == [area]
    assert "geojson" not in result.content[0].text


def test_raw_errors_return_the_api_error_as_it_came(local_api, monkeypatch):
    monkeypatch.setattr(config, "ERRORS", "raw")
    body = {"status": 404, "code": "NOT_FOUND", "message": "The specified resource is not found."}
    local_api.responses = [(404, body)]
    result = _call("camara_get_network", {"networkId": "n1"})

    assert result.is_error
    text = result.content[0].text
    assert text.startswith("Error executing tool camara_get_network: HTTP 404 Not Found: ")
    assert json.loads(text.split("Not Found: ", 1)[1]) == body
    assert "Verify the ID" not in text  # no remedy added


def test_the_full_contract_is_unchanged_by_default(local_api, monkeypatch):
    monkeypatch.setattr(config, "CONTRACT", "full")
    monkeypatch.setattr(config, "ERRORS", "translated")
    local_api.responses = [(201, NETWORK)]
    created = _call("camara_create_network",
                    {"serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "networkProfileId": "p1"})
    assert created.content[0].text.startswith("# Dedicated Network Created")


def test_over_stdio_the_plain_server_has_no_prompts_and_one_line_instructions():
    env = {k: v for k, v in os.environ.items() if not k.startswith("CAMARA_")}
    env["CAMARA_CONTRACT"] = "plain"
    srv = StdioServer(env)
    try:
        srv.send({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
            "protocolVersion": LATEST_PROTOCOL_VERSION, "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"}}})
        init = srv.response(1)["result"]
        srv.send({"jsonrpc": "2.0", "method": "notifications/initialized"})
        srv.send({"jsonrpc": "2.0", "id": 2, "method": "prompts/list", "params": {}})
        prompts = srv.response(2)
        srv.send({"jsonrpc": "2.0", "id": 3, "method": "tools/list", "params": {}})
        tools = srv.response(3)["result"]["tools"]
    finally:
        srv.close()
    assert init.get("instructions") == plain.PLAIN_INSTRUCTIONS
    assert prompts.get("result", {}).get("prompts", []) == []
    assert {t["name"]: t["description"] for t in tools} == {
        name: plain.PLAIN_SUMMARIES[name] for name in (t["name"] for t in tools)}
