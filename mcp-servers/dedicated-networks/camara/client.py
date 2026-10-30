"""
camara/client.py
────────────────
Shared HTTP client and error handler used by every tool.

Only two things are exported:
  api_request(api, path, method, body, params)  →  parsed JSON (dict / list / None)
  handle_error(exception)                        →  human-readable error string
"""

from typing import Any, Dict, Optional

import httpx

from camara.config import ACCESS_TOKEN, API_ROOT, API_PATHS


# ─── HTTP headers ──────────────────────────────────────────────────────────────

def _build_headers() -> Dict[str, str]:
    """Return request headers for every CAMARA API call.

    Always includes Content-Type and Accept for JSON.
    Adds Authorization: Bearer <token> only when a token is configured.
    """
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if ACCESS_TOKEN:
        headers["Authorization"] = f"Bearer {ACCESS_TOKEN}"
    return headers


# ─── Generic HTTP request ──────────────────────────────────────────────────────

async def api_request(
    api: str,                                    # key in API_PATHS, e.g. "networks"
    path: str,                                   # e.g. "/networks" or "/networks/{id}"
    method: str = "GET",
    body: Optional[Dict[str, Any]] = None,       # JSON request body (POST)
    params: Optional[Dict[str, Any]] = None,     # URL query parameters (GET)
) -> Any:
    """Send an HTTP request to a CAMARA sub-API and return the parsed JSON body.

    Builds the full URL from API_ROOT + the sub-API path + the endpoint path.
    Strips out any query parameters whose value is None.
    Raises httpx.HTTPStatusError on 4xx / 5xx so handle_error() can format them.
    Returns None for 204 No Content (used by DELETE operations).
    """
    url = f"{API_ROOT}{API_PATHS[api]}{path}"

    # Drop query params that were not provided (value is None)
    clean_params = {k: v for k, v in (params or {}).items() if v is not None}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.request(
            method=method,
            url=url,
            headers=_build_headers(),
            json=body,
            params=clean_params or None,
        )
        response.raise_for_status()

        if response.status_code == 204:   # DELETE returns no body
            return None
        return response.json()


# ─── Error handler ─────────────────────────────────────────────────────────────

def handle_error(e: Exception) -> str:
    """Convert any exception into a clear, actionable error message.

    Returns a plain string so tool functions can return it directly to Claude
    instead of crashing.
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
            401: f"Error 401 Unauthorized{suffix}. Set a valid token via CAMARA_ACCESS_TOKEN.",
            403: f"Error 403 Forbidden{suffix}. Your token lacks the required scope.",
            404: f"Error 404 Not Found{suffix}. Verify the ID is correct.",
            409: f"Error 409 Conflict{suffix}. Resource may already exist or be in an incompatible state.",
            410: f"Error 410 Gone{suffix}. The resource no longer exists.",
            422: f"Error 422 Unprocessable Content{suffix}. Check device identifier rules.",
        }
        return messages.get(status, f"Error {status}{suffix}. API request failed.")

    if isinstance(e, httpx.ConnectError):
        return (
            f"Error: Cannot connect to {API_ROOT}. "
            "Check that CAMARA_API_ROOT is correct and the server is running."
        )
    if isinstance(e, httpx.TimeoutException):
        return "Error: Request timed out. Check that CAMARA_API_ROOT is reachable."

    return f"Error: {type(e).__name__}: {e}"
