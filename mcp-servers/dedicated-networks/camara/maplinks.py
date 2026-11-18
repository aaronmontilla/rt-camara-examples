"""
camara/maplinks.py
──────────────────
Short map links, resolved on demand (CAMARA_MAP_LINKS=local).

By default every service area carries a geojson.io link with the whole
geometry embedded in the URL (camara/geo.py). Those links run to thousands of
characters, and a model asked to repeat them may rewrite them: a vertex
moves, a property disappears, the end is cut. In local mode the gateway
instead returns a short link,

    http://127.0.0.1:8765/map/<areaId>          one area
    http://127.0.0.1:8765/map?ids=<id>,<id>     several areas

and serves it from a small HTTP server on the local host. Opening the link
makes the gateway fetch the area from the CAMARA API at that moment and
redirect to the same geojson.io view. Nothing is stored: the identifier
resolves to the provider's own data, as the gateway's tools do. The gateway
runs as a local process of the agent host, so the link opens in the user's
browser on that machine.

The server only listens on a loopback address and only answers requests
addressed to it by that name (Host header), so other machines, and web pages
the user visits, cannot use it as a proxy to the API. It uses its own token
provider, so it never shares asyncio state with the MCP event loop.

If the server cannot start (port taken, non-loopback host, bad port), the
gateway keeps returning embedded links, so it never hands out a dead link.

Configuration: CAMARA_MAP_LINKS (embedded | local), CAMARA_MAP_HOST
(default 127.0.0.1; loopback only), CAMARA_MAP_PORT (default 8765; 0 picks a
free port).
"""

import asyncio
import http.server
import ipaddress
import os
import re
import socket
import sys
import threading
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, quote, urlparse

import httpx

from camara import config

# Area identifiers are UUIDs in the specification; accept the same characters
# and nothing that could change the API path.
_ID = re.compile(r"[A-Za-z0-9-]{1,64}")
MAX_IDS = 20

_base_url: Optional[str] = None   # set once the server is listening
_allowed_hosts: set = set()       # Host header values the server answers
_server: Optional[http.server.ThreadingHTTPServer] = None
_provider = None                  # this module's own TokenProvider (created on first use)
_fetch_lock = threading.Lock()    # one API fetch at a time: the provider is not thread-safe


def _valid_id(value: Any) -> bool:
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def base_url() -> Optional[str]:
    """http://host:port of the running link server, or None when links are embedded."""
    return _base_url


def area_link(area_id: Any) -> Optional[str]:
    if _base_url is None or not _valid_id(area_id):
        return None
    return f"{_base_url}/map/{area_id}"


def combined_link(area_ids: List[Any]) -> Optional[str]:
    """Short link for several areas, or None (then the embedded link is used) if any id is unusable."""
    if _base_url is None or not area_ids or len(area_ids) > MAX_IDS or not all(_valid_id(i) for i in area_ids):
        return None
    return f"{_base_url}/map?ids={','.join(area_ids)}"


def _token_provider():
    global _provider
    if _provider is None:
        from camara.auth import TokenProvider

        _provider = TokenProvider.from_config()
    return _provider


def fetch_area(area_id: str) -> Dict[str, Any]:
    """GET one area from the CAMARA API (synchronous, for the link server's threads)."""
    from camara import client as client_module  # the API root and paths in use

    with _fetch_lock:
        provider = _token_provider()

        def get() -> httpx.Response:
            token = asyncio.run(provider.get_token())
            headers = {"Accept": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            url = f"{client_module.API_ROOT}{client_module.API_PATHS['areas']}/areas/{quote(area_id, safe='')}"
            return httpx.get(url, headers=headers, timeout=30.0)

        response = get()
        if response.status_code == 401 and provider.renewable:
            provider.invalidate()
            response = get()
        response.raise_for_status()
        return response.json()


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 (http.server naming)
        from camara import geo

        if self.headers.get("Host", "") not in _allowed_hosts:
            return self._text(403, "Forbidden.")
        parsed = urlparse(self.path)
        if parsed.path.startswith("/map/"):
            ids = [parsed.path[len("/map/"):]]
        elif parsed.path == "/map":
            ids = [i for i in parse_qs(parsed.query).get("ids", [""])[0].split(",") if i]
        else:
            return self._text(404, "Not found.")
        if not ids or len(ids) > MAX_IDS or not all(_valid_id(i) for i in ids):
            return self._text(400, "Bad area identifier.")
        try:
            areas = [fetch_area(i) for i in ids]
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            return self._text(404 if status == 404 else 502, f"The CAMARA API answered {status} for this area.")
        except Exception as exc:  # network failure, token failure, bad JSON
            return self._text(502, f"Could not reach the CAMARA API ({type(exc).__name__}).")
        if not all(isinstance(a, dict) and a.get("id") == i for a, i in zip(areas, ids)):
            return self._text(502, "The CAMARA API returned a different area than requested.")
        try:
            target = geo.embedded_area_url(areas[0]) if len(areas) == 1 else geo.embedded_combined_url(areas)
        except Exception:
            target = None
        if not target:
            return self._text(422, geo.GEOJSON_UNAVAILABLE_NOTE)
        self.send_response(302)
        self.send_header("Location", target)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _text(self, status: int, message: str) -> None:
        data = message.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args: Any) -> None:
        pass  # stdout carries the MCP stdio stream; keep the server quiet


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    # On Windows SO_REUSEADDR lets a second socket bind a port already in use;
    # bind exclusively there, so a taken port fails and links stay embedded.
    allow_reuse_address = os.name != "nt"

    def server_bind(self) -> None:
        if os.name == "nt" and hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _fallback(reason: str) -> None:
    global _base_url
    _base_url = None
    print(f"[camara-mcp] Map link server not started ({reason}); using embedded map links.", file=sys.stderr)


def start(host: Optional[str] = None, port: Optional[int] = None) -> Optional[str]:
    """Start the link server in a daemon thread; returns its base URL, or None if it does not start."""
    global _base_url, _server, _allowed_hosts
    host = config.MAP_HOST if host is None else host
    port = config.MAP_PORT if port is None else port
    if not _is_loopback(host):
        _fallback(f"host {host!r} is not a loopback address")
        return None
    if not isinstance(port, int) or not 0 <= port <= 65535:
        _fallback(f"port {port!r} is out of range")
        return None
    try:
        _server = _Server((host, port), _Handler)
    except (OSError, OverflowError, ValueError) as exc:
        _fallback(str(exc))
        return None
    bound_port = _server.server_address[1]
    shown = f"[{host}]" if ":" in host else host
    _base_url = f"http://{shown}:{bound_port}"
    _allowed_hosts = {f"{shown}:{bound_port}", f"localhost:{bound_port}", f"127.0.0.1:{bound_port}"}
    threading.Thread(target=_server.serve_forever, name="camara-map-links", daemon=True).start()
    return _base_url


def stop() -> None:
    """Stop the link server (tests); links go back to embedded."""
    global _base_url, _server, _allowed_hosts
    if _server is not None:
        _server.shutdown()
        _server.server_close()
    _server = None
    _base_url = None
    _allowed_hosts = set()
