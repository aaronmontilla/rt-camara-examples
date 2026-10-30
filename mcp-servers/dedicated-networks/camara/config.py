"""
camara/config.py
────────────────
Central place for all configuration.

Every setting is read from an environment variable so that Claude Desktop
(or any other host) can inject them without changing source code.

Environment variables:
  CAMARA_API_ROOT       Base URL of your CAMARA API server
                        Default: http://localhost:9091
  CAMARA_ACCESS_TOKEN   Bearer token for authentication, used as given
                        Default: "" (no Authorization header is sent)
  CAMARA_TOKEN_URL      OAuth 2.0 token endpoint (client credentials grant)
  CAMARA_CLIENT_ID      OAuth client id
  CAMARA_CLIENT_SECRET  OAuth client secret
  CAMARA_SCOPE          Space-separated scopes to request (optional)
  CAMARA_TOKEN_AUTH     "basic" (HTTP Basic, default) or "body" (client id and
                        secret sent as form fields), as the provider expects
                        With the three first variables set (and no
                        CAMARA_ACCESS_TOKEN), the server requests and renews
                        tokens itself; see camara/auth.py.
  CAMARA_MAP_TILE_URL   XYZ tile URL template for the area-picker map
                        Default: https://tile.openstreetmap.org/{z}/{x}/{y}.png
"""

import os
from typing import Dict

# ─── API server URL ────────────────────────────────────────────────────────────
# All four sub-APIs append their own path to this root URL.
def _with_one_trailing_slash(url: str) -> str:
    """The sub-API paths are appended to the root as they are, so the root ends in exactly one slash."""
    return url.rstrip("/") + "/"


API_ROOT: str = _with_one_trailing_slash(os.environ.get("CAMARA_API_ROOT", "http://localhost:9091"))

# ─── Authentication ────────────────────────────────────────────────────────────
# A fixed token: when set, every HTTP request carries  Authorization: Bearer <token>
ACCESS_TOKEN: str = os.environ.get("CAMARA_ACCESS_TOKEN", "")

# OAuth 2.0 client credentials: the server obtains and renews the token itself.
TOKEN_URL: str = os.environ.get("CAMARA_TOKEN_URL", "")
CLIENT_ID: str = os.environ.get("CAMARA_CLIENT_ID", "")
CLIENT_SECRET: str = os.environ.get("CAMARA_CLIENT_SECRET", "")
SCOPE: str = os.environ.get("CAMARA_SCOPE", "")
TOKEN_AUTH: str = os.environ.get("CAMARA_TOKEN_AUTH", "basic")

# ─── Map tile server (used by the camara_pick_location UI resource) ───────────
# XYZ tile template, e.g. https://tile.openstreetmap.org/{z}/{x}/{y}.png
MAP_TILE_URL: str = os.environ.get("CAMARA_MAP_TILE_URL", "https://tile.openstreetmap.org/{z}/{x}/{y}.png")

# ─── Sub-API base paths ────────────────────────────────────────────────────────
# Each path is appended to API_ROOT to form the full base URL for that API.
# Example: http://localhost:9091/dedicated-network/vwip/networks
API_PATHS: Dict[str, str] = {
    "networks": "dedicated-network/v0.2-wip",
    "profiles": "dedicated-network-profiles/v0.2-wip",
    "accesses": "dedicated-network-accesses/v0.2-wip",
    "areas":    "dedicated-network-areas/v0.1-wip",
}


def _auth_summary() -> str:
    """How requests are authenticated, without any credential value."""
    if ACCESS_TOKEN:
        return "token set"
    client_credentials = {
        "CAMARA_TOKEN_URL": TOKEN_URL,
        "CAMARA_CLIENT_ID": CLIENT_ID,
        "CAMARA_CLIENT_SECRET": CLIENT_SECRET,
    }
    missing = [name for name, value in client_credentials.items() if not value]
    if not missing:
        return "client credentials"
    if len(missing) < len(client_credentials):
        return f"NO TOKEN (client credentials incomplete: {', '.join(missing)} not set)"
    return "NO TOKEN"


def startup_line() -> str:
    """The line the server writes to standard error when it starts. It says how requests are authenticated, never a
    token or secret."""
    return f"[camara-mcp] Starting | API root: {API_ROOT} | Auth: {_auth_summary()}"
