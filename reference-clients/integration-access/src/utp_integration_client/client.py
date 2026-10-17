"""Request/consent, exchange, rotation and scoped reads/writes for delegation v1."""

from __future__ import annotations

import hashlib
import json
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlsplit

API = "/api/delegation/v1"
READ_SCOPES = frozenset(
    {
        "profile.read",
        "games.read",
        "achievements.read",
        "history.read",
        "lists.read",
        "media.read",
    }
)
WRITE_SCOPES = frozenset({"tracking.write", "achievements.write", "compatibility.write"})

# (method, url, headers, body) -> (status, parsed JSON or None)
Transport = Callable[[str, str, dict[str, str], bytes | None], tuple[int, Any]]


class IntegrationError(Exception):
    """The instance rejected a request; ``status`` and ``detail`` come from the host."""

    def __init__(self, status: int, detail: str):
        super().__init__(f"{status}: {detail}")
        self.status = status
        self.detail = detail


class AccessDenied(Exception):
    """The user denied the consent request."""


class MissingCapability(Exception):
    """Raised before any network call when the grant lacks a capability."""


def urllib_transport(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> tuple[int, Any]:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
            raw, status = response.read(), response.status
    except urllib.error.HTTPError as error:
        raw, status = error.read(), error.code
    return status, (json.loads(raw) if raw else None)


@dataclass(frozen=True)
class InstanceInfo:
    """What ``GET /instance`` says: target identity, policy and approved clients."""

    base_url: str
    instance_id: str
    enabled: bool
    allow_any_origin: bool
    allow_legacy_api_keys: bool
    clients: list[dict]
    capabilities: dict[str, str]


@dataclass
class ConsentRequest:
    """A pending request. ``verifier`` is a secret and must never be placed in a URL."""

    request_id: str
    verification_url: str
    instance_id: str
    scopes: list[str]
    expires_at: int
    poll_interval: int
    verifier: str = field(repr=False)


@dataclass
class GrantSession:
    """A claimed grant. The token is the only secret; rotate it with :meth:`rotate`."""

    client: "ReferenceClient"
    instance_id: str
    grant_id: str
    scopes: list[str]
    expires_at: int | None
    token: str = field(repr=False)

    @property
    def ongoing(self) -> bool:
        return self.expires_at is None

    def has(self, scope: str) -> bool:
        return scope in self.scopes

    def _call(self, method: str, path: str, scope: str | None, body: dict | None = None):
        if scope is not None and not self.has(scope):
            raise MissingCapability(f"{scope} was not granted; request it with fresh consent.")
        return self.client._request(method, path, body, token=self.token)

    def status(self) -> dict:
        return self._call("GET", "/credential", None)

    def profile(self) -> dict:
        return self._call("GET", "/profile", "profile.read")

    def games(self, offset: int = 0, limit: int = 50) -> dict:
        return self._call("GET", f"/games?offset={offset}&limit={limit}", "games.read")

    def game(self, game_id: str) -> dict:
        return self._call("GET", f"/games/{game_id}", "games.read")

    def update_tracking(self, game_id: str, **fields: Any) -> dict:
        """Optional write; needs ``tracking.write`` consented separately."""
        return self._call("PATCH", f"/games/{game_id}/tracking", "tracking.write", fields)

    def rotate(self) -> None:
        """Replace the credential. Scopes and expiry are unchanged by the host."""
        result = self._call("POST", "/credential/rotate", None)
        self.token = result["access_token"]
        self.scopes = result["scopes"]
        self.expires_at = result["expires_at"]


class ReferenceClient:
    """An independently hosted requester identified by ``name`` and exact HTTPS ``origin``."""

    def __init__(
        self,
        base_url: str,
        *,
        name: str,
        origin: str,
        transport: Transport = urllib_transport,
        allow_insecure_localhost: bool = False,
    ):
        parts = urlsplit(base_url)
        local = parts.hostname in {"localhost", "127.0.0.1", "::1"}
        if parts.scheme != "https" and not (allow_insecure_localhost and local):
            raise ValueError("The instance URL must use HTTPS.")
        self.base_url = base_url.rstrip("/")
        self.name, self.origin = name, origin
        self._transport = transport
        self._instance: InstanceInfo | None = None

    def _request(
        self, method: str, path: str, body: dict | None = None, *, token: str | None = None
    ):
        headers = {"Accept": "application/json"}
        data = None
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        if token:
            headers["Authorization"] = f"Bearer {token}"
        status, payload = self._transport(method, self.base_url + API + path, headers, data)
        if status >= 400:
            detail = payload.get("detail") if isinstance(payload, dict) else None
            raise IntegrationError(status, str(detail or "request failed"))
        return payload

    def discover(self) -> InstanceInfo:
        raw = self._request("GET", "/instance")
        self._instance = InstanceInfo(
            self.base_url,
            raw["instance_id"],
            raw["enabled"],
            raw["allow_any_origin"],
            raw["allow_legacy_api_keys"],
            raw["clients"],
            raw["capabilities"],
        )
        return self._instance

    def client_id(self) -> str:
        """Find this origin among approved clients, or register under the open policy.

        Registration issues no credential and grants no data access.
        """
        # Policy can change at any time: always read it fresh before deciding.
        info = self.discover()
        for row in info.clients:
            if row["origin"] == self.origin:
                return row["id"]
        if not info.enabled or not info.allow_any_origin:
            raise IntegrationError(403, "The instance owner must approve this origin first.")
        body = {"name": self.name, "origin": self.origin}
        return self._request("POST", "/clients/register", body)["id"]

    def request_access(
        self,
        scopes: list[str],
        *,
        external_account: dict[str, str] | None = None,
    ) -> ConsentRequest:
        """Ask for exactly ``scopes``. Writes are requested only when listed by the caller."""
        unknown = set(scopes) - READ_SCOPES - WRITE_SCOPES
        if unknown or not scopes:
            raise ValueError(f"Unsupported capabilities: {sorted(unknown)}")
        info = self._instance or self.discover()
        unsupported = set(scopes) - info.capabilities.keys()
        if unsupported:
            raise ValueError(f"The instance does not offer: {sorted(unsupported)}")
        verifier = secrets.token_urlsafe(48)
        body: dict[str, Any] = {
            "client_id": self.client_id(),
            "scopes": sorted(set(scopes)),
            "code_challenge": hashlib.sha256(verifier.encode()).hexdigest(),
        }
        if external_account:
            body["external_account"] = external_account
        raw = self._request("POST", "/requests", body)
        return ConsentRequest(
            raw["request_id"],
            self.base_url + raw["verification_path"],
            info.instance_id,
            body["scopes"],
            raw["expires_at"],
            raw["poll_interval_seconds"],
            verifier,
        )

    def exchange(self, pending: ConsentRequest) -> GrantSession | None:
        """Poll once. ``None`` means still pending; denial raises :class:`AccessDenied`."""
        raw = self._request(
            "POST", f"/requests/{pending.request_id}/exchange", {"verifier": pending.verifier}
        )
        if raw["state"] == "pending":
            return None
        if raw["state"] == "denied":
            raise AccessDenied("The user denied this request.")
        return GrantSession(
            self,
            pending.instance_id,
            raw["grant_id"],
            raw["scopes"],
            raw["expires_at"],
            raw["access_token"],
        )

    def session_from_token(self, token: str, instance_id: str, grant_id: str = "") -> GrantSession:
        """Resume with a stored credential; scopes and expiry come from the host."""
        status = self._request("GET", "/credential", token=token)
        return GrantSession(
            self, instance_id, grant_id, status["scopes"], status["expires_at"], token
        )
