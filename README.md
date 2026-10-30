<p align="center">
  <img src=".github/banner.svg" width="100%" alt="Reference Tools · CAMARA Connectivity Quality Management APIs: CAMARA API Tools and Examples">
</p>

<p align="center">
  Example files, tools and configurations for working with <a href="https://camaraproject.org/">CAMARA</a>
  network APIs: a management portal, Insomnia collections and an MCP server.
</p>

<p align="center">
  <img alt="Status" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fwww.5g-mag.com%2Fbadges%2Fstatus%2Frt-camara-examples.json">
  <a href="https://github.com/5G-MAG/rt-camara-examples/releases"><img alt="Version"
    src="https://img.shields.io/github/v/release/5G-MAG/rt-camara-examples?label=Version"></a>
  <a href="LICENSE"><img alt="License: 5G-MAG Public License v1.0"
    src="https://img.shields.io/badge/License-5G--MAG%20PL%20v1.0-blue"></a>
</p>

<p align="center">
  <a href="https://www.5g-mag.com/reference-tools/network-apis/">Project page</a> &nbsp;&middot;&nbsp;
  <a href="https://github.com/5G-MAG/rt-camara-examples/issues">Issues</a> &nbsp;&middot;&nbsp;
  <a href="https://www.5g-mag.com/contributing">Contributing</a>
</p>

---

## At a glance

|  |  |
|---|---|
| **Implements** | [CAMARA](https://camaraproject.org/) Dedicated Networks APIs in the portal and the MCP server; Insomnia collections also cover QoS Booking and Quality on Demand |
| **Part of** | [CAMARA Connectivity Quality Management APIs](https://www.5g-mag.com/reference-tools/network-apis/) |

## Introduction

This repository holds example files, tools and configurations for working with
[CAMARA](https://camaraproject.org/) APIs, maintained by [5G-MAG](https://www.5g-mag.com/) as part
of its work on network API standardisation and adoption. It calls the CAMARA APIs as a client, in
three forms: a browser portal, an MCP server, and API collections for Insomnia. The portal and the
MCP server each have their own README with the setup instructions.

```
rt-camara-examples/
  management-portal/
    DedicatedNetworks/        Node.js portal for Dedicated Networks APIs
  insomnia/
    Insomnia_Using_DedicatedNetworks.yaml
    Insomnia_Using_QoSBooking.yaml
    Insomnia_Using_QualityonDemand.yaml
  mcp-servers/
    dedicated-networks/       Python MCP server for Dedicated Networks APIs
```

### Management portal: Dedicated Networks

A guided, browser-based portal for the CAMARA Dedicated Networks APIs (Areas, Networks, Accesses,
Profiles), with a one-click Quick Booking shortcut. What it does and how to run it are in the
[portal README](./management-portal/DedicatedNetworks/README.md).

### MCP server: Dedicated Networks

A Python [Model Context Protocol](https://modelcontextprotocol.io/) server exposing the four CAMARA Dedicated Networks APIs (Networks, Network Profiles, Device Accesses and Service Areas) as **12 tools**, plus **4 guided workflow prompts**. It lets an assistant discover profiles and service areas, reserve and monitor dedicated networks, and grant or revoke device access through natural language. Service areas are returned with a [geojson.io](https://geojson.io) link so they can be viewed on a map.
Installation, configuration and the available tools are in the [server README](./mcp-servers/dedicated-networks/README.md).

### Insomnia collections

API collections ready to import into [Insomnia](https://insomnia.rest/):

| File | APIs covered |
|------|-------------|
| [`Insomnia_Using_DedicatedNetworks.yaml`](./insomnia/Insomnia_Using_DedicatedNetworks.yaml) | Dedicated Networks, Areas, Profiles, Accesses |
| [`Insomnia_Using_QoSBooking.yaml`](./insomnia/Insomnia_Using_QoSBooking.yaml) | QoS Booking |
| [`Insomnia_Using_QualityonDemand.yaml`](./insomnia/Insomnia_Using_QualityonDemand.yaml) | Quality on Demand |

## Specification

The table lists every CAMARA API this repository calls, the path prefix the code and collections use,
and the specification revision checked for it.

| CAMARA API | Path prefix used here | Spec revision checked | Commonalities | Used by |
|---|---|---|---|---|
| Dedicated Network: Networks | `dedicated-network/v0.2-wip` | `0.2.0-rc.1` | `0.8.0` | Portal, MCP server, Insomnia |
| Dedicated Network: Network Profiles | `dedicated-network-profiles/v0.2-wip` | `0.2.0-rc.1` | `0.8.0` | Portal, MCP server, Insomnia |
| Dedicated Network: Device Accesses | `dedicated-network-accesses/v0.2-wip` | `0.2.0-rc.1` | `0.8.0` | Portal, MCP server, Insomnia |
| Dedicated Network: Service Areas | `dedicated-network-areas/v0.1-wip` | `0.1.0-rc.1` | `0.8.0` | Portal, MCP server, Insomnia |
| QoS Booking | `qos-bookings`, `device-qos-bookings` | not pinned | not pinned | Insomnia |
| Quality on Demand | `qos-assignments`, `sessions`, `retrieve-qos-profiles` | not pinned | not pinned | Portal (optional QoS profile list), Insomnia |

- The spec revisions are the CAMARA sources at tag `r2.2` of
  [camaraproject/DedicatedNetworks](https://github.com/camaraproject/DedicatedNetworks), read from each
  file's `info` block. The `main` branch is labelled `wip` and differs from `r2.2`.
- The sandbox behaves differently from the spec in two places: it rejects `name` on a network, and it
  takes one device per access (`device`, not `devices`). The code follows the sandbox.

## Install dependencies

- The management portal: Node.js LTS and npm.
- The MCP server: Python 3.10 or newer and pip.
- The Insomnia collections: [Insomnia](https://insomnia.rest/).

## Downloading

```bash
cd ~
git clone https://github.com/5G-MAG/rt-camara-examples.git
cd rt-camara-examples
```

## Building

None of the tools has a build step.

## Installing

```bash
cd management-portal/DedicatedNetworks && npm install
cd ../../mcp-servers/dedicated-networks && pip install -r requirements.txt
```

## Running

The portal, from `management-portal/DedicatedNetworks` after the configuration below:

```bash
node server.js
```

Open **http://localhost:3001**. The MCP server is started by an AI assistant from its configuration; its
[README](./mcp-servers/dedicated-networks/README.md#running) shows how to test it by hand. To use a collection, import
the file from `insomnia/` into Insomnia; the Dedicated Networks collection has a `DN Sandbox` environment to fill in.

## Configuration

Both tools call the CAMARA Dedicated Networks APIs of a server you name, and need its address and credentials: the
portal in its `.env` (client ID, client secret, token URL and the four API base URLs, copied from `.env.example`), the
MCP server in the variables `CAMARA_API_ROOT` and `CAMARA_ACCESS_TOKEN`. The Insomnia collections take the same values
in their environment. Access to the sandbox these tools are built against, and its credentials, are available to
5G-MAG members on request. Details are in the [portal README](./management-portal/DedicatedNetworks/README.md#configuration)
and the [server README](./mcp-servers/dedicated-networks/README.md#configuration).

## Development

The layout is in the tree under Introduction. The MCP server has a test suite of 42 cases
(`pip install -r requirements-dev.txt && python -m pytest` in `mcp-servers/dedicated-networks`); the portal has no
automated tests yet.

## Contributing

Contributions are welcome. How to raise an issue, fork the repository and open a pull request, and
the Contributor License Agreement required before code can be merged, are described at
<https://www.5g-mag.com/contributing>.

## License

Distributed under the 5G-MAG Public License v1.0. See [LICENSE](LICENSE). Third-party
dependencies are listed in [ATTRIBUTION_NOTICE](ATTRIBUTION_NOTICE).
