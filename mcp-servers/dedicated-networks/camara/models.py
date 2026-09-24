"""
camara/models.py
────────────────
All Pydantic input models and shared enums used by the tool modules.

Pydantic validates every value Claude sends to a tool before the code runs.
If a required field is missing or has the wrong type, Pydantic raises a clear
error automatically — no manual if/else checks needed.

Exported:
  ResponseFormat          — enum: "markdown" | "json"
  ServiceTimeInput        — {start, end} RFC 3339 timestamps
  PointInput              — {latitude, longitude}
  DeviceIpv4Input         — IPv4 address object
  DeviceInput             — device identifier (phone / IPv4 / IPv6)
  SinkCredentialInput     — notification callback credentials
  ListProfilesInput       — camara_list_profiles
  GetProfileInput         — camara_get_profile
  RetrieveAreasInput      — camara_retrieve_service_areas
  GetAreaInput            — camara_get_area
  PickLocationInput       — camara_pick_location
  ListNetworksInput       — camara_list_networks
  GetNetworkInput         — camara_get_network
  CreateNetworkInput      — camara_create_network
  DeleteNetworkInput      — camara_delete_network
  ListAccessesInput       — camara_list_accesses
  GetAccessInput          — camara_get_access
  CreateAccessInput       — camara_create_access
  DeleteAccessInput       — camara_delete_access
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ═════════════════════════════════════════════════════════════════════════════
# SHARED ENUM
# ═════════════════════════════════════════════════════════════════════════════

class ResponseFormat(str, Enum):
    """Output format accepted by every listing / get tool."""
    MARKDOWN = "markdown"   # human-readable with Markdown headers and bullet points
    JSON     = "json"       # raw JSON (useful for programmatic use)


# ═════════════════════════════════════════════════════════════════════════════
# SHARED SUB-MODELS  (reused across multiple tool input models)
# ═════════════════════════════════════════════════════════════════════════════

class ServiceTimeInput(BaseModel):
    """A time window with a start and end, both in RFC 3339 format with timezone."""
    model_config = ConfigDict(str_strip_whitespace=True)

    start: str = Field(
        ...,
        description="Start time, RFC 3339 with timezone. E.g. '2025-06-01T10:00:00Z'",
    )
    end: str = Field(
        ...,
        description="End time, RFC 3339 with timezone. E.g. '2025-06-01T18:00:00Z'",
    )


class PointInput(BaseModel):
    """A geographic coordinate expressed as latitude and longitude."""
    model_config = ConfigDict(validate_assignment=True)

    latitude: float = Field(
        ..., ge=-90, le=90,
        description="Latitude in decimal degrees. Range: -90 (south pole) to 90 (north pole).",
    )
    longitude: float = Field(
        ..., ge=-180, le=180,
        description="Longitude in decimal degrees. Range: -180 to 180.",
    )


class DeviceIpv4Input(BaseModel):
    """IPv4 address identifier for a device.

    Requires either (publicAddress + privateAddress) or (publicAddress + publicPort).
    """
    model_config = ConfigDict(validate_assignment=True)

    publicAddress:  Optional[str] = Field(None, description="Public IPv4, e.g. '84.125.93.10'")
    privateAddress: Optional[str] = Field(None, description="Private IPv4, e.g. '192.168.1.5'")
    publicPort:     Optional[int] = Field(None, ge=0, le=65535, description="TCP/UDP port (0–65535)")


class DeviceInput(BaseModel):
    """Identifies a device.  Provide at least one identifier field."""
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    phoneNumber: Optional[str] = Field(
        None,
        pattern=r"^\+[1-9][0-9]{4,14}$",
        description="E.164 phone number starting with '+', e.g. '+1234567890'",
    )
    networkAccessIdentifier: Optional[str] = Field(
        None,
        description="NAI, e.g. '123456789@domain.com' (reserved for future use)",
    )
    ipv4Address: Optional[DeviceIpv4Input] = Field(
        None,
        description="IPv4 address object with publicAddress and privateAddress or publicPort",
    )
    ipv6Address: Optional[str] = Field(
        None,
        description="IPv6 address, e.g. '2001:db8:85a3::8a2e:370:7334'",
    )


class SinkCredentialInput(BaseModel):
    """Credentials for authenticating to a notification callback (sink) endpoint."""
    model_config = ConfigDict(validate_assignment=True)

    credentialType: str = Field(
        ...,
        description="Type of credential: 'PLAIN', 'ACCESSTOKEN', or 'REFRESHTOKEN'",
    )
    # PLAIN fields
    identifier: Optional[str] = Field(None, description="Username (used with PLAIN)")
    secret:     Optional[str] = Field(None, description="Password (used with PLAIN)")
    # ACCESSTOKEN / REFRESHTOKEN fields
    accessToken:            Optional[str] = Field(None, description="Bearer token")
    accessTokenExpiresUtc:  Optional[str] = Field(None, description="Token expiry (RFC 3339)")
    accessTokenType:        Optional[str] = Field(None, description="Must be 'bearer'")
    # REFRESHTOKEN extra fields
    refreshToken:           Optional[str] = Field(None, description="Refresh token value")
    refreshTokenEndpoint:   Optional[str] = Field(None, description="URL to exchange refresh token")


# ═════════════════════════════════════════════════════════════════════════════
# PROFILES  (API 2)
# ═════════════════════════════════════════════════════════════════════════════

class ListProfilesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[str] = Field(
        None,
        description="Filter by exact profile name. Omit to return all available profiles.",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' for human-readable output, 'json' for raw data.",
    )


class GetProfileInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profileId: str = Field(
        ...,
        description="UUID of the network profile, e.g. 'a1b2c3d4-e5f6-...'",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' or 'json'.",
    )


# ═════════════════════════════════════════════════════════════════════════════
# AREAS  (API 4)
# ═════════════════════════════════════════════════════════════════════════════

class RetrieveAreasInput(BaseModel):
    """All filters are optional and AND-combined."""
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    atLocation: Optional[PointInput] = Field(
        None,
        description=(
            "Return areas that cover this exact point. "
            "Provide as {latitude: number, longitude: number}."
        ),
    )
    overlappingArea: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Return areas whose geography overlaps this shape. "
            "Format: {areaType: 'CIRCLE', center: {latitude, longitude}, radius: N} "
            "or {areaType: 'POLYGON', boundary: [{latitude, longitude}, ...]}."
        ),
    )
    coveringArea: Optional[Dict[str, Any]] = Field(
        None,
        description=(
            "Return areas that fully contain this shape. Same format as overlappingArea."
        ),
    )
    byName: Optional[str] = Field(None, description="Filter by exact area name.")
    byNetworkProfileId: Optional[str] = Field(
        None, description="Return areas that support this network profile UUID."
    )
    byQosProfileName: Optional[str] = Field(
        None, description="Return areas that support this QoS profile name."
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' or 'json'.",
    )


class GetAreaInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    areaId: str = Field(..., description="UUID of the service area to retrieve.")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' or 'json'.",
    )


class PickLocationInput(BaseModel):
    """All fields optional. Powers the ui://camara/area-picker map view."""
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    latitude: Optional[float] = Field(
        None, ge=-90, le=90,
        description="Initial map center latitude. Omit to let the map fit all areas.",
    )
    longitude: Optional[float] = Field(
        None, ge=-180, le=180,
        description="Initial map center longitude. Omit to let the map fit all areas.",
    )
    zoom: Optional[int] = Field(
        None, ge=0, le=22,
        description="Initial map zoom level (0-22). Omit to let the map fit all areas.",
    )
    byNetworkProfileId: Optional[str] = Field(
        None, description="Only show areas that support this network profile UUID.",
    )
    byQosProfileName: Optional[str] = Field(
        None, description="Only show areas that support this QoS profile name.",
    )


# ═════════════════════════════════════════════════════════════════════════════
# NETWORKS  (API 1)
# ═════════════════════════════════════════════════════════════════════════════

class ListNetworksInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' or 'json'.",
    )


class GetNetworkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    networkId: str = Field(..., description="UUID of the dedicated network.")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' or 'json'.",
    )


class CreateNetworkInput(BaseModel):
    """Exactly ONE of networkProfileId or qosProfileName must be provided."""
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    serviceAreaId: str = Field(
        ...,
        description=(
            "UUID of the geographic service area where the network will run. "
            "Use camara_retrieve_service_areas to find valid IDs."
        ),
    )
    serviceTime: ServiceTimeInput = Field(
        ...,
        description="Start and end times for the network service window.",
    )
    networkProfileId: Optional[str] = Field(
        None,
        description=(
            "UUID of the network profile (mutually exclusive with qosProfileName). "
            "Supports multiple devices and multiple QoS profiles. "
            "Use camara_list_profiles to find valid IDs."
        ),
    )
    qosProfileName: Optional[str] = Field(
        None,
        description=(
            "QoS profile name — simplified option for a single-device network "
            "(mutually exclusive with networkProfileId)."
        ),
    )
    sink: Optional[str] = Field(
        None,
        pattern=r"^https://.*",
        description="HTTPS URL to receive network lifecycle event notifications.",
    )
    sinkCredential: Optional[SinkCredentialInput] = Field(
        None,
        description="Credentials for authenticating to the notification sink.",
    )

    def model_post_init(self, __context: Any) -> None:
        """Enforce the oneOf constraint: exactly one of the two profile fields."""
        has_profile = self.networkProfileId is not None
        has_qos     = self.qosProfileName is not None
        if has_profile == has_qos:
            raise ValueError(
                "Provide exactly one of 'networkProfileId' or 'qosProfileName', not both and not neither."
            )


class DeleteNetworkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    networkId: str = Field(..., description="UUID of the dedicated network to delete.")


# ═════════════════════════════════════════════════════════════════════════════
# ACCESSES  (API 3)
# ═════════════════════════════════════════════════════════════════════════════

class ListAccessesInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    networkId: Optional[str] = Field(
        None,
        description="Filter accesses for a specific network UUID. Omit to return all.",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' or 'json'.",
    )


class GetAccessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accessId: str = Field(..., description="UUID of the device access grant.")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="'markdown' or 'json'.",
    )


class CreateAccessInput(BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    networkId: str = Field(
        ...,
        description=(
            "UUID of the dedicated network to grant the device access to. "
            "Obtain via camara_create_network or camara_list_networks."
        ),
    )
    device: Optional[DeviceInput] = Field(
        None,
        description=(
            "Device identifier. REQUIRED with a two-legged access token. "
            "MUST be omitted with a three-legged token (device is derived from the token). "
            "Provide at least one of: phoneNumber, ipv4Address, ipv6Address."
        ),
    )
    qosProfiles: Optional[List[str]] = Field(
        None,
        min_length=1,
        description=(
            "Allowed QoS profiles for this device (subset of the network's supported profiles). "
            "Omit to allow all profiles the network supports."
        ),
    )
    defaultQosProfile: Optional[str] = Field(
        None,
        description=(
            "Default QoS profile for this device. "
            "Omit to use the network profile's default."
        ),
    )
    sink: Optional[str] = Field(
        None,
        pattern=r"^https://.*",
        description="HTTPS notification callback URL for device access lifecycle events.",
    )
    sinkCredential: Optional[SinkCredentialInput] = Field(
        None,
        description="Credentials for the notification sink.",
    )


class DeleteAccessInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accessId: str = Field(..., description="UUID of the device access grant to delete.")
