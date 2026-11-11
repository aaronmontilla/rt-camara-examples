"""
camara/telemetry.py
───────────────────
What each tool call spent talking to the CAMARA APIs.

Every tool runs through camara.flat.flat_arguments, which starts a recording
before the tool body and returns the result with the recording in its `_meta`
field. camara/client.py and camara/auth.py add one entry per HTTP request.

The field names follow the backend telemetry that the 6G AI Traffic Testbed
reads from MCP results (as its own Spotify and Playwright servers report it).
The testbed copies backend_calls, the backend_total_* fields, backend_retries,
backend_rate_limited and token_call into each tool call's record; the whole
_meta is also kept in the payload traces (TRACE_PAYLOADS=1).

  backend_calls                  one entry per CAMARA API request: method, url,
                                 http_status, request_bytes, response_bytes,
                                 response_headers_bytes, latency_sec, attempt,
                                 new_connection, connect_sec
  backend_total_request_bytes    sums over backend_calls (API requests only;
  backend_total_response_bytes   token requests are in token_call)
  backend_total_latency_sec
  backend_retries                requests sent again after a 401 or a dropped
                                 idle connection
  backend_rate_limited           any 429
  backend_new_connections        TCP connections opened (0 when one was reused)
  backend_connect_sec            time spent opening them (TCP and TLS)
  token_call                     the OAuth token requests this call made:
                                 requests, latency_sec, bytes (summed)
  token_wait_sec                 time spent getting the token, including
                                 waiting for another call's token request
  gateway_latency_sec            the tool function, from validated arguments
                                 to the result text

gateway_latency_sec minus backend_total_latency_sec and token_wait_sec is the
time the gateway itself spent: validation, formatting, link building.

Bytes are as sent and received over HTTP: response_bytes is the body as
transferred (compressed, if the server compressed it), headers include the
request or status line. TLS and TCP overhead are not counted. The token and
the client secret never appear here.
"""

import contextvars
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import httpx


@dataclass
class Recording:
    calls: List[Dict[str, Any]] = field(default_factory=list)
    token_calls: List[Dict[str, Any]] = field(default_factory=list)
    token_wait: float = 0.0
    started: float = field(default_factory=time.perf_counter)


_current: contextvars.ContextVar[Optional[Recording]] = contextvars.ContextVar("camara_telemetry", default=None)


def start() -> contextvars.Token:
    return _current.set(Recording())


def stop(token: contextvars.Token) -> Optional[Recording]:
    recording = _current.get()
    _current.reset(token)
    return recording


def _headers_bytes(headers: httpx.Headers) -> int:
    return sum(len(k) + len(v) + 4 for k, v in headers.raw) + 2  # "name: value\r\n" ... "\r\n"


def request_bytes(request: httpx.Request) -> int:
    line = len(request.method) + len(str(request.url.raw_path, "ascii", "replace")) + 12  # "GET /x HTTP/1.1\r\n"
    return line + _headers_bytes(request.headers) + len(request.content or b"")


def response_headers_bytes(response: httpx.Response) -> int:
    status_line = len(response.http_version) + len(response.reason_phrase) + 7  # "HTTP/1.1 200 OK\r\n"
    return status_line + _headers_bytes(response.headers)


def response_body_bytes(response: httpx.Response) -> int:
    """The body as transferred (before decompression), when httpx knows it."""
    transferred = getattr(response, "num_bytes_downloaded", 0)
    return transferred or len(response.content)


class ConnectionTrace:
    """httpx trace hook: did the request open a new connection, and how long did it take."""

    def __init__(self) -> None:
        self.new_connection = False
        self._connect_started: Optional[float] = None
        self.connect_sec = 0.0

    async def __call__(self, event: str, info: dict) -> None:
        if event == "connection.connect_tcp.started":
            self.new_connection = True
            self._connect_started = time.perf_counter()
        elif event in ("connection.connect_tcp.complete", "connection.start_tls.complete"):
            if self._connect_started is not None:
                self.connect_sec = time.perf_counter() - self._connect_started


def record_call(response: Optional[httpx.Response], request: httpx.Request, latency: float,
                attempt: int, trace: ConnectionTrace, error: Optional[str] = None) -> None:
    recording = _current.get()
    if recording is None:
        return
    entry: Dict[str, Any] = {
        "method": request.method,
        "url": str(request.url),
        "http_status": response.status_code if response is not None else None,
        "request_bytes": request_bytes(request),
        "response_bytes": response_body_bytes(response) if response is not None else 0,
        "response_headers_bytes": response_headers_bytes(response) if response is not None else 0,
        "latency_sec": round(latency, 4),
        "attempt": attempt,
        "new_connection": trace.new_connection,
        "connect_sec": round(trace.connect_sec, 4),
    }
    if response is not None and response.status_code == 429:
        entry["rate_limited"] = True
    if error:
        entry["error"] = error
    recording.calls.append(entry)


def record_token_call(response: Optional[httpx.Response], url: str, latency: float,
                      error: Optional[str] = None) -> None:
    recording = _current.get()
    if recording is None:
        return
    entry: Dict[str, Any] = {
        "url": url,
        "http_status": response.status_code if response is not None else None,
        "request_bytes": request_bytes(response.request) if response is not None else 0,
        "response_bytes": response_body_bytes(response) if response is not None else 0,
        "latency_sec": round(latency, 4),
    }
    if error:
        entry["error"] = error
    recording.token_calls.append(entry)


def add_token_wait(seconds: float) -> None:
    recording = _current.get()
    if recording is not None:
        recording.token_wait += seconds


def meta(recording: Optional[Recording]) -> Dict[str, Any]:
    """The `_meta` of a tool result."""
    if recording is None:
        return {}
    calls = recording.calls
    out: Dict[str, Any] = {
        "gateway_latency_sec": round(time.perf_counter() - recording.started, 4),
        "token_wait_sec": round(recording.token_wait, 4),
    }
    if calls:
        out.update({
            "backend_calls": calls,
            "backend_total_request_bytes": sum(c["request_bytes"] for c in calls),
            "backend_total_response_bytes": sum(c["response_bytes"] for c in calls),
            "backend_total_latency_sec": round(sum(c["latency_sec"] for c in calls), 4),
            "backend_retries": sum(1 for c in calls if c["attempt"] > 1),
            "backend_rate_limited": any(c.get("rate_limited") for c in calls),
            "backend_new_connections": sum(1 for c in calls if c["new_connection"]),
            "backend_connect_sec": round(sum(c["connect_sec"] for c in calls), 4),
        })
    tokens = recording.token_calls
    if tokens:
        last = tokens[-1]
        out["token_call"] = {
            "url": last["url"],
            "http_status": last["http_status"],
            "requests": len(tokens),
            "request_bytes": sum(t["request_bytes"] for t in tokens),
            "response_bytes": sum(t["response_bytes"] for t in tokens),
            "latency_sec": round(sum(t["latency_sec"] for t in tokens), 4),
        }
        if any(t.get("error") for t in tokens):
            out["token_call"]["error"] = next(t["error"] for t in tokens if t.get("error"))
    return out
