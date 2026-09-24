"""
camara/tools/networks.py
─────────────────────────
MCP tools for the dedicated-network API (full lifecycle management).

API base path: /dedicated-network/vwip
Operations:
  GET    /networks            → camara_list_networks
  POST   /networks            → camara_create_network
  GET    /networks/{id}       → camara_get_network
  DELETE /networks/{id}       → camara_delete_network

Call register_network_tools(mcp) once from server.py to activate all four tools.
"""

import json
from typing import Any, Dict, List

from mcp.server.mcpserver import MCPServer as FastMCP

from camara.client import api_request, handle_error
from camara.formatters import fmt_network
from camara.models import (
    CreateNetworkInput,
    DeleteNetworkInput,
    GetNetworkInput,
    ListNetworksInput,
    ResponseFormat,
)


def register_network_tools(mcp: FastMCP) -> None:
    """Register all Network tools on the given FastMCP server instance."""

    # ── camara_list_networks ───────────────────────────────────────────────────

    @mcp.tool(
        name="camara_list_networks",
        annotations={
            "title": "List Dedicated Networks",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_list_networks(params: ListNetworksInput) -> str:
        """List all dedicated networks that belong to you.

        Network statuses:
          REQUESTED  — submitted, awaiting CSP approval
          RESERVED   — resources committed, outside the active time window
          ACTIVATED  — network is live; devices with GRANTED access can use it
          TERMINATED — network has ended; only deletion is possible

        Args:
            params.response_format: 'markdown' (default) or 'json'.

        Returns:
            List of networks. Each has: id, status, serviceAreaId,
            serviceTime (start/end), networkProfileId or qosProfileName, sink.

        Use when:
            - "Show me all my dedicated networks"
            - "Which networks are currently ACTIVATED?"
        """
        try:
            networks: List[Dict[str, Any]] = await api_request("networks", "/networks")

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"networks": networks, "count": len(networks)}, indent=2)

            if not networks:
                return "No dedicated networks found."
            return f"# Dedicated Networks ({len(networks)})\n\n" + "\n".join(
                fmt_network(n) for n in networks
            )

        except Exception as e:
            return handle_error(e)

    # ── camara_get_network ─────────────────────────────────────────────────────

    @mcp.tool(
        name="camara_get_network",
        annotations={
            "title": "Get Dedicated Network",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_get_network(params: GetNetworkInput) -> str:
        """Get the current details of a specific dedicated network by its UUID.

        Use to check the status (REQUESTED / RESERVED / ACTIVATED / TERMINATED)
        and full configuration of a previously created network.

        Args:
            params.networkId (str): UUID of the network.
            params.response_format: 'markdown' (default) or 'json'.

        Returns:
            Network details: id, status, serviceAreaId, serviceTime,
            networkProfileId or qosProfileName, sink.

        Errors:
            404 — network not found; verify the networkId UUID.

        Use when:
            - "What is the status of network b69e5404-...?"
            - "Has my network been ACTIVATED yet?"
        """
        try:
            network: Dict[str, Any] = await api_request(
                "networks", f"/networks/{params.networkId}"
            )

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(network, indent=2)
            return f"# Dedicated Network\n\n{fmt_network(network)}"

        except Exception as e:
            return handle_error(e)

    # ── camara_create_network ──────────────────────────────────────────────────

    @mcp.tool(
        name="camara_create_network",
        annotations={
            "title": "Create Dedicated Network",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def camara_create_network(params: CreateNetworkInput) -> str:
        """Create a new dedicated network reservation.

        You must provide EXACTLY ONE of:
          - networkProfileId: profile UUID from camara_list_profiles.
            Supports multiple devices, aggregated throughput, and multiple QoS profiles.
          - qosProfileName: simplified option for a single-device network.

        You must also provide:
          - serviceAreaId: UUID from camara_retrieve_service_areas
          - serviceTime: {start, end} RFC 3339 timestamps with timezone

        The network starts in REQUESTED status. Once approved by the CSP it becomes
        RESERVED (if the start time is in the future) or ACTIVATED (if immediate).

        The returned networkId is required to grant device access via camara_create_access.

        Args:
            params.serviceAreaId (str): UUID of the service area.
            params.serviceTime: {start, end} RFC 3339 timestamps.
            params.networkProfileId (optional str): profile UUID (exclusive with qosProfileName).
            params.qosProfileName (optional str): QoS name (exclusive with networkProfileId).
            params.sink (optional str): HTTPS notification callback URL.
            params.sinkCredential (optional): credentials for the callback.

        Returns:
            Created network with: id (store as networkId), status='REQUESTED',
            serviceAreaId, serviceTime, networkProfileId or qosProfileName.

        Errors:
            400 — invalid arguments; check timestamp formats and UUID formats.
            400 — if both or neither of networkProfileId/qosProfileName are given.

        Use when:
            - "Create a dedicated network using profile abc in area xyz from 9am to 5pm"
        """
        try:
            body: Dict[str, Any] = {
                "serviceAreaId": params.serviceAreaId,
                "serviceTime":   params.serviceTime.model_dump(),
            }
            if params.networkProfileId:
                body["networkProfileId"] = params.networkProfileId
            if params.qosProfileName:
                body["qosProfileName"] = params.qosProfileName
            if params.sink:
                body["sink"] = params.sink
            if params.sinkCredential:
                body["sinkCredential"] = params.sinkCredential.model_dump(exclude_none=True)

            network: Dict[str, Any] = await api_request(
                "networks", "/networks", method="POST", body=body
            )



            network_id = network.get("id", "?")
            return (
                f"# Dedicated Network Created\n\n"
                f"Network submitted. It will move from REQUESTED to RESERVED or ACTIVATED "
                f"based on the service time window.\n\n"
                f"{fmt_network(network)}\n"
                f"**Next step**: Use `camara_create_access` with `networkId = {network_id}` "
                f"to grant device access."
            )

        except Exception as e:
            return handle_error(e)

    # ── camara_delete_network ──────────────────────────────────────────────────

    @mcp.tool(
        name="camara_delete_network",
        annotations={
            "title": "Delete Dedicated Network",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_delete_network(params: DeleteNetworkInput) -> str:
        """Delete (cancel) a dedicated network reservation. This cannot be undone.

        Deletion cancels the resource reservation. Any associated device accesses
        should be deleted first via camara_delete_access.

        Args:
            params.networkId (str): UUID of the network to delete.

        Returns:
            Confirmation message on success.

        Errors:
            404 — network not found; verify the networkId UUID.

        Use when:
            - "Cancel the dedicated network b69e5404-..."
            - "Delete the network I created earlier"
        """
        try:
            await api_request("networks", f"/networks/{params.networkId}", method="DELETE")
            return (
                f"Network `{params.networkId}` has been successfully deleted "
                f"(resource reservation cancelled)."
            )
        except Exception as e:
            return handle_error(e)
