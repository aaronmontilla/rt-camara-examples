# CAMARA Dedicated Networks API Portal

A guided, browser-based portal for the CAMARA Dedicated Networks APIs (Areas, Networks,
Accesses and Profiles), with a one-click Quick Booking shortcut.

## Introduction

The portal walks a user through the full dedicated-network lifecycle as one guided flow
(**Areas → Network → Access → Devices**) where each stage is disabled with a one-line reason
until its prerequisite is done, and exercises the full parameter surface of its CAMARA API rather
than a cut-down subset. A **Start here** tab, shown on a first visit, follows the Dedicated Networks workflow on
[5g-mag.com](https://www.5g-mag.com/tech/network-apis/content-production/using-dedicated-networks)
(pre-conditions, before using the network, during operation, dismantling), marks who performs each
step (application provider or operator) and names the tab that does it. After the four stages,
**Shortcut: Quick Booking** covers one narrow case of tabs 1 to 3 in a single form (pick a point on the map, set a phone number and a time window, get a
network and an access in one request); both share the same state, so a network booked through the
shortcut shows up already unlocked in Devices.

- **Service areas**: search by point, drawn circle or polygon (overlapping/covering), or by
  name / network-profile / QoS-profile filters, combinable
- **Networks**: reserve by network profile *or* QoS profile, for a chosen area and time window,
  with optional callback (webhook) configuration
- **Accesses**: grant a device access to a network; the tracker always shows the three access
  states the API defines (REQUESTED, GRANTED, DENIED), highlights the current one and, for a
  denied access, shows the reason code and message
- **Devices**: create devices by phone number (MSISDN; kept in the browser, since the Accesses
  API has no device list), give one access to the current network from a drop-down, and see
  every access each device is part of, on any network
- **Live status**: adaptive polling (fast while transitioning or near expiry, slow once stable)
- **Callbacks**: status notifications sent by CAMARA arrive at the portal's webhook receiver and are
  listed in a Callbacks panel on the Network and Access tabs. A notification for the resource on
  screen refreshes its tracker at once. Sending them needs `SINK_BASE_URL` (see Configuration).
- **Dark mode**, offline-bundled map assets, no CDN dependency at runtime

The UI reuses the shared 5G-MAG reference-tools look, the same `blue-bar.css` and `style.css`
vocabulary as `rt-mbs-application-provider` / `rt-media-server` (copied, not reinvented): a
blue-bar header, `.card` / `.badge` / `.form-row` throughout, native `<dialog>` / `confirm()`,
and a single toast.

## Specification

Implements the 4 sub-APIs published in
[camaraproject/DedicatedNetworks](https://github.com/camaraproject/DedicatedNetworks):
Areas, Networks, Accesses and Profiles. It is built against the sandbox deployment, whose paths are
`dedicated-network/v0.2-wip`, `dedicated-network-accesses/v0.2-wip`,
`dedicated-network-profiles/v0.2-wip` and `dedicated-network-areas/v0.1-wip`. The sandbox differs from
the specification in two places: it rejects a `name` on a network, and it takes one device per access
(`device`, not `devices`). The versions are listed in the
[root README](../../README.md#specification).

## Install dependencies

Node.js LTS and npm; no other system packages are required.

## Downloading

```bash
cd ~
git clone https://github.com/5G-MAG/rt-camara-examples.git
cd rt-camara-examples/management-portal/DedicatedNetworks
```

## Building

No build step: plain Node.js on the backend, vanilla JS/CSS served as static files on the
frontend.

## Installing

```bash
npm install
```

## Running

```bash
cp .env.example .env
# fill in CLIENT_ID, CLIENT_SECRET, TOKEN_URL and the 4 CAMARA API base URLs
node server.js
```

Open **http://localhost:3001**.

## Configuration

All configuration is via `.env` (copied from `.env.example`); the OAuth2 credentials and CAMARA
base URLs can also be viewed and edited live from the portal's own **Config** tab.

| Variable | Description |
|----------|-------------|
| `CLIENT_ID` | OAuth2 client ID |
| `CLIENT_SECRET` | OAuth2 client secret |
| `TOKEN_URL` | OAuth2 token endpoint |
| `AREAS_URL` | Base URL for the Dedicated Network Areas API |
| `NETWORKS_URL` | Base URL for the Dedicated Network API |
| `PROFILES_URL` | Base URL for the Dedicated Network Profiles API |
| `ACCESSES_URL` | Base URL for the Dedicated Network Accesses API |
| `QOD_URL` | Base URL for the Quality on Demand API. Optional. Used by the QoS Profiles (reference) list in Areas, and by the Sessions route, which the UI does not expose. Left unset, the list shows "QOD_URL is not set" |
| `PORT` | Server port (default: 3001) |
| `SINK_BASE_URL` | Public https base URL for inbound CloudEvents notifications. The portal registers it with a bearer `sinkCredential` and answers `204`, or `401` without that credential |

For webhook notifications during local development, expose the server with a tunnel first. The portal has no
authentication, so a tunnel makes all of it, including the Config tab, reachable by anyone with the URL; use a
throwaway tunnel and stop it when done:

```bash
npx localtunnel --port 3001
# copy the tunnel URL into .env as SINK_BASE_URL and restart
```

## Development

```
management-portal/DedicatedNetworks/
  server.js                 Express entry point
  public/
    index.html              Shell: blue-bar header, tab-nav, per-tab <main> panels
    blue-bar.css             5G-MAG header component, copied verbatim from the reference tools
    style.css                 Shared 5G-MAG look (cards/badges/forms/toast/dark mode)
    js/
      app.js                  Entry point (type="module"): tabs, theme toggle, toast, health dots
      modules/
        wizard.js               Shared Guided-Setup / Quick-Booking state + tab locking
        api.js                   Fetch wrappers to /api/*
        polling.js               One adaptive-pace polling utility for every tab
        uiCommon.js               Formatting, badge helpers, lifecycle tracker
        callbackConfig.js         Shared sink/sinkCredential form fragment
        callbackLog.js            Callback list and immediate status refresh
        devicePool.js             Local device-identity pool
        stageAreas.js / stageNetwork.js / stageAccess.js / stageDevices.js
        quickBooking.js           Quick Booking tab
    lib/                     Locally bundled Leaflet + geocoder (no CDN at runtime)
  routes/                    areas.js, networks.js, accesses.js, profiles.js, config.js,
                             sessions.js (QoD, unexposed in the UI), webhooks.js
  services/                  tokenService.js (OAuth2 cache), apiService.js, webhookService.js
```

No automated test suite yet; verification has been manual/exploratory against the live sandbox.

## Contributing

Contributions are welcome. How to raise an issue, fork the repository and open a pull request,
and the Contributor License Agreement required before code can be merged, are described at
<https://www.5g-mag.com/contributing>.

## License

Distributed under the 5G-MAG Public License v1.0. See [LICENSE](../../LICENSE).
