"""
tests/test_config.py
────────────────────
CAMARA_API_ROOT is the address of the server, written with or without a trailing slash; the URLs built from it
must be the same either way.
"""

import importlib

import pytest

import camara.config as config


@pytest.fixture(autouse=True)
def restore_config(monkeypatch):
    yield
    monkeypatch.delenv("CAMARA_API_ROOT", raising=False)
    monkeypatch.delenv("CAMARA_ACCESS_TOKEN", raising=False)
    importlib.reload(config)


@pytest.mark.parametrize("root", ["https://api.example.com", "https://api.example.com/", "https://api.example.com//"])
def test_the_api_root_ends_in_exactly_one_slash(monkeypatch, root):
    monkeypatch.setenv("CAMARA_API_ROOT", root)
    importlib.reload(config)
    assert config.API_ROOT == "https://api.example.com/"
    url = f"{config.API_ROOT}{config.API_PATHS['profiles']}/profiles"
    assert url == "https://api.example.com/dedicated-network-profiles/v0.2-wip/profiles"


def test_the_default_root_is_the_local_server(monkeypatch):
    monkeypatch.delenv("CAMARA_API_ROOT", raising=False)
    importlib.reload(config)
    assert config.API_ROOT == "http://localhost:9091/"


def test_the_start_up_line_names_the_root_and_whether_a_token_is_set_but_never_the_token(monkeypatch):
    monkeypatch.setenv("CAMARA_API_ROOT", "https://api.example.com")
    monkeypatch.delenv("CAMARA_ACCESS_TOKEN", raising=False)
    importlib.reload(config)
    assert config.startup_line() == "[camara-mcp] Starting | API root: https://api.example.com/ | Auth: NO TOKEN"
    monkeypatch.setenv("CAMARA_ACCESS_TOKEN", "secret-value")
    importlib.reload(config)
    assert "secret-value" not in config.startup_line()
    assert config.startup_line().endswith("Auth: token set")
