"""
tests/test_auth.py
──────────────────
The server authenticates with a fixed token (CAMARA_ACCESS_TOKEN) or obtains and renews one with OAuth 2.0 client
credentials. The token endpoint and the API are simulated with httpx.MockTransport; no network is used.
"""

import asyncio
import base64
import importlib
from urllib.parse import parse_qs

import httpx
import pytest

import camara.client as client_module
import camara.config as config
from camara.auth import TokenError, TokenProvider
from camara.client import api_request, handle_error

TOKEN_URL = "https://auth.example.com/tokens"
SECRET = "s3cr3t-value"


class TokenEndpoint:
    """Simulated OAuth token endpoint that issues token-1, token-2, ... and records the requests."""

    def __init__(self, status=200, body=None, expires_in=3600):
        self.requests = []
        self.status = status
        self.body = body
        self.expires_in = expires_in

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.body is not None or self.status != 200:
            return httpx.Response(self.status, json=self.body)
        return httpx.Response(
            200,
            json={"access_token": f"token-{len(self.requests)}", "token_type": "bearer",
                  "expires_in": self.expires_in},
        )


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def provider(endpoint=None, clock=None, **kwargs) -> TokenProvider:
    settings = dict(token_url=TOKEN_URL, client_id="my-client", client_secret=SECRET)
    settings.update(kwargs)
    return TokenProvider(
        transport=httpx.MockTransport(endpoint) if endpoint else None,
        clock=clock or Clock(),
        **settings,
    )


def form_of(request: httpx.Request) -> dict:
    return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}


# ── TokenProvider ──────────────────────────────────────────────────────────────

def test_a_fixed_token_is_used_as_given_and_takes_precedence():
    endpoint = TokenEndpoint()
    p = provider(endpoint, static_token="fixed-token")
    assert p.mode == "static" and not p.renewable
    assert asyncio.run(p.get_token()) == "fixed-token"
    assert endpoint.requests == []


def test_without_credentials_no_token_is_sent():
    p = TokenProvider()
    assert p.mode == "none"
    assert asyncio.run(p.get_token()) is None


def test_incomplete_client_credentials_are_not_used():
    endpoint = TokenEndpoint()
    p = provider(endpoint, client_secret="")
    assert p.mode == "none"
    assert asyncio.run(p.get_token()) is None
    assert endpoint.requests == []


def test_client_credentials_with_basic_authentication():
    endpoint = TokenEndpoint()
    p = provider(endpoint, scope="dedicated-network:read dedicated-network:write")
    assert asyncio.run(p.get_token()) == "token-1"
    request = endpoint.requests[0]
    assert request.method == "POST" and str(request.url) == TOKEN_URL
    assert form_of(request) == {
        "grant_type": "client_credentials",
        "scope": "dedicated-network:read dedicated-network:write",
    }
    expected = base64.b64encode(f"my-client:{SECRET}".encode()).decode()
    assert request.headers["Authorization"] == f"Basic {expected}"


def test_client_credentials_sent_in_the_body():
    endpoint = TokenEndpoint()
    p = provider(endpoint, auth_mode="body")
    asyncio.run(p.get_token())
    request = endpoint.requests[0]
    assert form_of(request) == {
        "grant_type": "client_credentials",
        "client_id": "my-client",
        "client_secret": SECRET,
    }
    assert "Authorization" not in request.headers


def test_the_token_is_reused_until_shortly_before_it_expires():
    endpoint = TokenEndpoint(expires_in=3600)
    clock = Clock()
    p = provider(endpoint, clock=clock)
    assert asyncio.run(p.get_token()) == "token-1"
    clock.now += 3500  # 100 s left: still more than the 60 s margin
    assert asyncio.run(p.get_token()) == "token-1"
    clock.now += 60    # 40 s left: renew
    assert asyncio.run(p.get_token()) == "token-2"
    assert len(endpoint.requests) == 2


def test_a_short_lived_token_is_renewed_at_half_its_lifetime():
    endpoint = TokenEndpoint(expires_in=40)
    clock = Clock()
    p = provider(endpoint, clock=clock)
    asyncio.run(p.get_token())
    clock.now += 19
    assert asyncio.run(p.get_token()) == "token-1"
    clock.now += 2
    assert asyncio.run(p.get_token()) == "token-2"


def test_concurrent_requests_share_one_token_request():
    endpoint = TokenEndpoint()
    p = provider(endpoint)

    async def many():
        return await asyncio.gather(*(p.get_token() for _ in range(5)))

    assert asyncio.run(many()) == ["token-1"] * 5
    assert len(endpoint.requests) == 1


def test_a_rejected_token_request_is_reported_without_the_secret():
    endpoint = TokenEndpoint(status=401, body={"error": "invalid_client", "error_description": "Bad credentials"})
    p = provider(endpoint)
    with pytest.raises(TokenError) as info:
        asyncio.run(p.get_token())
    text = handle_error(info.value)
    assert "HTTP 401" in text and "invalid_client: Bad credentials" in text
    assert "CAMARA_CLIENT_ID" in text
    assert SECRET not in text


def test_a_token_response_without_access_token_is_an_error():
    endpoint = TokenEndpoint(body={"token_type": "bearer"})
    with pytest.raises(TokenError, match="no access_token"):
        asyncio.run(provider(endpoint).get_token())


def test_an_unreachable_token_endpoint_is_an_error():
    def refuse(request):
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(TokenError, match="cannot reach the token endpoint"):
        asyncio.run(provider(refuse).get_token())


# ── api_request with the provider ──────────────────────────────────────────────

@pytest.fixture
def api(monkeypatch):
    """Route api_request to a simulated API and return the list of requests it received."""
    received = []
    real_client = httpx.AsyncClient

    def install(handler, token_provider):
        def recording_handler(request):
            received.append(request)
            return handler(request)

        transport = httpx.MockTransport(recording_handler)

        def make_client(*args, **kwargs):
            # The token provider passes its own transport; only API clients get the simulated API.
            if kwargs.get("transport") is None:
                kwargs["transport"] = transport
            return real_client(*args, **kwargs)

        monkeypatch.setattr(client_module, "_token_provider", token_provider)
        monkeypatch.setattr(client_module.httpx, "AsyncClient", make_client)
        return received

    return install


def test_api_requests_carry_the_client_credentials_token(api):
    endpoint = TokenEndpoint()
    received = api(lambda r: httpx.Response(200, json=[]), provider(endpoint))
    asyncio.run(api_request("profiles", "/profiles"))
    asyncio.run(api_request("profiles", "/profiles"))
    assert [r.headers["Authorization"] for r in received] == ["Bearer token-1", "Bearer token-1"]
    assert len(endpoint.requests) == 1


def test_a_401_from_the_api_renews_the_token_and_retries_once(api):
    endpoint = TokenEndpoint()

    def handler(request):
        if request.headers["Authorization"] == "Bearer token-1":
            return httpx.Response(401, json={"code": "UNAUTHENTICATED", "message": "Token expired."})
        return httpx.Response(200, json=[{"id": "p1"}])

    received = api(handler, provider(endpoint))
    assert asyncio.run(api_request("profiles", "/profiles")) == [{"id": "p1"}]
    assert [r.headers["Authorization"] for r in received] == ["Bearer token-1", "Bearer token-2"]


def test_a_persistent_401_is_reported_after_one_retry(api):
    endpoint = TokenEndpoint()
    received = api(lambda r: httpx.Response(401, json={"message": "Unauthorized."}), provider(endpoint))
    with pytest.raises(httpx.HTTPStatusError) as info:
        asyncio.run(api_request("profiles", "/profiles"))
    assert len(received) == 2
    assert handle_error(info.value).startswith("Error 401 Unauthorized — Unauthorized. Check the credentials")


def test_a_fixed_token_is_not_retried_on_401(api):
    received = api(lambda r: httpx.Response(401, json={}), TokenProvider(static_token="fixed-token"))
    with pytest.raises(httpx.HTTPStatusError):
        asyncio.run(api_request("profiles", "/profiles"))
    assert len(received) == 1


# ── configuration and start-up line ────────────────────────────────────────────

AUTH_VARIABLES = ("CAMARA_ACCESS_TOKEN", "CAMARA_TOKEN_URL", "CAMARA_CLIENT_ID", "CAMARA_CLIENT_SECRET",
                  "CAMARA_SCOPE", "CAMARA_TOKEN_AUTH")


@pytest.fixture
def clean_auth_env(monkeypatch):
    for name in AUTH_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    yield monkeypatch
    for name in AUTH_VARIABLES:
        monkeypatch.delenv(name, raising=False)
    importlib.reload(config)


def test_the_start_up_line_names_client_credentials_but_no_secret(clean_auth_env):
    clean_auth_env.setenv("CAMARA_TOKEN_URL", TOKEN_URL)
    clean_auth_env.setenv("CAMARA_CLIENT_ID", "my-client")
    clean_auth_env.setenv("CAMARA_CLIENT_SECRET", SECRET)
    importlib.reload(config)
    line = config.startup_line()
    assert line.endswith("Auth: client credentials")
    assert SECRET not in line
    assert TokenProvider.from_config().mode == "client_credentials"


def test_the_start_up_line_says_which_client_credential_is_missing(clean_auth_env):
    clean_auth_env.setenv("CAMARA_TOKEN_URL", TOKEN_URL)
    clean_auth_env.setenv("CAMARA_CLIENT_ID", "my-client")
    importlib.reload(config)
    assert config.startup_line().endswith(
        "Auth: NO TOKEN (client credentials incomplete: CAMARA_CLIENT_SECRET not set)"
    )
