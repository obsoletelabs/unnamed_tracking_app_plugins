"""Live acceptance run of the reference integration client against a real instance.

Explicit cross-repository check, never imported by plugin payloads. It needs an
administrator and a second ordinary account on a disposable instance:

    python tools/check_integration_access.py --instance http://127.0.0.1:8000 \
        --admin admin:password --user-a alice:password --user-b bob:password

It reconfigures the instance's integration policy and creates throwaway clients and
games; run it only against a test installation. Every step prints PASS or fails.
"""

from __future__ import annotations

import argparse
import http.cookiejar
import json
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "reference-clients/integration-access/src"))

from utp_integration_client import (  # noqa: E402
    AccessDenied,
    IntegrationError,
    MissingCapability,
    ReferenceClient,
)

DELEGATION = "/api/delegation/v1"


class Browser:
    """A signed-in browser session, the only way to manage policy, consent and grants."""

    def __init__(self, base: str, credentials: str):
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )
        username, _, password = credentials.partition(":")
        self.call("POST", "/api/auth/login", {"username_or_email": username, "password": password})

    def call(self, method: str, path: str, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(
            self.base + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json", **(headers or {})},
        )
        try:
            with self.opener.open(request, timeout=20) as response:
                raw, status = response.read(), response.status
        except urllib.error.HTTPError as error:
            raw, status = error.read(), error.code
        return status, (json.loads(raw) if raw else None)

    def must(self, method: str, path: str, body=None):
        status, payload = self.call(method, path, body)
        assert status < 400, f"{method} {path} -> {status} {payload}"
        return payload


def bearer(base: str, token: str, method: str, path: str, body=None) -> int:
    status, _ = _Anonymous(base).call(
        method, path, body, {"Authorization": f"Bearer {token}"}
    )
    return status


class _Anonymous(Browser):
    def __init__(self, base: str):
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener()


def step(label: str) -> None:
    print(f"PASS  {label}")


def expect(error_type, label, function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except error_type as error:
        step(f"{label} ({error})")
        return error
    raise AssertionError(f"{label}: expected {error_type.__name__}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", required=True)
    parser.add_argument("--admin", required=True, help="username:password of an administrator")
    parser.add_argument("--user-a", required=True)
    parser.add_argument("--user-b", required=True)
    parser.add_argument("--allow-insecure-localhost", action="store_true")
    args = parser.parse_args()
    base = args.instance.rstrip("/")
    admin, alice, bob = (Browser(base, v) for v in (args.admin, args.user_a, args.user_b))

    origin = f"https://reference-{uuid.uuid4().hex[:10]}.example.test"
    policy = {
        "enabled": True,
        "allow_guests": False,
        "allow_any_origin": False,
        "allow_legacy_api_keys": False,
        "guest_retention_hours": 48,
        "maximum_grant_hours": 336,
    }
    admin.must("PUT", f"{DELEGATION}/policy", policy)

    def client() -> ReferenceClient:
        return ReferenceClient(
            base,
            name="Reference client",
            origin=origin,
            allow_insecure_localhost=args.allow_insecure_localhost,
        )

    def approve(user: Browser, pending, scopes, hours=1):
        summary = user.must("GET", f"{DELEGATION}/requests/{pending.request_id}")
        assert summary["origin"] == origin and summary["instance_id"] == pending.instance_id
        assert all(c["write"] == c["scope"].endswith(".write") for c in summary["capabilities"])
        user.must(
            "POST",
            f"{DELEGATION}/requests/{pending.request_id}/decision",
            {"approve": True, "scopes": scopes, "expires_in_hours": hours},
        )

    # Origin policy permits requests but is not consent.
    unknown = client()
    expect(IntegrationError, "unapproved origin cannot request", unknown.request_access, ["profile.read"])
    admin.must("PUT", f"{DELEGATION}/policy", {**policy, "allow_any_origin": True})
    pending = client().request_access(["profile.read"])
    assert client().exchange(pending) is None
    step("open-origin registration issues no credential; exchange stays pending until consent")
    alice.must(
        "POST", f"{DELEGATION}/requests/{pending.request_id}/decision",
        {"approve": False, "scopes": []},
    )
    expect(AccessDenied, "denial is reported", client().exchange, pending)
    admin.must("PUT", f"{DELEGATION}/policy", policy)
    clients = admin.must("GET", f"{DELEGATION}/policy")["clients"]
    entry = next(row for row in clients if row["origin"] == origin)

    # Game data for isolation checks.
    games = {}
    for label, user in (("a", alice), ("b", bob)):
        games[label] = user.must(
            "POST", "/api/game/create",
            {"title": f"Isolation {label} {uuid.uuid4().hex[:6]}", "folder_location": uuid.uuid4().hex},
        )["id"]

    # Read-only subset, timed.
    reader = client()
    pending = reader.request_access(
        ["profile.read", "games.read"],
        external_account={"provider": "example", "subject": "ref-1", "username": "reference"},
    )
    approve(alice, pending, ["profile.read", "games.read"], hours=1)
    session = reader.exchange(pending)
    assert session and not session.ongoing and session.scopes == ["games.read", "profile.read"]
    expect(IntegrationError, "exchange is one use", reader.exchange, pending)
    assert session.profile()["id"]
    assert any(g["id"] == games["a"] for g in session.games()["games"])
    assert all(g["id"] != games["b"] for g in session.games()["games"])
    step("read-only timed grant sees only the consenting user's library")
    expect(IntegrationError, "other user's game ID is not readable", session.game, games["b"])
    expect(MissingCapability, "write is blocked client-side without consent",
           session.update_tracking, games["a"], favorite=True)
    assert bearer(base, session.token, "PATCH", f"{DELEGATION}/games/{games['a']}/tracking",
                  {"favorite": True}) == 403
    step("host rejects an unconsented write")

    # Rotation keeps scopes and expiry; old credential dies.
    old, expiry = session.token, session.expires_at
    session.rotate()
    assert session.token != old and session.expires_at == expiry
    assert bearer(base, old, "GET", f"{DELEGATION}/profile") == 401
    session.profile()
    step("rotation replaces the credential without extending expiry or access")

    # Optional write needs its own consent.
    writer = client()
    pending = writer.request_access(["games.read", "tracking.write"])
    approve(bob, pending, ["games.read", "tracking.write"], hours=1)
    bob_session = writer.exchange(pending)
    assert bob_session.update_tracking(games["b"], favorite=True)["id"] == games["b"]
    expect(IntegrationError, "write to another user's game is refused",
           bob_session.update_tracking, games["a"], favorite=True)
    step("explicit write consent is limited to the consenting user's games")

    # Until revoked.
    ongoing_request = client().request_access(["profile.read"])
    alice.must("POST", f"{DELEGATION}/requests/{ongoing_request.request_id}/decision",
               {"approve": True, "scopes": ["profile.read"], "expires_in_hours": None})
    ongoing = client().exchange(ongoing_request)
    assert ongoing.ongoing and ongoing.status()["expires_at"] is None
    ongoing.rotate()
    assert ongoing.ongoing
    step("Until revoked grant has no expiry and survives rotation")

    # Reduction, revocation and disabled client.
    grants = alice.must("GET", f"{DELEGATION}/grants")
    mine = next(g for g in grants if g["id"] == session.grant_id)
    assert mine["external_account"]["username"] == "reference"
    alice.must("PATCH", f"{DELEGATION}/grants/{mine['id']}", {"scopes": ["profile.read"]})
    assert session.status()["scopes"] == ["profile.read"]
    expect(IntegrationError, "reduced grant loses games access", session.games)  # host 403
    status, _ = bob.call("DELETE", f"{DELEGATION}/grants/{mine['id']}")
    assert status == 404
    step("grants can be reduced; another user cannot revoke them")
    alice.must("DELETE", f"{DELEGATION}/grants/{mine['id']}")
    expect(IntegrationError, "revoked credential is rejected", session.profile)
    admin.must("PUT", f"{DELEGATION}/clients", {"name": "Reference client", "origin": origin, "enabled": False})
    expect(IntegrationError, "disabled client blocks existing ongoing grant", ongoing.profile)
    expect(IntegrationError, "disabled client blocks new requests", client().request_access, ["profile.read"])

    # Legacy API keys are separate and unchanged.
    key = alice.must("POST", "/api/auth/api-keys", {"name": "legacy", "scopes": ["games:read"]})["api_key"]
    assert bearer(base, key, "GET", f"{DELEGATION}/profile") == 401
    assert bearer(base, bob_session.token, "GET", "/api/game/list") in {401, 403}
    legacy = bearer(base, key, "GET", "/api/game/list")
    assert legacy == 200, legacy
    step("legacy API key keeps working but is not a delegated credential, and vice versa")
    print("All acceptance checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
