"""
camara/tools/profiles.py
─────────────────────────
MCP tools for the dedicated-network-profiles API (read-only).

API base path: /dedicated-network-profiles/vwip
Operations:
  GET /profiles            → camara_list_profiles
  GET /profiles/{profileId} → camara_get_profile

Call register_profile_tools(mcp) once from server.py to activate both tools.
"""

import json
from typing import Any, Dict, List

from mcp.server.mcpserver import MCPServer as FastMCP

from camara.client import api_request, handle_error
from camara.formatters import fmt_profile
from camara.models import GetProfileInput, ListProfilesInput, ResponseFormat


def register_profile_tools(mcp: FastMCP) -> None:
    """Register all Profile tools on the given FastMCP server instance."""

    # ── camara_list_profiles ───────────────────────────────────────────────────

    @mcp.tool(
        name="camara_list_profiles",
        annotations={
            "title": "List Dedicated Network Profiles",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_list_profiles(params: ListProfilesInput) -> str:
        """List all network profiles available to you, optionally filtered by name.

        A network profile describes what a dedicated network can deliver:
          - maxNumberOfDevices: how many devices can connect simultaneously
          - aggregatedUlThroughput / aggregatedDlThroughput: bandwidth budget
          - qosProfiles: QoS profile names devices can use within the network
          - defaultQosProfile: the QoS profile applied when none is specified

        The profile 'id' (UUID) is used as 'networkProfileId' when creating a
        network with camara_create_network.

        Args:
            params.name (optional str): Exact profile name to filter by.
            params.response_format: 'markdown' (default) or 'json'.

        Returns:
            List of profiles. Each profile has: id, name, maxNumberOfDevices,
            aggregatedUlThroughput, aggregatedDlThroughput, qosProfiles, defaultQosProfile.

        Use when:
            - "What network profiles are available?"
            - "I need to create a network but don't know the profile ID"
            - "Find the profile named 'enterprise-hd'"
        """
        try:
            query = {"name": params.name} if params.name else {}
            profiles: List[Dict[str, Any]] = await api_request(
                "profiles", "/profiles", params=query
            )

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"profiles": profiles, "count": len(profiles)}, indent=2)

            if not profiles:
                return "No network profiles available."
            return f"# Network Profiles ({len(profiles)})\n\n" + "\n".join(
                fmt_profile(p) for p in profiles
            )

        except Exception as e:
            return handle_error(e)

    # ── camara_get_profile ─────────────────────────────────────────────────────

    @mcp.tool(
        name="camara_get_profile",
        annotations={
            "title": "Get Dedicated Network Profile",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_get_profile(params: GetProfileInput) -> str:
        """Get the full details of a specific network profile by its UUID.

        Use this to inspect the exact capabilities (device limit, throughput,
        supported QoS profiles) before creating a network with that profile.

        Args:
            params.profileId (str): UUID of the network profile.
            params.response_format: 'markdown' (default) or 'json'.

        Returns:
            Profile details: id, name, maxNumberOfDevices,
            aggregatedUlThroughput, aggregatedDlThroughput, qosProfiles, defaultQosProfile.

        Errors:
            404 — profile not found; verify the profileId UUID.

        Use when:
            - "Show details of profile abc-123"
            - "How many devices does profile xyz support?"
        """
        try:
            profile: Dict[str, Any] = await api_request(
                "profiles", f"/profiles/{params.profileId}"
            )

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(profile, indent=2)
            return f"# Network Profile\n\n{fmt_profile(profile)}"

        except Exception as e:
            return handle_error(e)
