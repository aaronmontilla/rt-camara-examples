"""
tests/test_flat_arguments.py
────────────────────────────
Every tool publishes its input model's fields as top-level arguments
(camara/flat.py), not wrapped in a single `params` object, and still rejects
arguments it does not declare.
"""

import asyncio

import pytest
from mcp.server.mcpserver.exceptions import ToolError

import server
from camara.flat import FLAT_ATTRIBUTE
from camara.tools import networks

SERVICE_TIME = {"start": "2026-11-05T10:00:00Z", "end": "2026-11-05T12:00:00Z"}


def _tools():
    return server.mcp._tool_manager.list_tools()


def _call(name, arguments):
    return asyncio.run(server.mcp.call_tool(name, arguments))


@pytest.fixture
def captured_requests(monkeypatch):
    calls = []

    async def fake_api_request(api, path, method="GET", body=None, params=None):
        calls.append({"api": api, "path": path, "method": method, "body": body})
        return {"id": "n1", "status": "REQUESTED"} if method == "POST" else {"id": "n1"}

    monkeypatch.setattr(networks, "api_request", fake_api_request)
    return calls


@pytest.mark.parametrize("tool", _tools(), ids=lambda t: t.name)
def test_schema_lists_the_input_model_fields_at_the_top_level(tool):
    model = getattr(tool.fn, FLAT_ATTRIBUTE)
    assert set(tool.parameters["properties"]) == set(model.model_fields)
    assert "params" not in tool.parameters["properties"]
    assert tool.parameters["additionalProperties"] is False
    required = {name for name, field in model.model_fields.items() if field.is_required()}
    assert set(tool.parameters.get("required", [])) == required


@pytest.mark.parametrize("tool", _tools(), ids=lambda t: t.name)
def test_descriptions_do_not_mention_a_params_wrapper(tool):
    assert "params." not in (tool.description or "")


def test_flat_arguments_reach_the_api(captured_requests):
    _call(
        "camara_create_network",
        {"serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "networkProfileId": "p1"},
    )
    assert captured_requests == [{
        "api": "networks",
        "path": "/networks",
        "method": "POST",
        "body": {"serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "networkProfileId": "p1"},
    }]


def test_defaults_apply_when_optional_arguments_are_omitted(captured_requests):
    result = _call("camara_get_network", {"networkId": "n1"})
    assert not result.is_error
    assert "# Dedicated Network" in result.content[0].text  # response_format defaults to markdown


def test_an_unknown_argument_is_rejected(captured_requests):
    with pytest.raises(ToolError, match="profileId"):
        _call("camara_create_network", {"serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "profileId": "p1"})
    assert captured_requests == []


def test_the_old_params_wrapper_is_rejected(captured_requests):
    with pytest.raises(ToolError, match="params"):
        _call("camara_get_network", {"params": {"networkId": "n1"}})
    assert captured_requests == []


def test_the_input_model_checks_still_run(captured_requests):
    with pytest.raises(ToolError, match="exactly one of 'networkProfileId' or 'qosProfileName'"):
        _call(
            "camara_create_network",
            {"serviceAreaId": "a1", "serviceTime": SERVICE_TIME, "networkProfileId": "p1", "qosProfileName": "Q"},
        )
    assert captured_requests == []
