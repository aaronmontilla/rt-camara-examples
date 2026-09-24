"""
camara/tools/picker.py
───────────────────────
The camara_pick_location tool: opens the ui://camara/area-picker map so the
user can point at a location instead of typing coordinates.

Unlike the other tool modules, this one registers on the `Apps` extension
(camara.ui.build_apps_extension) rather than directly on `mcp`, since MCP
Apps tools must carry `_meta.ui.resourceUri` pointing at their resource.

Reuses the same request-building logic as camara_retrieve_service_areas
(see camara/tools/areas.py) against the same /retrieve-service-areas
endpoint, but returns its own JSON envelope — areas + a computed bounding
box + the tile URL — for the map view to consume, rather than Markdown or
the plain {areas, count} shape meant for the model.
"""

import json
from typing import Any, Dict, List

from mcp.server.apps import Apps

from camara.client import api_request, handle_error
from camara.config import MAP_TILE_URL
from camara.geo import combined_bounds
from camara.models import PickLocationInput

AREA_PICKER_URI = "ui://camara/area-picker"


def register_picker_tool(apps: Apps) -> None:
    """Register camara_pick_location on the given Apps extension."""

    @apps.tool(
        resource_uri=AREA_PICKER_URI,
        name="camara_pick_location",
        annotations={
            "title": "Pick a Dedicated Network Location on a Map",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_pick_location(params: PickLocationInput) -> str:
        """Open an interactive map so the user can point at the location where a
        dedicated network is needed.

        The map shows every available service area; clicking a point highlights
        the areas that cover it and lets the user confirm one. Once confirmed,
        the chosen coordinates and serviceAreaId arrive as a follow-up user
        message — continue from there with camara_list_profiles and
        camara_create_network.

        Args:
            params.latitude / params.longitude (optional): initial map center.
                Omit both to let the map fit all returned areas.
            params.zoom (optional): initial map zoom level (0-22).
            params.byNetworkProfileId (optional): only show areas supporting
                this network profile UUID.
            params.byQosProfileName (optional): only show areas supporting this
                QoS profile name.

        Returns:
            JSON with: areas (same objects camara_retrieve_service_areas
            returns), bounds (bounding box of all areas' geometry, so the map
            can fit them), center/zoom (only present if the caller gave them),
            and tileUrl.

        Use when:
            - "I want a dedicated network, let me point at the location on a map"
            - "Show me the coverage areas on a map so I can pick one"
            - "Let me click where I need the network instead of typing coordinates"
        """
        try:
            body: Dict[str, Any] = {}
            if params.byNetworkProfileId:
                body["byNetworkProfileId"] = params.byNetworkProfileId
            if params.byQosProfileName:
                body["byQosProfileName"] = params.byQosProfileName

            areas: List[Dict[str, Any]] = (
                await api_request("areas", "/retrieve-service-areas", method="POST", body=body)
                or []
            )

            result: Dict[str, Any] = {
                "areas": areas,
                "bounds": combined_bounds(areas),
                "tileUrl": MAP_TILE_URL,
            }
            if params.latitude is not None and params.longitude is not None:
                result["center"] = {"latitude": params.latitude, "longitude": params.longitude}
            if params.zoom is not None:
                result["zoom"] = params.zoom
            if not areas:
                result["message"] = "No service areas are currently available."

            return json.dumps(result, indent=2)

        except Exception as e:
            return handle_error(e)
