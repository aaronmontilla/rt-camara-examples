# CAMARA Dedicated Networks MCP Server (Python)

A Python MCP server that lets an AI assistant (Claude Desktop, OpenCode) call the four CAMARA Dedicated Networks APIs.

## Introduction

The server exposes the CAMARA Dedicated Networks APIs (Networks, Network Profiles, Device Accesses and Service
Areas) as **12 tools** and **4 workflow prompts** of the [Model Context Protocol](https://modelcontextprotocol.io/).
An assistant that has the server can list profiles, find service areas, reserve a dedicated network for a time window,
give a device access to it and dismantle it, from a conversation. Service areas come with a geojson.io link for viewing
them on a map.

| Term | Description |
|---|---|
| **Network** | A reserved slice of radio resources, tied to a geographic area and a time window. |
| **Profile** | A blueprint describing what a network can deliver (device limit, throughput, QoS options). |
| **Access** | A grant allowing a specific device to connect to a network. |
| **Service Area** | A geographic region with consistent dedicated-network coverage. |
| **serviceAreaId** | UUID from `camara_retrieve_service_areas`; required to create a network. |
| **networkProfileId** | UUID from `camara_list_profiles`; one of two ways to configure a network. |
| **qosProfileName** | String name; a simplified alternative to a profile UUID (single-device networks only). |

A network goes from `REQUESTED` through `RESERVED` and `ACTIVATED` to `TERMINATED`; an access goes from `REQUESTED`
to `GRANTED` or `REJECTED`.

| Tool | Group | What it does |
|------|-------|-------------|
| `camara_list_profiles` | Profiles | List available network profiles |
| `camara_get_profile` | Profiles | Get details of a specific profile |
| `camara_retrieve_service_areas` | Areas | Search geographic service areas (with GeoJSON URLs) |
| `camara_get_area` | Areas | Get details of a specific service area (with GeoJSON URL) |
| `camara_list_networks` | Networks | List all your dedicated networks |
| `camara_get_network` | Networks | Get status and details of one network |
| `camara_create_network` | Networks | Create a new dedicated network |
| `camara_delete_network` | Networks | Cancel a network |
| `camara_list_accesses` | Accesses | List device access grants |
| `camara_get_access` | Accesses | Check if a device access is granted or denied |
| `camara_create_access` | Accesses | Grant a device access to a network |
| `camara_delete_access` | Accesses | Revoke a device's access |

The parameters of each tool, the recommended order of calls, the GeoJSON links and the interactive map picker
(currently disabled) are in [docs/tool-reference.md](docs/tool-reference.md).

## Specification

Implements the four sub-APIs published in [camaraproject/DedicatedNetworks](https://github.com/camaraproject/DedicatedNetworks).
The versions and paths this server uses are listed in the [root README](../../README.md#specification).

## Install dependencies

- Python 3.10 or newer, with pip.
- Node.js 20 or newer with npm is needed only to build the map view if the map picker is re-enabled (it is disabled).

## Downloading

```bash
cd ~
git clone https://github.com/5G-MAG/rt-camara-examples.git
cd rt-camara-examples/mcp-servers/dedicated-networks
```

## Building

No build step. The map view of the disabled map picker is built as described in
[docs/tool-reference.md](docs/tool-reference.md#building-the-view).

## Installing

```bash
pip install -r requirements.txt
```

This installs `mcp[cli]` (the MCP framework), `httpx` (the HTTP client) and `pydantic` (input validation).

## Running

An MCP client starts the server itself, from the configuration below. To test that it starts, run it by hand:

```bash
python server.py
```

The server writes a line like this to standard error (standard output carries the protocol), saying whether a token is set:

```
[camara-mcp] Starting | API root: http://localhost:9091/ | Auth: NO TOKEN
```

Press Ctrl+C to stop. Example prompts to give the assistant once it is configured:

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

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CAMARA_API_ROOT` | Base URL of your CAMARA API server | `http://localhost:9091` |
| `CAMARA_ACCESS_TOKEN` | Bearer token for authentication | *(empty; no auth header sent)* |
| `CAMARA_MAP_TILE_URL` | XYZ tile URL template for the `camara_pick_location` map (only used if the map picker is re-enabled) | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` |

### Claude Desktop (Windows)

Open the Claude Desktop configuration file `%APPDATA%\Claude\claude_desktop_config.json` (paste that path into the
Explorer address bar; create the file if it does not exist) and add this block inside `"mcpServers"`:

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

Replace `CAMARA_API_ROOT` with the URL of your CAMARA API server and `CAMARA_ACCESS_TOKEN` with your bearer token, then
restart Claude Desktop.

### OpenCode

[OpenCode](https://opencode.ai) reads MCP servers from an `opencode.json` (or `opencode.jsonc`): in the project root
(highest precedence), or globally in `~/.config/opencode/opencode.json`. Add this block (create the file if it does not
exist):

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

Replace `CAMARA_API_ROOT` and `CAMARA_ACCESS_TOKEN` as above. On macOS or Linux use a forward-slash path (for example
`/path/to/rt-camara-examples/mcp-servers/dedicated-networks/server.py`) and, if needed, point `command` at your `python3`
binary. Restart OpenCode to pick up the server. Its tools then have the prefix `camara-dedicated-networks_`, for example
`camara-dedicated-networks_camara_list_profiles`.

## Development

```
server.py                   Entry point: creates the FastMCP instance and
                            registers all tool groups and prompts.
camara/
  config.py                 Reads CAMARA_API_ROOT and CAMARA_ACCESS_TOKEN
                            from environment variables.
  client.py                 Shared async HTTP client (_api_request, _handle_error).
  models.py                 Pydantic input models shared across tools.
  formatters.py             Turns API JSON responses into readable Markdown.
  geo.py                    Geometry helpers: bounding boxes and GeoJSON /
                            geojson.io URL generation for service areas, plus
                            the rule telling the assistant to show the link.
  ui.py, tools/picker.py    Interactive map picker (currently disabled).
  prompts.py                Registers the four workflow guidance prompts.
  tools/
    networks.py             camara_list_networks, camara_get_network,
                            camara_create_network, camara_delete_network
    profiles.py             camara_list_profiles, camara_get_profile
    accesses.py             camara_list_accesses, camara_get_access,
                            camara_create_access, camara_delete_access
    areas.py                camara_retrieve_service_areas, camara_get_area
```

Each tool has a Pydantic model that validates what the assistant passes in, is registered with the `@mcp.tool`
decorator, calls `_api_request()` and formats the result, and has its errors turned into readable messages by
`_handle_error()`. All tools accept `response_format: 'json'` to return the raw API payload instead of Markdown.

The test suite has 42 cases:

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Contributing

Contributions are welcome. How to raise an issue, fork the repository and open a pull request, and the Contributor
License Agreement required before code can be merged, are described at <https://www.5g-mag.com/contributing>.

## License

Distributed under the 5G-MAG Public License v1.0. See [LICENSE](../../LICENSE).

## Acknowledgement

This work has been performed in the framework of the AGENTIC6G: AUTONOMOUS MULTI-AGENT AGENTIC AI SYSTEM FOR 6G NETWORKS project (Grant Agreement No. 101290342), funded by the Smart Networks and Services Joint Undertaking (SNS JU) under the European Union's Horizon Europe research and innovation programme.

The SNS JU receives support from the European Union's Horizon Europe research and innovation programme and the SNS JU members (public and private).

Views and opinions expressed are however those of the author(s) only and do not necessarily reflect those of the European Union or the SNS JU. Neither the European Union nor the granting authority can be held responsible for them.
