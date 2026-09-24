"""
CAMARA Dedicated Networks — MCP Prompts
========================================
Advisory prompts that guide an AI agent through the recommended workflow
for the Dedicated Networks API.  These are *suggestions*, not hard constraints —
the caller may skip, reorder, or combine steps as their use case requires.
"""

from mcp.server.mcpserver import MCPServer as FastMCP


def register_prompts(mcp: FastMCP) -> None:  # noqa: C901

    # ── Prompt 1: Full lifecycle workflow ─────────────────────────────────────

    @mcp.prompt()
    def dedicated_network_workflow() -> str:
        """
        End-to-end advisory guide for reserving a dedicated network, connecting
        devices, and tearing it down gracefully.  All steps are *recommended*,
        not required — skip or adapt them to your use case.
        """
        return """\
# Dedicated Network — Recommended Workflow

This guide describes the typical flow for using the Dedicated Networks API.
Steps are **advisory**: skip or adapt them as your situation requires.

---

## Pre-conditions (operator side — no API calls needed)

Before using the API, the following should already be in place:
- The API invoker has signed up with the API provider.
- QoS Profiles have been defined by the network operator (via the QoS Profiles API).
- Network Profiles (with device limits and throughput budgets) have been defined by the operator.
- Dedicated Network Service Areas have been created by the operator.

---

## Phase 1 — Before using the network

### 1.1a  Discover available Network Profiles (recommended)

Use **`camara_list_profiles`** to see what capabilities the operator offers.
Each profile exposes `id`, `maxNumberOfDevices`, `aggregatedUlThroughput`,
`aggregatedDlThroughput`, and the `qosProfiles` available within it.

Keep the `id` of the profile that fits your needs — you will pass it as
`networkProfileId` when creating the network.

### 1.1b  Discover available Service Areas (recommended)

Use **`camara_retrieve_service_areas`** to find geographic zones that cover
your target location.  You can filter by:
- `atLocation` (latitude/longitude point)
- `byNetworkProfileId` (only areas supporting a specific profile)
- `byQosProfileName`, `byName`, `overlappingArea`, `coveringArea`

Keep the `id` of the matching area — you will pass it as `serviceAreaId`
when creating the network.

### 1.2  Reserve the Dedicated Network

Use **`camara_create_network`** with:
- `profileId` — the profile UUID from step 1.1a
- `serviceAreaId` — the area UUID from step 1.1b
- `serviceTime` — `{ start, end }` RFC 3339 timestamps for the reservation window
- Optionally: `sink` (webhook URL) and `sinkCredential` for status notifications

The response will include the `id` (your `networkId`) and status `REQUESTED`.

### 1.3  Monitor reservation status (recommended)

Use **`camara_get_network`** (or **`camara_list_networks`**) to track the
network as it transitions:

```
REQUESTED → RESERVED (future start time) → ACTIVATED (live) → TERMINATED
```

You may proceed to grant device access once the network exists; access grants
will be fulfilled when the network becomes ACTIVATED.

### 1.4  Grant device access

Use **`camara_create_access`** with:
- `networkId` — the network UUID from step 1.2
- `device` — phone number, IPv4/IPv6 address, or NAI (omit for 3-legged tokens)
- `qosProfiles` — subset of QoS profiles to allow for this device (optional)
- `defaultQosProfile` — which profile to use by default (optional)

The response includes the `accessId`.  The access starts in `REQUESTED`
status and moves to `GRANTED` (or `REJECTED`) once the network is active.

---

## Phase 2 — During operation

### 2.1  Verify the network is live

Use **`camara_get_network`** to confirm status is `ACTIVATED`.

### 2.2  Add or remove devices dynamically

While the network is active you can:
- **Add devices**: `camara_create_access` (as above)
- **Remove devices**: `camara_delete_access` with the relevant `accessId`

This lets you attach and detach devices without losing the reserved resources.

### 2.3  Monitor device access status

Use **`camara_get_access`** or **`camara_list_accesses`** to check whether
a device's access is `REQUESTED`, `GRANTED`, or `REJECTED`.

---

## Phase 3 — Dismantling

When you are done (or at end of service window), tear down gracefully:

1. **`camara_delete_access`** for each active device access (by `accessId`)
2. **`camara_delete_network`** to cancel the network reservation (by `networkId`)

Deleting accesses before the network ensures a clean release of reserved resources.

---

## Quick reference

| Step | Tool | Purpose |
|------|------|---------|
| 1.1a | `camara_list_profiles` | Discover network profiles |
| 1.1b | `camara_retrieve_service_areas` | Discover service areas |
| 1.2  | `camara_create_network` | Reserve the network |
| 1.3  | `camara_get_network` | Track status |
| 1.4  | `camara_create_access` | Grant device access |
| 2.2  | `camara_create_access` / `camara_delete_access` | Add/remove devices |
| 3    | `camara_delete_access` → `camara_delete_network` | Graceful teardown |
"""

    # ── Prompt 2: Pre-network discovery ───────────────────────────────────────

    @mcp.prompt()
    def discover_profiles_and_areas() -> str:
        """
        Advisory steps for discovering which Network Profiles and Service Areas
        are available before creating a dedicated network reservation.
        """
        return """\
# Discovery — Network Profiles & Service Areas

Run these lookups before creating a network.  Both steps are optional if you
already know the IDs you need.

## Step A — List Network Profiles

Call **`camara_list_profiles`** (no parameters required).

For each profile, note:
- **`id`** — the `networkProfileId` you will pass to `camara_create_network`
- **`maxNumberOfDevices`** — concurrent device limit
- **`aggregatedUlThroughput` / `aggregatedDlThroughput`** — bandwidth budget
- **`qosProfiles`** — QoS options available within this network profile
- **`defaultQosProfile`** — the QoS profile applied if a device does not specify one

Pick the profile that matches your requirements and save its `id`.

## Step B — Find a Service Area

Call **`camara_retrieve_service_areas`** with one or more filters:

| Filter | Use when |
|--------|----------|
| `atLocation: { latitude, longitude }` | You know the physical location |
| `byNetworkProfileId` | You want areas compatible with your chosen profile |
| `byQosProfileName` | You need a specific QoS capability |
| `byName` | You know the area name |
| No filters | List all available areas |

From the results, save the **`id`** of the area that covers your target location.
This becomes the `serviceAreaId` for `camara_create_network`.

## Next step

Once you have both IDs, proceed with **`camara_create_network`**.
See the `dedicated_network_workflow` prompt for the full lifecycle.
"""

    # ── Prompt 3: Device access management ────────────────────────────────────

    @mcp.prompt()
    def manage_device_access() -> str:
        """
        Advisory steps for granting, monitoring, and revoking device access
        during the active phase of a dedicated network.
        """
        return """\
# Device Access Management

This prompt covers adding and removing devices during or before network activation.
Steps are **advisory** — adapt them to your operational needs.

## Grant access to a device

Call **`camara_create_access`** with:
- **`networkId`** *(required)* — UUID of the target network
- **`device`** *(2-legged auth only)* — identify the device by one of:
  - `phoneNumber` (e.g. `+123456789`)
  - `ipv4Address: { publicAddress, publicPort }`
  - `ipv6Address`
  - `networkAccessIdentifier` (e.g. `123456789@domain.com`)
- **`qosProfiles`** *(optional)* — restrict this device to a subset of the
  network's QoS profiles.  Omit to allow all.
- **`defaultQosProfile`** *(optional)* — QoS profile applied when the device
  does not request a specific one.

The response contains the **`accessId`** — save it for status checks and deletion.
Initial status is `REQUESTED`; it moves to `GRANTED` or `REJECTED`.

> **3-legged tokens**: omit the `device` field entirely.  The device identity
> is derived from the access token.

## Check access status

Call **`camara_get_access`** with the `accessId` to see whether the grant
is `REQUESTED`, `GRANTED`, or `REJECTED`.

Call **`camara_list_accesses`** (optionally filtered by `networkId`) to see
all device grants for a network.

## Revoke device access

Call **`camara_delete_access`** with the `accessId`.

This is reversible at the network level — the device can be re-added later
with a new `camara_create_access` call without losing the dedicated resources.

## Teardown order (recommended)

When dismantling, delete accesses **before** the network:
1. `camara_delete_access` for each active `accessId`
2. `camara_delete_network` for the `networkId`
"""

    # ── Prompt 4: Graceful teardown ────────────────────────────────────────────

    @mcp.prompt()
    def teardown_network() -> str:
        """
        Advisory steps for gracefully dismantling a dedicated network and
        revoking all associated device accesses.
        """
        return """\
# Graceful Network Teardown

Follow these steps to release resources cleanly.  The order is *recommended*
but not enforced by the API.

## Step 1 — List active device accesses

Call **`camara_list_accesses`** filtered by your `networkId` to find all
current access grants.

```
camara_list_accesses(networkId="<your-network-id>")
```

Note each `accessId` with status `GRANTED` or `REQUESTED`.

## Step 2 — Delete each device access

For each `accessId`, call **`camara_delete_access`**:

```
camara_delete_access(accessId="<access-id>")
```

Repeat for every active access grant.

## Step 3 — Delete the network

Once all accesses are cleared, call **`camara_delete_network`**:

```
camara_delete_network(networkId="<your-network-id>")
```

This cancels the reservation and releases the reserved resources.

---

> **Why this order?**  Deleting accesses before the network ensures a
> controlled, auditable release.  The API does not prevent deleting the
> network first, but doing so may leave access records in an inconsistent state.
"""
