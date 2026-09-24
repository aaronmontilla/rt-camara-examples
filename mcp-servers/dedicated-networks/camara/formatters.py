"""
camara/formatters.py
─────────────────────
Functions that convert raw API JSON into readable Markdown text.

These are called by tool functions when response_format == "markdown".
Each formatter receives a plain Python dict (the API response) and returns
a Markdown string that Claude can display to the user.

Exported:
  fmt_network(n)   → Markdown block for one dedicated network
  fmt_profile(p)   → Markdown block for one network profile
  fmt_access(a)    → Markdown block for one device access grant
  fmt_area(a)      → Markdown block for one service area
"""

from typing import Any, Dict, List

from camara.geo import area_geojson_url


# ─── Networks ──────────────────────────────────────────────────────────────────

def fmt_network(n: Dict[str, Any]) -> str:
    """Format a single dedicated network as a Markdown section."""
    lines = [
        f"## Network `{n.get('id', '?')}`",
        f"- **Status**: {n.get('status', '?')}",
        f"- **Service Area**: {n.get('serviceAreaId', '?')}",
    ]

    service_time = n.get("serviceTime") or {}
    if service_time:
        lines.append(
            f"- **Service Time**: {service_time.get('start', '?')} → {service_time.get('end', '?')}"
        )

    if n.get("networkProfileId"):
        lines.append(f"- **Network Profile**: {n['networkProfileId']}")
    if n.get("qosProfileName"):
        lines.append(f"- **QoS Profile**: {n['qosProfileName']}")
    if n.get("sink"):
        lines.append(f"- **Notification Sink**: {n['sink']}")

    lines.append("")   # blank line between entries
    return "\n".join(lines)


# ─── Profiles ──────────────────────────────────────────────────────────────────

def fmt_profile(p: Dict[str, Any]) -> str:
    """Format a single network profile as a Markdown section."""
    ul = p.get("aggregatedUlThroughput") or {}
    dl = p.get("aggregatedDlThroughput") or {}

    # Use "name" as display label if available; fall back to the UUID
    label = p.get("name") or p.get("id", "?")

    lines = [
        f"## Profile: {label} (`{p.get('id', '?')}`)",
        f"- **Max Devices**: {p.get('maxNumberOfDevices', '?')}",
        f"- **Uplink**:   {ul.get('value', '?')} {ul.get('unit', '')}",
        f"- **Downlink**: {dl.get('value', '?')} {dl.get('unit', '')}",
        f"- **Supported QoS Profiles**: {', '.join(p.get('qosProfiles', []))}",
        f"- **Default QoS Profile**: {p.get('defaultQosProfile', '?')}",
        "",
    ]
    return "\n".join(lines)


# ─── Device accesses ───────────────────────────────────────────────────────────

def _device_label(device: Dict[str, Any]) -> str:
    """Summarise a device object into a short human-readable string."""
    parts: List[str] = []
    if device.get("phoneNumber"):
        parts.append(f"Phone: {device['phoneNumber']}")
    ipv4 = device.get("ipv4Address") or {}
    if ipv4.get("publicAddress"):
        parts.append(f"IPv4: {ipv4['publicAddress']}")
    if device.get("ipv6Address"):
        parts.append(f"IPv6: {device['ipv6Address']}")
    return ", ".join(parts) if parts else "Identified from access token"


def fmt_access(a: Dict[str, Any]) -> str:
    """Format a single device access grant as a Markdown section."""
    device = a.get("device") or {}
    lines = [
        f"## Access `{a.get('id', '?')}`",
        f"- **Status**: {a.get('status', '?')}",
        f"- **Network**: {a.get('networkId', '?')}",
        f"- **Device**: {_device_label(device)}",
    ]

    if a.get("defaultQosProfile"):
        lines.append(f"- **Default QoS Profile**: {a['defaultQosProfile']}")
    if a.get("qosProfiles"):
        lines.append(f"- **Allowed QoS Profiles**: {', '.join(a['qosProfiles'])}")

    # Show reason when DENIED or informational
    status_info = a.get("statusInfo") or {}
    reason = status_info.get("reason") or {}
    if reason.get("code"):
        lines.append(f"- **Status Reason**: {reason['code']} — {reason.get('message', '')}")

    if a.get("sink"):
        lines.append(f"- **Notification Sink**: {a['sink']}")

    lines.append("")
    return "\n".join(lines)


# ─── Service areas ─────────────────────────────────────────────────────────────

def fmt_area(area: Dict[str, Any]) -> str:
    """Format a single service area as a Markdown section."""
    label = area.get("name") or area.get("id", "?")
    lines = [f"## Area: {label} (`{area.get('id', '?')}`)"]

    if area.get("description"):
        lines.append(f"> {area['description']}")

    geo = area.get("area") or {}
    area_type = geo.get("areaType", "?")

    if area_type == "CIRCLE":
        ctr = geo.get("center") or {}
        lines.append(
            f"- **Geography**: Circle — centre ({ctr.get('latitude')}, {ctr.get('longitude')}), "
            f"radius {geo.get('radius')} m"
        )
    elif area_type == "POLYGON":
        pts = " → ".join(
            f"({p['latitude']}, {p['longitude']})"
            for p in geo.get("boundary", [])
        )
        lines.append(f"- **Geography**: Polygon — {pts}")
    else:
        lines.append(f"- **Geography**: {area_type}")

    url = area_geojson_url(area)
    if url:
        lines.append(f"- **GeoJSON map**: [View area]({url})")

    if area.get("networkProfiles"):
        lines.append(f"- **Network Profiles**: {', '.join(area['networkProfiles'])}")
    if area.get("qosProfiles"):
        lines.append(f"- **QoS Profiles**: {', '.join(area['qosProfiles'])}")

    lines.append("")
    return "\n".join(lines)
