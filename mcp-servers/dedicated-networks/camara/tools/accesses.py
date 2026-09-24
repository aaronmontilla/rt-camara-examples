"""
camara/tools/accesses.py
────────────────────────
MCP tools for the dedicated-network-accesses API (full lifecycle management).

API base path: /dedicated-network-accesses/vwip
Operations:
  GET    /accesses            → camara_list_accesses
  POST   /accesses            → camara_create_access
  GET    /accesses/{id}       → camara_get_access
  DELETE /accesses/{id}       → camara_delete_access

Call register_access_tools(mcp) once from server.py to activate all four tools.
"""

import json
from typing import Any, Dict, List

from mcp.server.mcpserver import MCPServer as FastMCP

from camara.client import api_request, handle_error
from camara.formatters import fmt_access
from camara.models import (
    CreateAccessInput,
    DeleteAccessInput,
    GetAccessInput,
    ListAccessesInput,
    ResponseFormat,
)


def register_access_tools(mcp: FastMCP) -> None:
    """Register all Device Access tools on the given FastMCP server instance."""

    # ── camara_list_accesses ───────────────────────────────────────────────────

    @mcp.tool(
        name="camara_list_accesses",
        annotations={
            "title": "List Device Accesses",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_list_accesses(params: ListAccessesInput) -> str:
        """List device access grants, optionally filtered by network.

        Access statuses:
          REQUESTED — submitted, awaiting CSP approval
          GRANTED   — device is permitted to use the dedicated network
          REJECTED  — access was denied by the CSP
          DELETED   — access has been removed

        Args:
            params.networkId (optional str): Filter results to a specific network UUID.
                Omit to return accesses across all your networks.
            params.response_format: 'markdown' (default) or 'json'.

        Returns:
            List of device accesses. Each has: id, status, networkId, device,
            defaultQosProfile, qosProfiles, sink.

        Use when:
            - "Show me all device accesses"
            - "Which devices have access to network b69e5404-...?"
        """
        try:
            query_params: Dict[str, Any] = {}
            if params.networkId:
                query_params["networkId"] = params.networkId

            accesses: List[Dict[str, Any]] = await api_request(
                "accesses", "/accesses", params=query_params
            )

            if params.response_format == ResponseFormat.JSON:
                return json.dumps({"accesses": accesses, "count": len(accesses)}, indent=2)

            if not accesses:
                return "No device accesses found."
            return f"# Device Accesses ({len(accesses)})\n\n" + "\n".join(
                fmt_access(a) for a in accesses
            )

        except Exception as e:
            return handle_error(e)

    # ── camara_get_access ──────────────────────────────────────────────────────

    @mcp.tool(
        name="camara_get_access",
        annotations={
            "title": "Get Device Access",
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_get_access(params: GetAccessInput) -> str:
        """Get the current details of a specific device access grant by its UUID.

        Use to check the status (REQUESTED / GRANTED / REJECTED / DELETED)
        and QoS configuration of a previously created access.

        Args:
            params.accessId (str): UUID of the device access grant.
            params.response_format: 'markdown' (default) or 'json'.

        Returns:
            Access details: id, status, networkId, device, defaultQosProfile,
            qosProfiles, statusInfo (reason code if REJECTED), sink.

        Errors:
            404 — access not found; verify the accessId UUID.

        Use when:
            - "What is the status of access c3d4e5f6-...?"
            - "Has my device access been GRANTED yet?"
        """
        try:
            access: Dict[str, Any] = await api_request(
                "accesses", f"/accesses/{params.accessId}"
            )

            if params.response_format == ResponseFormat.JSON:
                return json.dumps(access, indent=2)
            return f"# Device Access\n\n{fmt_access(access)}"

        except Exception as e:
            return handle_error(e)

    # ── camara_create_access ───────────────────────────────────────────────────

    @mcp.tool(
        name="camara_create_access",
        annotations={
            "title": "Create Device Access",
            "readOnlyHint": False,
            "destructiveHint": False,
            "idempotentHint": False,
            "openWorldHint": True,
        },
    )
    async def camara_create_access(params: CreateAccessInput) -> str:
        """Grant a device access to a dedicated network.

        With a two-legged access token: you MUST provide the device field to
        identify which device gets access.

        With a three-legged access token: the device is derived automatically
        from the token — do NOT provide the device field.

        Optionally restrict which QoS profiles the device may use by supplying
        qosProfiles (a subset of what the network allows). Omit to allow all.

        Args:
            params.networkId (str): UUID of the dedicated network.
            params.device (optional): Device identifier (phone number, IPv4, or IPv6).
                Required with two-legged token; omit with three-legged token.
            params.qosProfiles (optional list[str]): Allowed QoS profiles for this device.
            params.defaultQosProfile (optional str): Default QoS profile for this device.
            params.sink (optional str): HTTPS notification callback URL.
            params.sinkCredential (optional): Credentials for the callback.

        Returns:
            Created access with: id (store as accessId), status='REQUESTED',
            networkId, device, qosProfiles.

        Errors:
            400 — invalid arguments; check device identifier format.
            404 — networkId not found; verify the network UUID.
            422 — device identifier rules violated (e.g. NAI not supported).

        Use when:
            - "Grant my phone +1234567890 access to network b69e5404-..."
            - "Allow this device to use the dedicated network"
        """
        try:
            body: Dict[str, Any] = {"networkId": params.networkId}

            if params.device:
                body["device"] = params.device.model_dump(exclude_none=True)
            if params.qosProfiles:
                body["qosProfiles"] = params.qosProfiles
            if params.defaultQosProfile:
                body["defaultQosProfile"] = params.defaultQosProfile
            if params.sink:
                body["sink"] = params.sink
            if params.sinkCredential:
                body["sinkCredential"] = params.sinkCredential.model_dump(exclude_none=True)

            access: Dict[str, Any] = await api_request(
                "accesses", "/accesses", method="POST", body=body
            )

            access_id = access.get("id", "?")
            return (
                f"# Device Access Created\n\n"
                f"Access request submitted. It will move from REQUESTED to GRANTED "
                f"once the CSP approves it.\n\n"
                f"{fmt_access(access)}\n"
                f"**Access ID**: `{access_id}` — use this with `camara_delete_access` "
                f"to revoke access when no longer needed."
            )

        except Exception as e:
            return handle_error(e)

    # ── camara_delete_access ───────────────────────────────────────────────────

    @mcp.tool(
        name="camara_delete_access",
        annotations={
            "title": "Delete Device Access",
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": True,
        },
    )
    async def camara_delete_access(params: DeleteAccessInput) -> str:
        """Revoke a device access grant. This cannot be undone.

        Removes the device's permission to use the dedicated network.
        Delete all accesses before deleting the network itself.

        Args:
            params.accessId (str): UUID of the device access grant to delete.

        Returns:
            Confirmation message on success.

        Errors:
            404 — access not found; verify the accessId UUID.

        Use when:
            - "Revoke access c3d4e5f6-... from the network"
            - "Remove the device access I created earlier"
        """
        try:
            await api_request("accesses", f"/accesses/{params.accessId}", method="DELETE")
            return (
                f"Access `{params.accessId}` has been successfully deleted "
                f"(device access revoked)."
            )
        except Exception as e:
            return handle_error(e)
