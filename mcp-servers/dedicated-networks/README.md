# CAMARA Dedicated Networks — MCP Server (Python)

A Python MCP server that lets Claude Desktop call the four CAMARA Dedicated Networks APIs directly.

---

## API versions

This server was built against the following CAMARA API definitions (OpenAPI `3.0.3`):

| API | Title | API version | Path version | Commonalities |
|-----|-------|-------------|--------------|---------------|
| Networks | `Dedicated Network - Networks` | `wip` | `v0` | `0.6` |
| Network Profiles | `Dedicated Network - Network Profiles` | `wip` | `v0` | `0.6` |
| Device Accesses | `Dedicated Network - Accesses` | `wip` | `v0` | `0.6` |
| Service Areas | `Dedicated Network - Areas` | `wip` | `v0` | `0.6` |

> `wip` ("work in progress") is the version label carried in the CAMARA source specs at the time this server was built. As the CAMARA APIs stabilise into numbered releases, update the tool implementations accordingly.

---

## Concepts

| Term | Description |
|---|---|
| **Network** | A reserved slice of radio resources, tied to a geographic area and a time window. |
| **Profile** | A blueprint describing what a network can deliver (device limit, throughput, QoS options). |
| **Access** | A grant allowing a specific device to connect to a network. |
| **Service Area** | A geographic region with consistent dedicated-network coverage. |
| **serviceAreaId** | UUID from `camara_retrieve_service_areas` — required to create a network. |
| **networkProfileId** | UUID from `camara_list_profiles` — one of two ways to configure a network. |
| **qosProfileName** | String name — simplified alternative to a profile UUID (single-device networks only). |

### Network lifecycle

```
REQUESTED → RESERVED → ACTIVATED → TERMINATED
              (future)   (live)      (ended)
```

### Access lifecycle

```
REQUESTED → GRANTED
           REJECTED
```

---

## Tools

This server exposes **12 tools** across four functional groups. Service areas come with a
GeoJSON URL for viewing them on a map. (A 13th tool, `camara_pick_location`, an interactive
map, is temporarily disabled.)

| Tool | Group | What it does |
|------|-------|-------------|
| `camara_list_profiles` | Profiles | List available network profiles |
| `camara_get_profile` | Profiles | Get details of a specific profile |
| `camara_retrieve_service_areas` | Areas | Search geographic service areas (with GeoJSON URLs) |
| `camara_get_area` | Areas | Get details of a specific service area (with GeoJSON URL) |
| `camara_list_networks` | Networks | List all your dedicated networks |
| `camara_get_network` | Networks | Get status/details of one network |
| `camara_create_network` | Networks | Create a new dedicated network |
| `camara_delete_network` | Networks | Cancel/delete a network |
| `camara_list_accesses` | Accesses | List device access grants |
| `camara_get_access` | Accesses | Check if a device access is granted/denied |
| `camara_create_access` | Accesses | Grant a device access to a network |
| `camara_delete_access` | Accesses | Revoke a device's access |

---

## Requirements

- **Python 3.10 or newer**
- **pip** (Python's package manager)
- **Node.js 20+ and npm** — *optional*; only needed to build the
  `camara_pick_location` map view if you re-enable it (currently disabled)

---

## Installation

### 1. Open a terminal / Command Prompt

On Windows: press `Win + R`, type `cmd`, press Enter.

### 2. Install the dependencies

```bash
cd path\to\camara-dedicated-networks-mcp-python
pip install -r requirements.txt
```

This installs three packages:
- `mcp[cli]` — the MCP framework (registers tools for Claude)
- `httpx` — the async HTTP client (makes API calls)
- `pydantic` — validates the inputs Claude sends to each tool

### 3. Build the map view (optional — map picker currently disabled)

Only needed if you re-enable the map picker (`ENABLE_MAP_PICKER = True` in
`server.py`); skip it otherwise.

```bash
cd ui/area-picker
npm install
npm run build
cd ../..
```

Details in [Interactive Map Picker](#interactive-map-picker-mcp-apps--temporarily-disabled).

### 4. Test that it runs

```bash
python server.py
```

You should see a line like:
```
[camara-mcp] Starting | API root: http://localhost:9091 | Auth: NO TOKEN
```
(Press Ctrl+C to stop.)

---

## Configure Claude Desktop

Open your Claude Desktop config file:

- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
  (paste `%APPDATA%\Claude\claude_desktop_config.json` into the Explorer address bar)
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add the following block inside `"mcpServers"` (create the file if it does not exist):

```json
{
  "mcpServers": {
    "camara-dedicated-networks": {
      "command": "python",
      "args": [
        "C:\\path\\to\\camara-dedicated-networks-mcp-python\\server.py"
      ],
      "env": {
        "CAMARA_API_ROOT": "https://your-api-server.example.com",
        "CAMARA_ACCESS_TOKEN": "your-bearer-token-here"
      }
    }
  }
}
```

> **Replace** `CAMARA_API_ROOT` with the real URL of your CAMARA API server.
> **Replace** `CAMARA_ACCESS_TOKEN` with your bearer token.

Then **restart Claude Desktop**.

---

## Configure OpenCode

[OpenCode](https://opencode.ai) reads MCP server definitions from an `opencode.json` (or `opencode.jsonc`) config file:

- **Project-level**: `opencode.json` in your project root (highest precedence).
- **Global**: `~/.config/opencode/opencode.json`.

Add the following block (create the file if it does not exist):

```json
{
  "mcp": {
    "camara-dedicated-networks": {
      "type": "local",
      "command": [
        "python",
        "C:\\path\\to\\camara-dedicated-networks-mcp-python\\server.py"
      ],
      "enabled": true,
      "environment": {
        "CAMARA_API_ROOT": "https://your-api-server.example.com",
        "CAMARA_ACCESS_TOKEN": "your-bearer-token-here"
      }
    }
  }
}
```

> **Replace** `CAMARA_API_ROOT` with the real URL of your CAMARA API server.
> **Replace** `CAMARA_ACCESS_TOKEN` with your bearer token.
> On macOS/Linux, use a forward-slash path (e.g. `/path/to/camara-dedicated-networks-mcp-python/server.py`) and, if needed, point `command` at your `python3` binary.

Restart OpenCode (or run `opencode` again) to pick up the new server. Tools then become available with the `camara-dedicated-networks_` prefix, e.g. `camara-dedicated-networks_camara_list_profiles`.

---

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CAMARA_API_ROOT` | Base URL of your CAMARA API server | `http://localhost:9091` |
| `CAMARA_ACCESS_TOKEN` | Bearer token for authentication | *(empty — no auth header sent)* |
| `CAMARA_MAP_TILE_URL` | XYZ tile URL template for the `camara_pick_location` map (only used if the map picker is re-enabled) | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` |

---

## Example prompts

```
What network profiles are available?
```
```
Find service areas near latitude 50.74, longitude 7.10
```
```
Create a dedicated network using profile <id> in area <id> from 2025-06-01T09:00:00Z to 2025-06-01T17:00:00Z
```
```
List all my dedicated networks and show their status
```
```
Grant phone number +1234567890 access to network <networkId>
```
```
Is access <accessId> granted yet?
```

---

## Tool reference

### Group 1 — Networks

#### `camara_list_networks`

Lists all dedicated networks belonging to the caller.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `response_format` | `markdown` \| `json` | No | Output format. Default: `markdown`. |

**Returns** — Each network contains `id`, `status`, `serviceAreaId`, `serviceTime`, `networkProfileId` or `qosProfileName`, and `sink`.

---

#### `camara_get_network`

Fetches the current state of a single network by UUID.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `networkId` | string (UUID) | Yes | ID of the network to inspect. |
| `response_format` | `markdown` \| `json` | No | Output format. Default: `markdown`. |

**Errors** — `404` Network not found.

---

#### `camara_create_network`

Creates a new dedicated network reservation. Starts in `REQUESTED` status.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `serviceAreaId` | string (UUID) | Yes | Target geographic area (from `camara_retrieve_service_areas`). |
| `serviceTime` | `{ start, end }` | Yes | RFC 3339 timestamps with timezone offset. |
| `networkProfileId` | string (UUID) | Exclusive* | Profile UUID (from `camara_list_profiles`). |
| `qosProfileName` | string | Exclusive* | QoS profile name — simplified, single-device option. |
| `sink` | string (HTTPS URL) | No | Webhook for status-change notifications. |
| `sinkCredential` | object | No | Auth credentials for the webhook. |
| `response_format` | `markdown` \| `json` | No | Output format. Default: `markdown`. |

*Provide **exactly one** of `networkProfileId` or `qosProfileName`.

**Returns** — Created network object including its new `networkId`.

**Errors** — `400` Invalid input (bad timestamps, bad UUID, or both/neither profile fields provided).

---

#### `camara_delete_network`

Cancels a network reservation. Irreversible. Delete all device accesses first.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `networkId` | string (UUID) | Yes | ID of the network to cancel. |

**Errors** — `404` Network not found.

---

### Group 2 — Profiles

Profiles are read-only resources managed by the CSP.

#### `camara_list_profiles`

Lists all network profiles available to the caller.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `name` | string | No | Exact profile name to filter by. |
| `response_format` | `markdown` \| `json` | No | Output format. Default: `markdown`. |

**Returns** — Each profile contains `id`, `name`, `maxNumberOfDevices`, throughput budgets, `qosProfiles`, and `defaultQosProfile`.

---

#### `camara_get_profile`

Fetches full details of a single network profile by UUID.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `profileId` | string (UUID) | Yes | UUID of the profile. |
| `response_format` | `markdown` \| `json` | No | Output format. Default: `markdown`. |

**Errors** — `404` Profile not found.

---

### Group 3 — Accesses

An access grant ties a device to a network and controls which QoS profiles that device may use.

#### `camara_list_accesses`

Lists device access grants, optionally scoped to a specific network.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `networkId` | string (UUID) | No | Filter to a specific network. Omit to return all accesses. |
| `response_format` | `markdown` \| `json` | No | Output format. Default: `markdown`. |

**Returns** — Each access contains `id`, `status`, `networkId`, `device`, `defaultQosProfile`, `qosProfiles`, and `sink`.

---

#### `camara_get_access`

Fetches the current state of a single access grant by UUID.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `accessId` | string (UUID) | Yes | UUID of the access grant. |
| `response_format` | `markdown` \| `json` | No | Output format. Default: `markdown`. |

**Returns** — Full access object including `statusInfo` (reason code if `REJECTED`).

**Errors** — `404` Access not found.

---

#### `camara_create_access`

Grants a device access to a dedicated network.

**Token type determines how the device is identified:**

| Token type | `device` field |
|---|---|
| 2-legged | **Required** — provide `phoneNumber`, `ipv4Address`, or `ipv6Address`. |
| 3-legged | **Must be omitted** — device is derived from the token. |

| Parameter | Type | Required | Description |
|---|---|---|---|
| `networkId` | string (UUID) | Yes | Target network. |
| `device` | object | Conditional | Device identifier (see above). |
| `qosProfiles` | list of strings | No | Allowed QoS profiles for this device. Omit to allow all. |
| `defaultQosProfile` | string | No | Default QoS profile for this device. |
| `sink` | string (HTTPS URL) | No | Webhook for status-change notifications. |
| `sinkCredential` | object | No | Auth credentials for the webhook. |

**Returns** — Created access object with its `accessId`.

**Errors** — `400` Invalid device identifier. `404` Network not found. `422` Device identifier rule violated.

---

#### `camara_delete_access`

Revokes a device's access grant. Irreversible.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `accessId` | string (UUID) | Yes | UUID of the access grant to revoke. |

**Errors** — `404` Access not found.

---

### Group 4 — Service Areas

Service areas are read-only geographic regions defined by the CSP.

#### `camara_retrieve_service_areas`

Searches for service areas using geographic and/or profile filters. All filters are optional and AND-combined.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `atLocation` | `{ latitude, longitude }` | No | A point that must be covered by the area. |
| `overlappingArea` | `{ areaType: 'CIRCLE'\|'POLYGON', … }` | No | Shape that must overlap the area. |
| `coveringArea` | `{ areaType: 'CIRCLE'\|'POLYGON', … }` | No | Shape that the area must fully contain. |
| `byName` | string | No | Exact area name. |
| `byNetworkProfileId` | string (UUID) | No | Only areas supporting this network profile. |
| `byQosProfileName` | string | No | Only areas supporting this QoS profile name. |
| `response_format` | `markdown` \| `json` | No | Output format. Default: `markdown`. |

**Returns** — Each area contains `id`, `name`, `description`, `area` geometry, `networkProfiles`, and `qosProfiles`, plus a geojson.io URL to view it (see [Visualizing service areas](#visualizing-service-areas-geojson)).

---

#### `camara_get_area`

Fetches the full details of a single service area by UUID.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `areaId` | string (UUID) | Yes | UUID of the service area. |
| `response_format` | `markdown` \| `json` | No | Output format. Default: `markdown`. |

**Errors** — `404` Area not found.

---

#### `camara_pick_location` (temporarily disabled)

> **Disabled:** this tool is not registered while `ENABLE_MAP_PICKER = False`
> in `server.py`. Use the GeoJSON URLs returned by the area tools instead
> (see [Visualizing service areas](#visualizing-service-areas-geojson)).

Opens an interactive map (see [Interactive Map Picker](#interactive-map-picker-mcp-apps)
below) so the user can point at a location instead of typing coordinates.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `latitude` | number | No | Initial map center latitude. Omit to fit all areas. |
| `longitude` | number | No | Initial map center longitude. Omit to fit all areas. |
| `zoom` | integer (0-22) | No | Initial map zoom level. Omit to fit all areas. |
| `byNetworkProfileId` | string (UUID) | No | Only show areas supporting this network profile. |
| `byQosProfileName` | string | No | Only show areas supporting this QoS profile name. |

Returns JSON with `areas`, a computed `bounds` bounding box, `tileUrl`, and
`center`/`zoom` (only echoed back if the caller passed them). The chosen
location and `serviceAreaId` arrive later as a follow-up user message once
the user confirms a selection on the map — this tool does not return them
directly.

---

## Visualizing service areas (GeoJSON)

Every time a service area is returned, the server also generates a
[geojson.io](https://geojson.io) URL that draws it on a map — no local build or
map hosting needed. The GeoJSON is embedded in the URL itself.

| Tool | Where the URL appears |
|---|---|
| `camara_get_area` | Markdown: `GeoJSON map: [View area](…)` line. JSON: `geojsonUrl` field on the area. |
| `camara_retrieve_service_areas` | Markdown: one link per area. JSON: `geojsonUrl` on each area, plus a top-level `geojsonUrl` showing **all** returned areas together. |

Notes:
- GeoJSON has no circle type, so `CIRCLE` areas are approximated by a 64-point polygon.
- Areas with missing or malformed geometry get no URL.
- Areas with many vertices produce long URLs (the whole GeoJSON is in the link).

---

## Interactive Map Picker (MCP Apps) — temporarily disabled

> **Status:** disabled because the map does not yet work as required. The code
> (`camara/ui.py`, `camara/tools/picker.py`, `ui/`) is kept intact. To re-enable
> it, set `ENABLE_MAP_PICKER = True` in `server.py`; the tool count then goes
> from 12 back to 13. Building the view (below) is only needed in that case.

`camara_pick_location` opens an interactive Leaflet map inside the chat (via
the [MCP Apps](https://modelcontextprotocol.io/specification/draft/extensions/apps)
extension, `io.modelcontextprotocol/ui`) so the user can point at a location
instead of typing coordinates:

1. The map opens showing every available service area, dimmed.
2. Clicking a point calls `camara_retrieve_service_areas` (with `atLocation`)
   and highlights the areas covering it, in a side panel ordered from the
   smallest (most specific) to the largest.
3. An optional "draw a circle" mode (checkbox above the panel) lets the user
   click-and-drag instead, querying with `overlappingArea` rather than
   `atLocation`.
4. Clicking "Usar esta área" sends the chosen coordinates, `serviceAreaId`,
   name, and available profiles back into the conversation — continue from
   there with `camara_list_profiles` and `camara_create_network`.

### Building the view

The map is a small Vite + Leaflet project at `ui/area-picker/`, bundled with
[`vite-plugin-singlefile`](https://github.com/richardtallent/vite-plugin-singlefile)
into one self-contained HTML file (Leaflet and the MCP Apps client SDK
inlined, no CDN). **It must be built before starting the server**, or
`camara_pick_location`'s map resource will fail to read:

```bash
cd ui/area-picker
npm install
npm run build
```

This writes `ui/dist/area_picker.html`, which `camara/ui.py` serves as the
`ui://camara/area-picker` resource. If you don't rebuild after editing
`ui/area-picker/src/`, the server keeps serving the previous build — there's
no watch step wired into `python server.py`.

`ui/dist/` is **not** committed (it's covered by the root `.gitignore`'s
`dist/` rule) — it's a regenerated build artifact, and Leaflet + the MCP Apps
SDK bundled in make it a few hundred KB, not worth tracking in git.

### Tile server

Map tiles come from `CAMARA_MAP_TILE_URL` (see
[Environment variables](#environment-variables)), an XYZ template like
`https://tile.openstreetmap.org/{z}/{x}/{y}.png`. Its hostname is the only
external origin the view's Content-Security-Policy allows — tiles load as
`<img>` sources, so it's declared under the resource's `resourceDomains`
(not `connectDomains`).

### Known issue

There's an open upstream issue (`ext-apps` #671) about MCP Apps UIs not
rendering in Claude Desktop for Windows when going through the `mcp-remote`
proxy. If the tool runs but no map appears, try connecting directly instead
of through `mcp-remote` before assuming the view itself is broken.

---

## Recommended workflow

### Pre-conditions (operator side)

Before calling the API, the following should already be in place:
- The API invoker has signed up with the API provider.
- QoS Profiles, Network Profiles, and Service Areas have been defined by the operator.

### Phase 1 — Before using the network

| Step | Tool | What to do |
|------|------|-----------|
| 1.1a | `camara_list_profiles` | Discover available profiles — save the `id` that fits your requirements. |
| 1.1b | `camara_retrieve_service_areas` | Find a service area covering your location — save its `id`. |
| 1.2 | `camara_create_network` | Reserve a network with `profileId`, `serviceAreaId`, and `serviceTime`. |
| 1.3 | `camara_get_network` | Monitor status: `REQUESTED → RESERVED → ACTIVATED`. |
| 1.4 | `camara_create_access` | Grant a device access using the returned `networkId`. |

### Phase 2 — During operation

| Step | Tool | What to do |
|------|------|-----------|
| 2.1 | `camara_get_network` | Confirm status is `ACTIVATED`. |
| 2.2 | `camara_create_access` / `camara_delete_access` | Add or remove devices dynamically. |
| 2.3 | `camara_get_access` | Check device access status: `REQUESTED → GRANTED / REJECTED`. |

### Phase 3 — Dismantling

| Step | Tool | What to do |
|------|------|-----------|
| 3.1 | `camara_delete_access` | Revoke each device access. |
| 3.2 | `camara_delete_network` | Cancel the network reservation. |

> **Tip:** The server also exposes four **prompts** for interactive guidance:
> `dedicated_network_workflow`, `discover_profiles_and_areas`, `manage_device_access`, `teardown_network`.

---

## Understanding the code

```
server.py                   Entry point — creates the FastMCP instance and
                            registers all tool groups and prompts.
camara/
  config.py                 Reads CAMARA_API_ROOT and CAMARA_ACCESS_TOKEN
                            from environment variables.
  client.py                 Shared async HTTP client (_api_request, _handle_error).
  models.py                 Pydantic input models shared across tools.
  formatters.py             Turns API JSON responses into readable Markdown.
  geo.py                    Geometry helpers: bounding boxes and GeoJSON /
                            geojson.io URL generation for service areas.
  ui.py, tools/picker.py    Interactive map picker (currently disabled).
  prompts.py                Registers the four workflow guidance prompts.
  tools/
    networks.py             camara_list_networks, camara_get_network,
                            camara_create_network, camara_delete_network
    profiles.py             camara_list_profiles, camara_get_profile
    accesses.py             camara_list_accesses, camara_get_access,
                            camara_create_access, camara_delete_access
    areas.py                camara_retrieve_service_areas, camara_get_area
docs/
  dedicated-network.yaml              OpenAPI spec — Networks API
  dedicated-network-profiles.yaml     OpenAPI spec — Network Profiles API
  dedicated-network-accesses.yaml     OpenAPI spec — Device Accesses API
  dedicated-network-areas.yaml        OpenAPI spec — Service Areas API
```

Each tool follows the same pattern:
1. A **Pydantic model** validates what Claude passes in
2. The `@mcp.tool` decorator registers it with the MCP server
3. The function body calls `_api_request()` and formats the result
4. Errors are caught and turned into readable messages by `_handle_error()`

All tools accept `response_format: 'json'` to retrieve raw API payloads instead of formatted Markdown.

---

## Acknowledgement

This work has been performed in the framework of the AGENTIC6G: AUTONOMOUS MULTI-AGENT AGENTIC AI SYSTEM FOR 6G NETWORKS project (Grant Agreement No. 101290342), funded by the Smart Networks and Services Joint Undertaking (SNS JU) under the European Union's Horizon Europe research and innovation programme.

The SNS JU receives support from the European Union's Horizon Europe research and innovation programme and the SNS JU members (public and private).

Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or the SNS JU. Neither the European Union nor the granting authority can be held responsible for them.
