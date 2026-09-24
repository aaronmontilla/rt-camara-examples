"""
camara/ui.py
────────────
Wires up the MCP Apps extension (io.modelcontextprotocol/ui): the
ui://camara/area-picker HTML resource and the camara_pick_location tool
bound to it.

The resource is served straight from ui/dist/area_picker.html (built by
`npm run build` in ui/area-picker/ — see README.md). It is read lazily on
every `resources/read`, so a missing build does not stop the server from
starting; only reading the resource fails, with a clear FileNotFoundError.

CSP: the only external origin the view needs is the tile server, and tiles
are loaded as <img> sources, so its host goes in resourceDomains rather than
connectDomains.
"""

from pathlib import Path
from urllib.parse import urlparse

from mcp.server.apps import Apps, ResourceCsp
from mcp.server.mcpserver.resources import FileResource

from camara.config import MAP_TILE_URL
from camara.tools.picker import AREA_PICKER_URI, register_picker_tool

# ui/area-picker/ builds into ui/dist/area_picker.html at the repo root.
_DIST_HTML = Path(__file__).resolve().parent.parent / "ui" / "dist" / "area_picker.html"


def _tile_resource_domain(tile_url: str) -> str:
    """The hostname the tile server is served from, for the resource's CSP."""
    host = urlparse(tile_url).hostname
    return host or tile_url


def build_apps_extension() -> Apps:
    """Build the Apps extension: the area-picker resource plus its tool."""
    apps = Apps()

    csp = ResourceCsp(resource_domains=[_tile_resource_domain(MAP_TILE_URL)])
    apps.add_resource(
        FileResource(
            uri=AREA_PICKER_URI,
            name="camara-area-picker",
            title="CAMARA Service Area Picker",
            description="Interactive map to choose a dedicated-network location.",
            path=_DIST_HTML,
            meta={"ui": {"csp": csp.model_dump(by_alias=True, exclude_none=True)}},
        )
    )
    register_picker_tool(apps)

    return apps
