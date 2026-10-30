"""
camara/tools/areas.py
──────────────────────
MCP tools for the dedicated-network-areas API (read-only).

API base path: /dedicated-network-areas/vwip
Operations:
  POST /retrieve-service-areas → camara_retrieve_service_areas
  GET  /areas/{areaId}         → camara_get_area

Call register_area_tools(mcp) once from server.py to activate both tools.
"""

import json
from typing import Any, Dict, List

from mcp.server.mcpserver import MCPServer as FastMCP

from camara.client import api_request, tool_error
from camara.formatters import fmt_area
from camara.geo import combined_geojson_url, with_geojson_url
from camara.models import GetAreaInput, ResponseFormat, RetrieveAreasInput


def register_area_tools(mcp: FastMCP) -> None:
    """Register all Area tools on the given FastMCP server instance."""

    # ── camara_retrieve_service_areas ──────────────────────────────────────────

    @mcp.tool(
        name="camara_retrieve_service_areas",
        annotations={
            "title": "Retrieve Dedicated Network Service Areas",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_retrieve_service_areas(params: RetrieveAreasInput) -> str:
        """Search for network service areas using geographic or profile filters.

        A service area is a geographic region with consistent dedicated network
        coverage. Its 'id' (serviceAreaId) is required when creating a network
        with camara_create_network.

        All filters are optional and AND-combined (all specified criteria must match):
          - atLocation:          point that must be covered by the area
          - overlappingArea:     CIRCLE or POLYGON that must overlap the area
          - coveringArea:        CIRCLE or POLYGON that the area must fully contain
          - byName:              exact name match
          - byNetworkProfileId:  areas supporting a specific network profile UUID
          - byQosProfileName:    areas supporting a specific QoS profile name

        Args:
            params.atLocation (optional): {latitude, longitude}
            params.overlappingArea (optional): {areaType: 'CIRCLE'|'POLYGON', ...}
            params.coveringArea (optional): same format as overlappingArea
            params.byName (optional str)
            params.byNetworkProfileId (optional str)
            params.byQosProfileName (optional str)
            params.response_format: 'markdown' (default) or 'json'

        Returns:
            List of matching service areas. Each has: id (use as serviceAreaId),
            name, description, area (CIRCLE or POLYGON with coordinates),
            networkProfiles, qosProfiles, plus a GeoJSON map link
            ('geojsonUrl' in JSON, 'GeoJSON map' in Markdown; 'geojsonNote'
            instead if the geometry cannot be drawn). With several areas, a
            link drawing all of them together is also returned.

        IMPORTANT: always show the user each area's GeoJSON map link, copied in
        full and unmodified, whenever you present an area. Skip it only if you
        gave that exact link in your immediately preceding message.

        Use when:
            - "Find service areas near latitude 50.74, longitude 7.10"
            - "Which areas support profile enterprise-hd?"
            - "List all available service areas"
        """
        try:
            body: Dict[str, Any] = {}
            if params.atLocation:
                body["atLocation"] = params.atLocation.model_dump()
            if params.overlappingArea:
                body["overlappingArea"] = params.overlappingArea
            if params.coveringArea:
                body["coveringArea"] = params.coveringArea
            if params.byName:
                body["byName"] = params.byName
            if params.byNetworkProfileId:
                body["byNetworkProfileId"] = params.byNetworkProfileId
            if params.byQosProfileName:
                body["byQosProfileName"] = params.byQosProfileName

            areas: List[Dict[str, Any]] = (
                await api_request("areas", "/retrieve-service-areas", method="POST", body=body)
                or []
            )
            all_url = combined_geojson_url(areas)

            if params.response_format == ResponseFormat.JSON:
                result: Dict[str, Any] = {
                    "areas": [with_geojson_url(a) for a in areas],
                    "count": len(areas),
                }
                if all_url:
                    result["geojsonUrl"] = all_url
                return json.dumps(result, indent=2)

            if not areas:
                return "No service areas found matching the given criteria."
            header = f"# Network Service Areas ({len(areas)})\n\n"
            if len(areas) > 1 and all_url:
                header += f"**All areas on one map**: [View all areas]({all_url})\n\n"
            return header + "\n".join(fmt_area(a) for a in areas)

        except Exception as e:
            raise tool_error(e) from e

    # ── camara_get_area ────────────────────────────────────────────────────────

    @mcp.tool(
        name="camara_get_area",
        annotations={
            "title": "Get Dedicated Network Service Area",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_get_area(params: GetAreaInput) -> str:
        """Get the full details of a specific service area by its UUID.

        Use this to inspect the geographic boundary and supported profiles of
        a known area before creating a network in it.

        Args:
            params.areaId (str): UUID of the service area.
            params.response_format: 'markdown' (default) or 'json'.

        Returns:
            Area details: id, name, description, area geometry (CIRCLE or POLYGON),
            networkProfiles, qosProfiles, plus a GeoJSON map link ('geojsonUrl'
            in JSON, 'GeoJSON map' in Markdown; 'geojsonNote' instead if the
            geometry cannot be drawn).

        IMPORTANT: always show the user the area's GeoJSON map link, copied in
        full and unmodified, whenever you present the area. Skip it only if you
        gave that exact link in your immediately preceding message.

        Errors:
            404 — area not found; verify the areaId UUID.

        Use when:
            - "Show me service area xyz-789"
            - "What is the geographic boundary of area abc-123?"
        """
        try:
            area: Dict[str, Any] = await api_request("areas", f"/areas/{params.areaId}")

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(with_geojson_url(area), indent=2)
            return f"# Network Service Area\n\n{fmt_area(area)}"

        except Exception as e:
            raise tool_error(e) from e
