"""
tests/test_apps_extension.py
─────────────────────────────
Checks the MCP Apps wiring itself, independent of a running server:

  - camara_pick_location advertises _meta.ui.resourceUri (what tools/list
    must expose so a host knows which ui:// resource to render).
  - The ui://camara/area-picker resource is served with the
    text/html;profile=mcp-app MIME type MCP Apps requires.
  - None of this disturbs the 12 pre-existing tools.
"""

from mcp.server.apps import APP_MIME_TYPE

from camara.ui import AREA_PICKER_URI, build_apps_extension


def test_pick_location_tool_exposes_ui_resource_uri():
    apps = build_apps_extension()
    bindings = {binding.fn.__name__: binding for binding in apps.tools()}

    assert "camara_pick_location" in bindings
    assert bindings["camara_pick_location"].meta == {"ui": {"resourceUri": AREA_PICKER_URI}}


def test_area_picker_resource_uses_mcp_app_mime_type():
    apps = build_apps_extension()
    resources = {binding.resource.uri: binding.resource for binding in apps.resources()}

    assert AREA_PICKER_URI in resources
    assert resources[AREA_PICKER_URI].mime_type == APP_MIME_TYPE


def test_area_picker_resource_csp_points_at_tile_host():
    apps = build_apps_extension()
    resource = next(b.resource for b in apps.resources() if b.resource.uri == AREA_PICKER_URI)

    # Tiles load as <img> sources, so the tile host belongs in resourceDomains,
    # not connectDomains.
    assert resource.meta["ui"]["csp"] == {"resourceDomains": ["tile.openstreetmap.org"]}


def test_server_registers_tools_matching_map_picker_flag():
    import server  # imported lazily so this test doesn't pay import cost for the others

    names = {t.name for t in server.mcp._tool_manager.list_tools()}
    if server.ENABLE_MAP_PICKER:
        assert "camara_pick_location" in names
        assert len(names) == 13  # the 12 regular tools + camara_pick_location
    else:
        # Map picker temporarily disabled (see server.py)
        assert "camara_pick_location" not in names
        assert len(names) == 12
