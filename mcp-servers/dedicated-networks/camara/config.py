"""
camara/config.py
────────────────
Central place for all configuration.

Every setting is read from an environment variable so that Claude Desktop
(or any other host) can inject them without changing source code.

Environment variables:
  CAMARA_API_ROOT       Base URL of your CAMARA API server
                        Default: http://localhost:9091
  CAMARA_ACCESS_TOKEN   Bearer token for authentication
                        Default: "" (no Authorization header is sent)
  CAMARA_MAP_TILE_URL   XYZ tile URL template for the area-picker map
                        Default: https://tile.openstreetmap.org/{z}/{x}/{y}.png
"""

import os
from typing import Dict

# ─── API server URL ────────────────────────────────────────────────────────────
# All four sub-APIs append their own path to this root URL.
API_ROOT: str = os.environ.get("CAMARA_API_ROOT", "http://localhost:9091")

# ─── Authentication token ──────────────────────────────────────────────────────
# When set, every HTTP request carries  Authorization: Bearer <token>
ACCESS_TOKEN: str = os.environ.get("CAMARA_ACCESS_TOKEN", "")

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
