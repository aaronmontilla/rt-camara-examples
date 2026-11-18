"""
camara/plain.py
───────────────
Baseline modes for evaluation, approximating a wrapper generated directly
from the CAMARA OpenAPI specifications (release r2.2: Networks, Network
Profiles and Device Accesses 0.2.0-rc.1, Service Areas 0.1.0-rc.1, the
versions the gateway follows).

CAMARA_CONTRACT=plain (default: full)
  - each tool's description is the `summary` of its OpenAPI operation (not
    the longer operation `description`), and each parameter's description is
    the one in the specification, verbatim;
  - the input schemas keep names and types, and carry the constraints of the
    specification (formats, lengths, patterns, ranges, item counts, a device
    needing a phone number, the circle and polygon area shapes); the
    gateway's own texts, pydantic titles and the response_format option are
    removed;
  - each tool returns the API's JSON response as it came (or the bare HTTP
    status for an empty response), before the gateway formats anything: no
    Markdown, no next steps, no map links;
  - a one-line server instruction and no workflow prompts;
  - a cross-field check of the gateway (exactly one of networkProfileId and
    qosProfileName) answers with a neutral validation message, as a schema
    validator would, not with advice. The rule is not in the input schema:
    the Claude API rejects oneOf/allOf/anyOf at the top level of a tool's
    input schema, so a generated wrapper would have to leave it out too.

  The constraints are declared to the model, as in a generated wrapper; the
  gateway's own argument checks are unchanged and the API validates the rest.

  Differences from the specification, all shared with the full contract:
  the paging (perPage, page), the network-name filter, the optional network
  `name` on creation and the x-device header are not exposed; an access is
  created for one `device` (the specification takes a `devices` list of 1 to
  100); sinkCredential keeps the gateway's flat shape (no run uses it). After
  a DELETE resent on a fresh connection is answered 404, the first one is
  taken as executed and "HTTP 204 No Content" is returned.

CAMARA_ERRORS=raw (default: raw with the plain contract, translated otherwise)
  - a failed call returns the HTTP status and the API's error body as they
    came (the body cut at 2000 characters), or the exception, instead of a
    message naming cause and remedy.
    It is still an MCP tool error, so hosts and the testbed see the failure.

The tools themselves (one per operation), argument validation and the API
client are the same in every mode, so only the contract the model reads and
the texts it gets back change. Every tool makes one API call; in plain mode
camara/client.py raises RawResult with its response, which camara/flat.py
returns as the tool's text.
"""

import json
from typing import Any, Dict, Iterable

from camara import config

# Operation summaries, verbatim from the CAMARA r2.2 OpenAPI files.
PLAIN_SUMMARIES: Dict[str, str] = {
    "camara_list_networks": "Get a paged list of dedicated networks",
    "camara_get_network": "Get the current information about a dedicated network",
    "camara_create_network": "Request to create a dedicated network",
    "camara_delete_network": "Delete a dedicated network",
    "camara_list_profiles": "Read dedicated network profiles",
    "camara_get_profile": "Read a dedicated network profile",
    "camara_list_accesses": ("Get a paged list of accesses to dedicated networks, optionally filtered "
                             "for a given device and/or for a given dedicated network"),
    "camara_get_access": "Read access information",
    "camara_create_access": ("Create an access to a dedicated network with given configuration, "
                             "optionally including devices"),
    "camara_delete_access": "Delete an access",
    "camara_retrieve_service_areas": "Retrieve network service areas, filtered by additional search criteria",
    "camara_get_area": "Read a network service area",
    "camara_pick_location": "Retrieve network service areas, filtered by additional search criteria",
}

# ── specification texts and constraints (verbatim) ────────────────────────────
_RFC3339 = ("It must follow [RFC 3339](https://datatracker.ietf.org/doc/html/rfc3339#section-5.6) and must "
            "have time zone. Recommended format is yyyy-MM-dd'T'HH:mm:ss.SSSZ (i.e. which allows "
            "2023-07-03T14:27:08.312+02:00 or 2023-07-03T12:27:08.312Z)")
_TIME = {"description": _RFC3339, "format": "date-time", "maxLength": 64}
_QOS_NAME = {
    "description": ("A unique name for identifying a specific QoS profile.\n"
                    "This may follow different formats depending on the service providers implementation.\n"
                    "Some options addresses:\n"
                    "  - A UUID style string\n"
                    "  - Support for predefined profiles QOS_S, QOS_M, QOS_L, and QOS_E\n"
                    "  - A searchable descriptive name\n"
                    "The set of QoS Profiles that an operator is offering can be retrieved by means of the "
                    "QoS Profile API."),
    "minLength": 3, "maxLength": 256, "pattern": "^[a-zA-Z0-9_.-]+$"}
_SINK = {"description": "The address to which events shall be delivered using the selected protocol.",
         "format": "uri", "maxLength": 2048, "pattern": "^https:\\/\\/.+$"}
_SINK_CREDENTIAL = {"description": ("A sink credential provides authentication or authorization information "
                                    "necessary to enable delivery of events to a target.")}
_CREDENTIAL_TYPE = {"description": "The type of the credential - MUST be set to ACCESSTOKEN or PRIVATE_KEY_JWT for now",
                    "enum": ["ACCESSTOKEN", "PRIVATE_KEY_JWT"]}


def _uuid(description: str) -> Dict[str, Any]:
    return {"description": description, "format": "uuid", "maxLength": 36}


_IPV4 = {"description": "A single IPv4 address with no subnet mask", "format": "ipv4", "maxLength": 15}

_LATITUDE = {"description": "Latitude component of a location", "type": "number", "format": "double",
             "minimum": -90, "maximum": 90}
_LONGITUDE = {"description": "Longitude component of location", "type": "number", "format": "double",
              "minimum": -180, "maximum": 180}
_POINT = {"type": "object", "description": "Coordinates (latitude, longitude) defining a location in a map",
          "required": ["latitude", "longitude"],
          "properties": {"latitude": _LATITUDE, "longitude": _LONGITUDE}}
_AREA_TYPE_TEXT = ("Type of this area.\nCIRCLE - The area is defined as a circle.\n"
                   "POLYGON - The area is defined as a polygon.")


def _area_type(value: str) -> Dict[str, Any]:
    return {"type": "string", "enum": [value], "description": _AREA_TYPE_TEXT}


# The Area schema with its two shapes, flattened from allOf; the areaType discriminator fixes each shape's type.
_AREA = {
    "description": "Base schema for all areas",
    "anyOf": [
        {"type": "object", "description": "Circular area", "required": ["areaType", "center", "radius"],
         "properties": {"areaType": _area_type("CIRCLE"), "center": _POINT,
                        "radius": {"type": "number", "description": "Distance from the center in meters",
                                   "minimum": 1}}},
        {"type": "object",
         "description": "Polygonal area. The Polygon should be a simple polygon, i.e. should not intersect itself.",
         "required": ["areaType", "boundary"],
         "properties": {"areaType": _area_type("POLYGON"),
                        "boundary": {"type": "array", "description": "List of points defining a polygon",
                                     "items": _POINT, "minItems": 3, "maxItems": 15}}},
    ],
}

_DEVICE = {
    "description": ("A device is identified by the CAMARA `device` object. Out of the four identifiers defined "
                    "by the `device` object, this API supports the Phone Number assigned by the mobile network "
                    "operator as the only option.\n"
                    "NOTE1: Phone Number is the required identifier in a `device` object for this API. Any "
                    "other identifier present in a `device` object received by this API will be silently "
                    "ignored but will be retained and echoed back.\n"
                    "NOTE2: A `device` object without a Phone Number will be rejected by this API."),
    "minProperties": 1, "required": ["phoneNumber"]}
_IPV4_DEVICE = {
    "description": (
        "The device should be identified by either the public (observed) IP address and port as seen by the "
        "application server, or the private (local) and any public (observed) IP addresses in use by the "
        "device (this information can be obtained by various means, for example from some DNS servers).\n\n"
        "If the allocated and observed IP addresses are the same (i.e. NAT is not in use) then  the same "
        "address should be specified for both publicAddress and privateAddress.\n\n"
        "If NAT64 is in use, the device should be identified by its publicAddress and publicPort, or "
        "separately by its allocated IPv6 address (field ipv6Address of the Device object)\n\n"
        "In all cases, publicAddress must be specified, along with at least one of either privateAddress or "
        "publicPort, dependent upon which is known. In general, mobile devices cannot be identified by their "
        "public IPv4 address alone."),
    "anyOf": [{"required": ["publicAddress", "privateAddress"]}, {"required": ["publicAddress", "publicPort"]}]}

# Per tool: property path -> specification keywords. "description" goes on the property; every other
# keyword constrains its value (the non-null branch of an optional property, or the schema it references).
SPEC_PROPERTIES: Dict[str, Dict[str, Dict[str, Any]]] = {
    "camara_get_network": {"networkId": _uuid("Identifier of the dedicated network")},
    "camara_delete_network": {"networkId": _uuid("Identifier of the dedicated network")},
    "camara_create_network": {
        "serviceAreaId": _uuid("Unique identifier of a network service area"),
        "networkProfileId": _uuid("Network profile id in UUID format"),
        "qosProfileName": _QOS_NAME,
        "serviceTime": {"description": "The time window during which the dedicated network shall be available"},
        "serviceTime.start": _TIME,
        "serviceTime.end": _TIME,
        "sink": _SINK,
        "sinkCredential": _SINK_CREDENTIAL,
        "sinkCredential.credentialType": _CREDENTIAL_TYPE,
    },
    "camara_list_profiles": {"name": {"description": "Only network profiles with this name are to be returned",
                                      "maxLength": 1024}},
    "camara_get_profile": {"profileId": _uuid("Identifier of the network profile")},
    "camara_list_accesses": {"networkId": _uuid("Dedicated network id")},
    "camara_get_access": {"accessId": _uuid("access identifier")},
    "camara_delete_access": {"accessId": _uuid("access identifier")},
    "camara_create_access": {
        "networkId": _uuid("Network id in UUID format"),
        "qosProfiles": {"description": ("(Optional) List of supported QOS profiles usable for the device(s). "
                                        "When absent, all QosProfiles of the network are supported. Only a "
                                        "subset of the QOS profiles of the network is allowed"),
                        "minItems": 1, "maxItems": 32},
        "qosProfiles[]": _QOS_NAME,
        "defaultQosProfile": _QOS_NAME,
        "device": _DEVICE,
        "device.phoneNumber": {
            "description": ("A public identifier addressing a telephone subscription. In mobile networks it "
                            "corresponds to the MSISDN (Mobile Station International Subscriber Directory "
                            "Number). In order to be globally unique it has to be formatted in international "
                            "format, according to E.164 standard, prefixed with '+'."),
            "pattern": "^\\+[1-9][0-9]{4,14}$", "maxLength": 16},
        "device.networkAccessIdentifier": {
            "description": ("A public identifier addressing a subscription in a mobile network. In 3GPP "
                            "terminology, it corresponds to the GPSI formatted with the External Identifier "
                            "({Local Identifier}@{Domain Identifier}). Unlike the telephone number, the network "
                            "access identifier is not subjected to portability ruling in force, and is "
                            "individually managed by each operator."),
            "maxLength": 2048},
        "device.ipv4Address": _IPV4_DEVICE,
        "device.ipv4Address.publicAddress": _IPV4,
        "device.ipv4Address.privateAddress": _IPV4,
        "device.ipv4Address.publicPort": {"description": "TCP or UDP port number", "format": "int32",
                                          "minimum": 1, "maximum": 65535},
        "device.ipv6Address": {
            "description": ("The device should be identified by the observed IPv6 address, or by any single "
                            "IPv6 address from within the subnet allocated to the device (e.g. adding ::0 to "
                            "the /64 prefix)."),
            "format": "ipv6", "maxLength": 45},
        "sink": _SINK,
        "sinkCredential": _SINK_CREDENTIAL,
        "sinkCredential.credentialType": _CREDENTIAL_TYPE,
    },
    "camara_retrieve_service_areas": {
        "atLocation": {"description": "Coordinates (latitude, longitude) defining a location in a map"},
        "atLocation.latitude": {"description": "Latitude component of a location", "format": "double"},
        "atLocation.longitude": {"description": "Longitude component of location", "format": "double"},
        "byName": {"description": "Only service areas with a name matching exactly this parameter are to be returned",
                   "maxLength": 1024},
        "byNetworkProfileId": _uuid("Network profile id in UUID format"),
        "byQosProfileName": _QOS_NAME,
    },
    "camara_get_area": {"areaId": _uuid("Identifier of the service area")},
}

# Properties whose schema is replaced by the specification's (the gateway models them differently).
SPEC_REPLACED: Dict[str, Dict[str, Dict[str, Any]]] = {
    "camara_retrieve_service_areas": {"overlappingArea": _AREA, "coveringArea": _AREA},
}

PLAIN_INSTRUCTIONS = "CAMARA Dedicated Networks APIs."

# Neutral text for the gateway's cross-field check, in the style of a schema validator.
ONEOF_MESSAGE = ("1 validation error: the input is not valid under exactly one of the oneOf schemas "
                 "(networkProfileId, qosProfileName)")

EMPTY = object()   # an API response with no body (HTTP 204)


class RawResult(BaseException):
    """Carries the API's response out of a tool in plain mode, before the tool formats it.

    A BaseException, so the tools' `except Exception` error handling lets it through to camara/flat.py.
    """

    def __init__(self, result: Any):
        super().__init__("raw API result")
        self.result = result


def contract_plain() -> bool:
    return config.CONTRACT == "plain"


def errors_raw() -> bool:
    return config.ERRORS == "raw"


def raw_text(result: Any) -> str:
    """The API's response as the tool's text: its JSON as it came, or the bare status for an empty body."""
    if result is EMPTY:
        return "HTTP 204 No Content"
    return json.dumps(result, indent=2, ensure_ascii=False)


def neutral_validation_message(exc: Exception) -> str:
    """The text for the failed oneOf check in plain mode: no advice, as a schema validator says it.

    Any other validation error keeps its own text.
    """
    if "networkProfileId" in str(exc) and "qosProfileName" in str(exc):
        return ONEOF_MESSAGE
    return str(exc)


# ── schema rewriting ──────────────────────────────────────────────────────────

def _strip(schema: Any) -> Any:
    """Remove description and title keywords (not properties that happen to be named so)."""
    if isinstance(schema, list):
        return [_strip(v) for v in schema]
    if not isinstance(schema, dict):
        return schema
    out = {}
    for k, v in schema.items():
        if k in ("description", "title"):
            continue
        if k in ("properties", "$defs"):
            out[k] = {name: _strip(sub) for name, sub in v.items()}
        else:
            out[k] = _strip(v)
    return out


def _value(schema: Dict[str, Any], node: Dict[str, Any]) -> Dict[str, Any]:
    """The schema a property's value must match: the non-null branch of anyOf/allOf, with local $refs followed."""
    for _ in range(10):
        ref = node.get("$ref", "")
        if ref.startswith("#/$defs/"):
            node = schema["$defs"][ref.split("/")[-1]]
            continue
        branches = [b for b in node.get("anyOf", []) + node.get("allOf", [])
                    if isinstance(b, dict) and b.get("type") != "null"]
        if len(branches) == 1 and "properties" not in node and "type" not in node:
            node = branches[0]
            continue
        return node
    raise ValueError("schema reference chain too deep")


def _find(schema: Dict[str, Any], path: str) -> Dict[str, Any]:
    """The property node at a dotted path ("a.b"; "a[]" is the items schema of array a)."""
    node = schema
    for part in path.split("."):
        items = part.endswith("[]")
        name = part[:-2] if items else part
        props = _value(schema, node).get("properties", {})
        if name not in props:
            raise KeyError(f"no property {path!r} in the tool's schema")
        node = props[name]
        if items:
            node = _value(schema, node).get("items")
            if not isinstance(node, dict):
                raise KeyError(f"{path!r} is not an array")
    return node


def _apply_spec(schema: Dict[str, Any], spec: Dict[str, Dict[str, Any]]) -> None:
    for path, keywords in spec.items():
        node = _find(schema, path)
        if "description" in keywords:
            node["description"] = keywords["description"]
        constraints = {k: v for k, v in keywords.items() if k != "description"}
        if constraints:
            _value(schema, node).update(json.loads(json.dumps(constraints)))


def _prune_defs(schema: Dict[str, Any]) -> None:
    """Drop $defs entries no longer referenced (e.g. ResponseFormat once response_format is gone)."""
    defs = schema.get("$defs")
    if not defs:
        return
    while True:
        text = json.dumps({k: v for k, v in schema.items() if k != "$defs"}) + json.dumps(defs)
        unused = [name for name in defs if f'"#/$defs/{name}"' not in text]
        if not unused:
            break
        for name in unused:
            defs.pop(name)
    if not defs:
        schema.pop("$defs")


def apply(tools: Iterable[Any]) -> None:
    """Rewrite the registered tools' contract to the plain baseline (CAMARA_CONTRACT=plain)."""
    for tool in tools:
        tool.description = PLAIN_SUMMARIES.get(tool.name, "")
        params = _strip(tool.parameters)
        params.get("properties", {}).pop("response_format", None)
        if "required" in params:
            params["required"] = [r for r in params["required"] if r != "response_format"]
        for name, replacement in SPEC_REPLACED.get(tool.name, {}).items():
            if name not in params.get("properties", {}):
                raise KeyError(f"no property {name!r} in {tool.name}")
            params["properties"][name] = json.loads(json.dumps(replacement))
        _apply_spec(params, SPEC_PROPERTIES.get(tool.name, {}))
        _prune_defs(params)
        tool.parameters = params
        if getattr(tool, "annotations", None) is not None and getattr(tool.annotations, "title", None):
            tool.annotations = tool.annotations.model_copy(update={"title": None})
