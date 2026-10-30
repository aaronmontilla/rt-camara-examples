"""
camara/auth.py
──────────────
The access token sent to the CAMARA APIs.

Two ways to authenticate, chosen from the environment (see camara/config.py):
  1. CAMARA_ACCESS_TOKEN: a bearer token used as given; it is never renewed.
  2. OAuth 2.0 client credentials: CAMARA_TOKEN_URL, CAMARA_CLIENT_ID and
     CAMARA_CLIENT_SECRET (optionally CAMARA_SCOPE and CAMARA_TOKEN_AUTH).
     The token is requested when first needed, kept in memory, and renewed
     shortly before it expires or when the API rejects it with 401.
CAMARA_ACCESS_TOKEN takes precedence when both are set. With neither,
requests carry no Authorization header.

The client secret and the tokens are never written to logs or messages.
"""

import asyncio
import time
from typing import Callable, Optional

import httpx

# Renew this long before expiry (at most half of the token's lifetime).
REFRESH_MARGIN_SECONDS = 60.0
# Lifetime assumed when the token response has no expires_in.
DEFAULT_LIFETIME_SECONDS = 300.0


class TokenError(Exception):
    """The token endpoint could not provide an access token."""


class TokenProvider:
    """Supplies the bearer token for each request, renewing it when needed."""

    def __init__(
        self,
        *,
        static_token: str = "",
        token_url: str = "",
        client_id: str = "",
        client_secret: str = "",
        scope: str = "",
        auth_mode: str = "basic",
        transport: Optional[httpx.AsyncBaseTransport] = None,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._static_token = static_token
        self._token_url = token_url
        self._client_id = client_id
        self._client_secret = client_secret
        self._scope = scope
        self._send_in_body = auth_mode.strip().lower() == "body"
        self._transport = transport
        self._clock = clock
        self._token: Optional[str] = None
        self._refresh_at = 0.0
        self._lock: Optional[asyncio.Lock] = None
        self._lock_loop: Optional[asyncio.AbstractEventLoop] = None

    @classmethod
    def from_config(cls) -> "TokenProvider":
        from camara import config

        return cls(
            static_token=config.ACCESS_TOKEN,
            token_url=config.TOKEN_URL,
            client_id=config.CLIENT_ID,
            client_secret=config.CLIENT_SECRET,
            scope=config.SCOPE,
            auth_mode=config.TOKEN_AUTH,
        )

    @property
    def mode(self) -> str:
        """'static', 'client_credentials' or 'none'."""
        if self._static_token:
            return "static"
        if self._token_url and self._client_id and self._client_secret:
            return "client_credentials"
        return "none"

    @property
    def renewable(self) -> bool:
        return self.mode == "client_credentials"

    async def get_token(self) -> Optional[str]:
        """The token to send now, or None when no authentication is configured."""
        mode = self.mode
        if mode == "static":
            return self._static_token
        if mode == "none":
            return None
        if self._is_fresh():
            return self._token
        async with self._get_lock():
            if not self._is_fresh():  # another request may have renewed it meanwhile
                await self._fetch()
        return self._token

    def invalidate(self) -> None:
        """Forget the current token, so the next request fetches a new one."""
        self._token = None
        self._refresh_at = 0.0

    # ── internals ──────────────────────────────────────────────────────────────

    def _is_fresh(self) -> bool:
        return self._token is not None and self._clock() < self._refresh_at

    def _get_lock(self) -> asyncio.Lock:
        loop = asyncio.get_running_loop()
        if self._lock is None or self._lock_loop is not loop:
            self._lock = asyncio.Lock()
            self._lock_loop = loop
        return self._lock

    async def _fetch(self) -> None:
        form = {"grant_type": "client_credentials"}
        if self._scope:
            form["scope"] = self._scope
        auth = None
        if self._send_in_body:
            form["client_id"] = self._client_id
            form["client_secret"] = self._client_secret
        else:
            auth = (self._client_id, self._client_secret)

        try:
            async with httpx.AsyncClient(timeout=30.0, transport=self._transport) as client:
                response = await client.post(
                    self._token_url, data=form, auth=auth, headers={"Accept": "application/json"}
                )
        except httpx.HTTPError as e:
            raise TokenError(f"cannot reach the token endpoint ({type(e).__name__})") from e

        if response.status_code >= 400:
            raise TokenError(f"the token endpoint answered HTTP {response.status_code}{_oauth_error(response)}")
        try:
            data = response.json()
            token = data["access_token"]
        except (ValueError, KeyError, TypeError):
            raise TokenError("the token endpoint response has no access_token") from None

        try:
            lifetime = float(data.get("expires_in") or DEFAULT_LIFETIME_SECONDS)
        except (TypeError, ValueError):
            lifetime = DEFAULT_LIFETIME_SECONDS
        margin = min(REFRESH_MARGIN_SECONDS, lifetime / 2)
        self._token = token
        self._refresh_at = self._clock() + lifetime - margin


def _oauth_error(response: httpx.Response) -> str:
    """The OAuth error code and description from a token error response, if any."""
    try:
        body = response.json()
    except ValueError:
        return ""
    if not isinstance(body, dict):
        return ""
    parts = [str(body[k]) for k in ("error", "error_description") if body.get(k)]
    return f" ({': '.join(parts)})" if parts else ""
