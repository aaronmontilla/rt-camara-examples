#!/usr/bin/env python3
"""
CAMARA Dedicated Networks — MCP Server (Python)
================================================
Entry point.  Creates the FastMCP instance, registers all tool groups,
and starts the server.

The four API groups:
  1. dedicated-network            → Networks (create / list / get / delete)
  2. dedicated-network-profiles   → Profiles (list / get)        [read-only]
  3. dedicated-network-accesses   → Device Accesses (create / list / get / delete)
  4. dedicated-network-areas      → Service Areas (retrieve / get) [read-only]

Plus one MCP Apps (io.modelcontextprotocol/ui) tool: camara_pick_location,
which opens an interactive map (see camara/ui.py).

Configuration (environment variables):
  CAMARA_API_ROOT      Base URL of your CAMARA server   (default: http://localhost:9091)
  CAMARA_ACCESS_TOKEN  Bearer token for authentication  (default: empty → no auth header)
  CAMARA_MAP_TILE_URL  XYZ tile URL for the area-picker map
                       (default: https://tile.openstreetmap.org/{z}/{x}/{y}.png)

Run (stdio transport for Claude Desktop):
  python server.py

For full setup instructions see README.md.
"""

from mcp.server.mcpserver import MCPServer as FastMCP

from camara.tools.networks  import register_network_tools
from camara.tools.profiles  import register_profile_tools
from camara.tools.accesses  import register_access_tools
from camara.tools.areas     import register_area_tools
from camara.prompts         import register_prompts
from camara.ui              import build_apps_extension

# ── Create the MCP server instance ────────────────────────────────────────────
# The Apps extension is fixed at construction time, so it's built first and
# passed in; it contributes the ui://camara/area-picker resource and the
# camara_pick_location tool on top of the tools registered below.
# TEMPORARILY DISABLED: the interactive map does not work as required yet.
# Flip ENABLE_MAP_PICKER to True to bring camara_pick_location back. Areas are
# meanwhile visualised through GeoJSON URLs (see camara/geo.py).
ENABLE_MAP_PICKER = False

mcp = FastMCP(
    "CAMARA Dedicated Networks",
    extensions=[build_apps_extension()] if ENABLE_MAP_PICKER else [],
)

# ── Register all tool groups ───────────────────────────────────────────────────
register_network_tools(mcp)
register_profile_tools(mcp)
register_access_tools(mcp)
register_area_tools(mcp)

# ── Register workflow guidance prompts ────────────────────────────────────────
register_prompts(mcp)

# ── Start the server ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run()
