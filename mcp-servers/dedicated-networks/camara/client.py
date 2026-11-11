"""
camara/client.py
────────────────
Shared HTTP client and error handler used by every tool.

Exported:
  api_request(api, path, method, body, params)  →  parsed JSON (dict / list / None)
  handle_error(exception)                        →  human-readable error string
  tool_error(exception)                          →  ToolError for a tool to raise
"""

import asyncio
import time
from typing import Any, Dict, Optional

import httpx
from mcp.server.mcpserver.exceptions import ToolError

from camara import telemetry
from camara.auth import TokenError, TokenProvider
from camara.config import API_ROOT, API_PATHS

# Supplies the bearer token: fixed (CAMARA_ACCESS_TOKEN) or obtained and renewed
# with OAuth client credentials (CAMARA_TOKEN_URL, CAMARA_CLIENT_ID, ...).
_token_provider = TokenProvider.from_config()

# ─── Shared connection ─────────────────────────────────────────────────────────
# One client for every request, so the TCP and TLS connection to the API is
# reused between tool calls instead of being opened (and paid in round trips)
# each time. Idle connections are kept for KEEPALIVE_SECONDS, enough for the
# model to think between two tool calls, and below the 60 s idle timeout common
# in front of web APIs.
KEEPALIVE_SECONDS = 50.0
# Methods that may be sent again when a reused connection turns out to be closed.
_IDEMPOTENT = {"GET", "HEAD", "PUT", "DELETE", "OPTIONS"}

_client: Optional[httpx.AsyncClient] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


def _http_client() -> httpx.AsyncClient:
    """The shared client, created on first use in the running event loop.

    An httpx client's connections belong to the loop that opened them, so a new
    loop (each asyncio.run, as in tests) gets a new client.
    """
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not loop or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, keepalive_expiry=KEEPALIVE_SECONDS),
        )
        _client_loop = loop
    return _client


# ─── HTTP headers ──────────────────────────────────────────────────────────────

async def _build_headers() -> Dict[str, str]:
    """Return request headers for every CAMARA API call.

    Always includes Content-Type and Accept for JSON.
    Adds Authorization: Bearer <token> only when authentication is configured.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    started = time.perf_counter()
    token = await _token_provider.get_token()
    # Time spent getting the token, including waiting for another call's request.
    telemetry.add_token_wait(time.perf_counter() - started)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


# ─── Generic HTTP request ──────────────────────────────────────────────────────

async def api_request(
    api: str,                                    # key in API_PATHS, e.g. "networks"
    path: str,                                   # e.g. "/networks" or "/networks/{id}"
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,       # JSON request body (POST)
    params: Optional[Dict[str, Any]] = None,     # URL query parameters (GET)
    read_only: bool = False,                     # a POST that only queries (retrieve-service-areas)
) -> Any:
    """Send an HTTP request to a CAMARA sub-API and return the parsed JSON body.

    Builds the full URL from API_ROOT + the sub-API path + the endpoint path.
    Strips out any query parameters whose value is None.
    Raises httpx.HTTPStatusError on 4xx / 5xx so handle_error() can format them.
    Raises TokenError when a client-credentials token cannot be obtained.
    Returns None for 204 No Content (used by DELETE operations).

    If the shared connection turns out to be closed (the server dropped it while
    idle), the request is sent again on a new one when repeating it is harmless:
    GET, DELETE, or a POST marked read_only. A POST that creates something is
    never repeated, since the first one may have been executed.
    """
    url = f"{API_ROOT}{API_PATHS[api]}{path}"

    # Drop query params that were not provided (value is None)
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}

    client = _http_client()
    attempt = 0

    async def send() -> httpx.Response:
        nonlocal attempt
        attempt += 1
        request = client.build_request(
            method=method,
            url=url,
            headers=await _build_headers(),
            json=body,
            params=clean_params or None,
        )
        trace = telemetry.ConnectionTrace()
        request.extensions["trace"] = trace
        started = time.perf_counter()
        try:
            response = await client.send(request)
        except httpx.HTTPError as exc:
            telemetry.record_call(None, request, time.perf_counter() - started, attempt, trace,
                                  error=type(exc).__name__)
            raise
        telemetry.record_call(response, request, time.perf_counter() - started, attempt, trace)
        return response

    resent = False
    try:
        response = await send()
    except (httpx.RemoteProtocolError, httpx.ReadError):
        # A reused idle connection may have been closed by the server just as it
        # was taken. Send again on a fresh one, but only if repeating is harmless.
        if method.upper() not in _IDEMPOTENT and not read_only:
            raise
        resent = True
        response = await send()
    if resent and method.upper() == "DELETE" and response.status_code == 404:
        # The first DELETE may have been executed before its response was lost:
        # the resource being gone is the outcome that was asked for.
        return None
    if response.status_code == 401 and _token_provider.renewable:
        # The token may have expired or been revoked early: get a new one, once.
        _token_provider.invalidate()
        response = await send()
    response.raise_for_status()

    if response.status_code == 204:   # DELETE returns no body
        return None
    return response.json()


# ─── Error handler ─────────────────────────────────────────────────────────────

def tool_error(e: Exception) -> ToolError:
    """The exception a tool raises when it fails.

    The MCP client receives a result flagged isError whose text is the readable
    message from handle_error(), so the model can still act on it, and clients
    that measure success (or show errors differently) see the call as failed.
    Usage in a tool:  except Exception as e: raise tool_error(e) from e
    """
    return ToolError(handle_error(e))


def handle_error(e: Exception) -> str:
    """Convert any exception into a clear, actionable error message.

    Tools raise it wrapped in a ToolError (see tool_error) instead of crashing.
    """
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code

        # Try to extract the CAMARA error body (has "code" and "message" fields)
        try:
            body = e.response.json()
            detail = str(body.get("message") or body.get("code") or "")
            # The messages below add their own period after the detail.
            detail = detail.strip().rstrip(".").rstrip()
            suffix = f" — {detail}" if detail else ""
        except Exception:
            suffix = ""

        messages: Dict[int, str] = {
            400: f"Error 400 Bad Request{suffix}. Check all required fields are correct.",
            401: (
                f"Error 401 Unauthorized{suffix}. Check the credentials: CAMARA_ACCESS_TOKEN, or "
                "CAMARA_CLIENT_ID and CAMARA_CLIENT_SECRET."
            ),
            403: f"Error 403 Forbidden{suffix}. Your token lacks the required scope.",
            404: f"Error 404 Not Found{suffix}. Verify the ID is correct.",
            409: f"Error 409 Conflict{suffix}. Resource may already exist or be in an incompatible state.",
            410: f"Error 410 Gone{suffix}. The resource no longer exists.",
            422: f"Error 422 Unprocessable Content{suffix}. Check device identifier rules.",
        }
        return messages.get(status, f"Error {status}{suffix}. API request failed.")

    if isinstance(e, TokenError):
        return (
            f"Error: Could not obtain an access token: {e}. "
            "Check CAMARA_TOKEN_URL, CAMARA_CLIENT_ID, CAMARA_CLIENT_SECRET and CAMARA_SCOPE."
        )
    if isinstance(e, httpx.ConnectError):
        return (
            f"Error: Cannot connect to {API_ROOT}. "
            "Check that CAMARA_API_ROOT is correct and the server is running."
        )
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Check that CAMARA_API_ROOT is reachable."

    return f"Error: {type(e).__name__}: {e}"
