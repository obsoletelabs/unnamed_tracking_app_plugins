"""Reference client against an in-memory host that follows the delegation v1 contract.

The live equivalent against a real instance is tools/check_integration_access.py.
"""

import hashlib
import json
import re
import stat
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "reference-clients/integration-access"
sys.path.insert(0, str(PACKAGE / "src"))

from utp_integration_client import (  # noqa: E402
    AccessDenied,
    CredentialStore,
    IntegrationError,
    MissingCapability,
    ReferenceClient,
)

ORIGIN = "https://notes.example.test"
SCOPES = {
    "profile.read": "Read profile",
    "games.read": "Read games",
    "tracking.write": "Write tracking",
}


class FakeHost:
    """Minimal contract double: ownership, policy, expiry, rotation, revocation."""

    def __init__(self):
        self.now = 1_000_000
        self.enabled, self.any_origin, self.max_hours = True, False, 336
        self.clients = {}
        self.requests, self.grants = {}, {}
        self.games = {"alice": {"a1": {"favorite": False}}, "bob": {"b1": {"favorite": False}}}
        self.legacy_keys = {"utk_legacy": "alice"}

    def approve_origin(self, origin, enabled=True):
        self.clients[origin] = {"id": str(uuid.uuid4()), "name": "x", "origin": origin, "enabled": enabled}

    def decide(self, request_id, user, scopes, hours=24, approve=True):
        request = self.requests[request_id]
        if not approve:
            request["state"] = "denied"
            return
        assert set(scopes) <= set(request["scopes"])
        assert hours is None or hours <= self.max_hours
        grant = {
            "id": str(uuid.uuid4()), "user": user, "client": request["client"],
            "scopes": sorted(scopes), "token": None, "revoked": False,
            "expires": None if hours is None else self.now + hours * 3600,
        }
        self.grants[request_id] = grant
        request["state"] = "approved"

    def transport(self, method, url, headers, body):
        path = url.split("/api/delegation/v1", 1)[1]
        data = json.loads(body) if body else {}
        bearer = headers.get("Authorization", "")[7:]
        if path == "/instance":
            return 200, {
                "instance_id": "inst-1", "enabled": self.enabled,
                "allow_any_origin": self.any_origin, "allow_legacy_api_keys": False,
                "clients": [c for c in self.clients.values() if c["enabled"]] if self.enabled else [],
                "capabilities": SCOPES,
            }
        if path == "/clients/register":
            if not (self.enabled and self.any_origin):
                return 403, {"detail": "approve origin"}
            known = self.clients.get(data["origin"])
            if known and not known["enabled"]:
                return 403, {"detail": "disabled"}
            self.approve_origin(data["origin"])
            return 201, self.clients[data["origin"]]
        if path == "/requests":
            request_id = str(uuid.uuid4())
            client = next(c for c in self.clients.values() if c["id"] == data["client_id"])
            self.requests[request_id] = {
                "client": client["id"], "scopes": data["scopes"], "state": "pending",
                "challenge": data["code_challenge"], "ttl": self.now + 600,
            }
            return 201, {"request_id": request_id, "expires_at": self.now + 600,
                         "verification_path": f"/integration-access/{request_id}",
                         "poll_interval_seconds": 5}
        match = re.fullmatch(r"/requests/([^/]+)/exchange", path)
        if match:
            request = self.requests[match[1]]
            digest = hashlib.sha256(data["verifier"].encode()).hexdigest()
            assert digest == request["challenge"]
            if request["state"] in {"pending", "denied"}:
                return 200, {"state": request["state"]}
            if request["state"] == "claimed":
                return 409, {"detail": "already exchanged"}
            grant = self.grants[match[1]]
            grant["token"] = "utd_" + uuid.uuid4().hex
            request["state"] = "claimed"
            return 200, {"state": "connected", "access_token": grant["token"],
                         "grant_id": grant["id"], "expires_at": grant["expires"],
                         "scopes": grant["scopes"]}
        return self.resource(method, path, data, bearer)

    def authenticate(self, token):
        for grant in self.grants.values():
            client_on = any(c["id"] == grant["client"] and c["enabled"] for c in self.clients.values())
            live = grant["expires"] is None or grant["expires"] > self.now
            if grant["token"] == token and not grant["revoked"] and live and client_on and self.enabled:
                return grant
        return None

    def resource(self, method, path, data, token):
        grant = self.authenticate(token) if token.startswith("utd_") else None
        if grant is None:
            return 401, {"detail": "expired, revoked or disabled"}
        if path == "/credential":
            return 200, {"scopes": grant["scopes"], "expires_at": grant["expires"]}
        if path == "/credential/rotate":
            grant["token"] = "utd_" + uuid.uuid4().hex
            return 200, {"access_token": grant["token"], "expires_at": grant["expires"],
                         "scopes": grant["scopes"]}

        def need(scope):
            return None if scope in grant["scopes"] else (403, {"detail": "not granted"})

        owned = self.games[grant["user"]]
        if path == "/profile":
            return need("profile.read") or (200, {"id": grant["user"]})
        if path.startswith("/games?"):
            return need("games.read") or (200, {"games": [{"id": g} for g in owned]})
        tracking = re.fullmatch(r"/games/([^/]+)/tracking", path)
        if tracking:
            denied = need("tracking.write")
            if denied:
                return denied
            if tracking[1] not in owned:
                return 404, {"detail": "Game not found."}
            owned[tracking[1]].update(data)
            return 200, {"id": tracking[1], **data}
        game = re.fullmatch(r"/games/([^/]+)", path)
        if game:
            denied = need("games.read")
            if denied:
                return denied
            return (200, {"id": game[1]}) if game[1] in owned else (404, {"detail": "Game not found."})
        return 404, {"detail": "unknown"}


@pytest.fixture
def host():
    fake = FakeHost()
    fake.approve_origin(ORIGIN)
    return fake


def make_client(host, origin=ORIGIN):
    return ReferenceClient("https://tracker.example.test", name="Notes", origin=origin,
                           transport=host.transport)


def connect(host, scopes, user="alice", hours=24):
    client = make_client(host)
    pending = client.request_access(scopes)
    assert client.exchange(pending) is None
    host.decide(pending.request_id, user, scopes, hours)
    return client.exchange(pending)


def test_requires_https_except_explicit_localhost(host):
    with pytest.raises(ValueError):
        ReferenceClient("http://tracker.example.test", name="n", origin=ORIGIN)
    with pytest.raises(ValueError):
        ReferenceClient("http://127.0.0.1:8000", name="n", origin=ORIGIN)
    ReferenceClient("http://127.0.0.1:8000", name="n", origin=ORIGIN, allow_insecure_localhost=True)


def test_discovery_shows_target_instance_and_request_names_identity(host):
    client = make_client(host)
    assert client.discover().instance_id == "inst-1"
    pending = client.request_access(["profile.read", "games.read"])
    assert pending.instance_id == "inst-1"
    assert pending.verification_url.startswith("https://tracker.example.test/integration-access/")
    assert pending.verifier not in pending.verification_url and pending.verifier not in repr(pending)
    assert host.requests[pending.request_id]["scopes"] == ["games.read", "profile.read"]


def test_read_only_subset_never_requests_or_gets_writes(host):
    session = connect(host, ["profile.read", "games.read"])
    assert set(session.scopes) == {"profile.read", "games.read"}
    assert session.profile() == {"id": "alice"}
    with pytest.raises(MissingCapability):
        session.update_tracking("a1", favorite=True)
    assert host.games["alice"]["a1"] == {"favorite": False}


def test_user_can_approve_a_subset_of_the_request(host):
    client = make_client(host)
    pending = client.request_access(["profile.read", "games.read"])
    host.decide(pending.request_id, "alice", ["profile.read"])
    session = client.exchange(pending)
    assert session.scopes == ["profile.read"]
    with pytest.raises(MissingCapability):
        session.games()


def test_denial_is_reported(host):
    client = make_client(host)
    pending = client.request_access(["profile.read"])
    host.decide(pending.request_id, "alice", [], approve=False)
    with pytest.raises(AccessDenied):
        client.exchange(pending)


def test_exchange_is_single_use(host):
    client = make_client(host)
    pending = client.request_access(["profile.read"])
    host.decide(pending.request_id, "alice", ["profile.read"])
    assert client.exchange(pending)
    with pytest.raises(IntegrationError) as error:
        client.exchange(pending)
    assert error.value.status == 409


def test_optional_write_is_separate_consent_and_own_data_only(host):
    session = connect(host, ["games.read", "tracking.write"])
    assert session.update_tracking("a1", favorite=True)["favorite"] is True
    with pytest.raises(IntegrationError) as error:
        session.update_tracking("b1", favorite=True)
    assert error.value.status == 404 and host.games["bob"]["b1"] == {"favorite": False}


def test_cross_user_game_ids_are_not_readable(host):
    session = connect(host, ["games.read"], user="alice")
    with pytest.raises(IntegrationError) as error:
        session.game("b1")
    assert error.value.status == 404


def test_timed_grant_expires_without_extension_and_ongoing_does_not(host):
    timed = connect(host, ["profile.read"], hours=1)
    ongoing = connect(host, ["profile.read"], hours=None)
    assert not timed.ongoing and ongoing.ongoing
    timed.rotate()
    assert timed.expires_at == host.now + 3600
    host.now += 3601
    with pytest.raises(IntegrationError) as error:
        timed.profile()
    assert error.value.status == 401
    host.now += 10 * 365 * 86400
    assert ongoing.profile()["id"] == "alice"


def test_rotation_invalidates_old_credential_and_keeps_access(host):
    session = connect(host, ["profile.read"])
    old = session.token
    session.rotate()
    assert session.token != old and session.scopes == ["profile.read"]
    stale = make_client(host)
    with pytest.raises(IntegrationError):
        stale.session_from_token(old, "inst-1")
    assert session.profile()


def test_revocation_and_disabled_client_and_disabled_integrations_block(host):
    session = connect(host, ["profile.read"], hours=None)
    host.enabled = False
    with pytest.raises(IntegrationError):
        session.profile()
    host.enabled = True
    next(iter(host.clients.values()))["enabled"] = False
    with pytest.raises(IntegrationError):
        session.profile()
    next(iter(host.clients.values()))["enabled"] = True
    assert session.profile()
    next(iter(host.grants.values()))["revoked"] = True
    with pytest.raises(IntegrationError):
        session.profile()


def test_origin_policy_permits_requests_but_never_data(host):
    unknown = make_client(host, origin="https://other.example.test")
    with pytest.raises(IntegrationError) as error:
        unknown.request_access(["profile.read"])
    assert error.value.status == 403
    host.any_origin = True
    pending = unknown.request_access(["profile.read"])
    assert unknown.exchange(pending) is None  # registered and requested: still no access
    assert all(g["token"] is None for g in host.grants.values())


def test_open_registration_cannot_reenable_a_disabled_origin(host):
    host.any_origin = True
    host.clients[ORIGIN]["enabled"] = False
    with pytest.raises(IntegrationError):
        make_client(host).request_access(["profile.read"])


def test_unsupported_or_unoffered_capabilities_are_refused_locally(host):
    client = make_client(host)
    with pytest.raises(ValueError):
        client.request_access(["admin.everything"])
    with pytest.raises(ValueError):
        client.request_access(["history.read"])  # valid but not offered by this instance


def test_legacy_api_key_is_not_a_delegated_credential(host):
    client = make_client(host)
    with pytest.raises(IntegrationError) as error:
        client.session_from_token("utk_legacy", "inst-1")
    assert error.value.status == 401


def test_credential_store_is_owner_only_and_forgets(tmp_path):
    store = CredentialStore(tmp_path / "creds.json")
    store.save("inst-1", "utd_secret", "grant-1")
    assert stat.S_IMODE((tmp_path / "creds.json").stat().st_mode) == 0o600
    assert store.load("inst-1") == {"token": "utd_secret", "grant_id": "grant-1"}
    store.forget("inst-1")
    assert store.load("inst-1") is None


def test_package_is_standalone_and_platform_neutral():
    source = "\n".join(p.read_text(encoding="utf-8") for p in (PACKAGE / "src").rglob("*.py"))
    imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", source, re.M)
    forbidden = ("src.", "sdk", "discord", "ValidationGateway")
    assert not [i for i in imports if i.startswith(forbidden)]
    assert "discord" not in source.lower()
    assert (PACKAGE / "pyproject.toml").is_file() and (PACKAGE / "README.md").is_file()
