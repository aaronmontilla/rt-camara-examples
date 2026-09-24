# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python MCP (Model Context Protocol) server that exposes the four CAMARA "Dedicated Networks" REST APIs as 12 tools an MCP host (e.g. Claude Desktop) can call: Networks, Profiles, Accesses, and Service Areas. It's a thin, stateless proxy — no database, no business logic beyond request/response shaping.

## Commands

```bash
pip install -r requirements.txt   # mcp[cli], httpx, pydantic
python server.py                  # run the server over stdio (for Claude Desktop / MCP Inspector)
```

There is no test suite, linter, or build step configured in this repo. To exercise a tool manually, run `python server.py` and drive it with the MCP Inspector, or point an MCP host at it via `claude_desktop_config.json` (see README.md).

Configuration is via environment variables (no config file):
- `CAMARA_API_ROOT` — base URL of the target CAMARA API server (default `http://localhost:9091`)
- `CAMARA_ACCESS_TOKEN` — bearer token; when empty, no `Authorization` header is sent

## Architecture

**Request flow:** `server.py` builds a `FastMCP` instance and calls one `register_*_tools(mcp)` function per API group. Each tool function in `camara/tools/*.py` is decorated with `@mcp.tool(...)`, takes a single Pydantic model as its argument, calls `camara.client.api_request()`, formats the result, and catches all exceptions through `camara.client.handle_error()` so tools return error strings instead of raising.

**Module responsibilities:**
- `camara/config.py` — reads `CAMARA_API_ROOT` / `CAMARA_ACCESS_TOKEN` from env; `API_PATHS` maps a short key (`networks`, `profiles`, `accesses`, `areas`) to each sub-API's base path (e.g. `dedicated-network/v0.2-wip`). Every sub-API is versioned independently.
- `camara/client.py` — the only place that calls `httpx`. `api_request(api, path, method, body, params)` builds `API_ROOT + API_PATHS[api] + path`, strips `None` query params, and returns parsed JSON (or `None` for a 204). `handle_error(e)` maps `httpx` exceptions — especially `HTTPStatusError` by status code — to human-readable strings, pulling `message`/`code` out of the CAMARA error body when present.
- `camara/models.py` — every tool's input is a Pydantic model (`extra="forbid"`), which is how argument validation happens; there is no manual validation in tool bodies. Cross-field rules live in `model_post_init` (e.g. `CreateNetworkInput` enforces exactly one of `networkProfileId` xor `qosProfileName`). All list/get tools share the `ResponseFormat` enum (`markdown` | `json`) and a `response_format` field.
- `camara/formatters.py` — pure functions (`fmt_network`, `fmt_profile`, etc.) that turn one API JSON object into a Markdown block; used only when `response_format == markdown`. When `json`, tools bypass formatters and `json.dumps` the raw payload.
- `camara/tools/{networks,profiles,accesses,areas}.py` — one `register_*_tools(mcp)` function per group, mirroring the four CAMARA sub-APIs. Each tool's docstring is the description the LLM sees, including a "Use when:" section with example phrasings — treat these docstrings as user-facing prompt content, not just documentation.
- `camara/prompts.py` — registers four MCP prompts (`dedicated_network_workflow`, `discover_profiles_and_areas`, `manage_device_access`, `teardown_network`) that give the host canned guidance for multi-step workflows.
- `docs/*.yaml` — the upstream CAMARA OpenAPI specs (one per sub-API). These are the source of truth for request/response shapes; consult them when a tool's behavior needs to match the spec exactly (status codes, field names, enum values).

**Adding a new tool:** add/extend a Pydantic input model in `models.py`, add a formatter in `formatters.py` if it returns Markdown, implement the `@mcp.tool`-decorated async function in the relevant `camara/tools/*.py` file (follow the existing try/except → `handle_error` pattern), and it's automatically registered since each file's `register_*_tools` is already called from `server.py`.

**Domain model** (see README.md for full lifecycle diagrams and the tool reference table): a **Network** is a reserved slice of radio resources tied to a `serviceAreaId` and a `serviceTime` window, configured by either a `networkProfileId` (multi-device) or a `qosProfileName` (single-device, simplified). An **Access** grants one device (`phoneNumber` / `ipv4Address` / `ipv6Address`, or implicit from a 3-legged token) permission to use a network. Networks move `REQUESTED → RESERVED → ACTIVATED → TERMINATED`; Accesses move `REQUESTED → GRANTED` or `REJECTED`.
