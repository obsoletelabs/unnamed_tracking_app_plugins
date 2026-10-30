"""Jellyfin sign-in: a fake server with the real status codes, plus an opt-in live check.

The fake mirrors what a real Jellyfin 10.10 to 12.4 answers (checked against live servers):
one access token per (user, DeviceId) so a new sign-in under the same DeviceId revokes the
previous token, 401 for every refused sign-in, 400 without a MediaBrowser Authorization header,
and 404 for a Quick Connect secret that is unknown or older than five minutes.
"""

import importlib.util
import json
import os
import re
import types
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest

SOURCE = Path(__file__).parents[1] / "official/jellyfin-media-sync"
USER = str(uuid4())
REMOTE = "a" * 32
PASSWORD = "disposable-fixture-password"


def context(user=USER, **values):
    return {"_plugin_context": {"user_id": user, "is_admin": False}, **values}


def admin(**values):
    return {"_plugin_context": {"user_id": USER, "is_admin": True}, **values}


class FakeJellyfin:
    """Just enough of Jellyfin's HTTP API, answering like the host's outbound adapter."""

    def __init__(self, clock):
        self.clock = clock
        self.quick_enabled = True
        self.tokens = {}  # token -> user id
        self.device_token = {}  # (user id, device id) -> token
        self.secrets = {}  # secret -> {"code", "authorized", "created"}
        self.requests = []
        self.sign_in_devices = []
        self.failures = {}  # path -> host-shaped failure

    def authorize(self, code):
        for entry in self.secrets.values():
            if entry["code"] == code:
                entry["authorized"] = True

    def _issue(self, device):
        self.sign_in_devices.append(device)
        old = self.device_token.pop((REMOTE, device), None)
        self.tokens.pop(old, None)
        token = uuid4().hex
        self.tokens[token], self.device_token[(REMOTE, device)] = REMOTE, token
        return {"User": {"Id": REMOTE, "Name": "fixture-user"}, "AccessToken": token}

    def valid(self, token):
        return token in self.tokens

    def __call__(self, payload):
        url = urlsplit(payload["url"])
        method, path = payload.get("method", "GET"), url.path
        self.requests.append((method, path))
        header = payload["headers"].get("Authorization", "")
        fields = dict(re.findall(r'(\w+)="([^"]*)"', header))
        if path in self.failures:
            return self.failures[path]
        if not header.startswith("MediaBrowser ") or not fields.get("DeviceId"):
            return {"status": 400, "error": "Remote server rejected the request."}
        if path == "/QuickConnect/Enabled":
            return {"status": 200, "data": self.quick_enabled}
        if path == "/QuickConnect/Initiate":
            if not self.quick_enabled:
                return {"status": 401, "error": "Remote server rejected the request."}
            secret = uuid4().hex
            code = str(100000 + len(self.secrets))
            self.secrets[secret] = {
                "code": code,
                "authorized": False,
                "created": self.clock[0],
            }
            return {"status": 200, "data": {"Secret": secret, "Code": code}}
        if path == "/QuickConnect/Connect":
            entry = self.secrets.get(parse_qs(url.query).get("secret", [""])[0])
            if not entry or self.clock[0] - entry["created"] > 300:
                return {"status": 404, "error": "Remote server rejected the request."}
            return {"status": 200, "data": {"Authenticated": entry["authorized"]}}
        if path == "/Users/AuthenticateWithQuickConnect":
            secret = payload["body"]["Secret"]
            entry = self.secrets.get(secret)
            if not entry or not entry["authorized"]:
                return {"status": 401, "error": "Remote server rejected the request."}
            del self.secrets[secret]
            return {"status": 200, "data": self._issue(fields["DeviceId"])}
        if path == "/Users/AuthenticateByName":
            if payload["body"] != {"Username": "fixture-user", "Pw": PASSWORD}:
                return {"status": 401, "error": "Remote server rejected the request."}
            return {"status": 200, "data": self._issue(fields["DeviceId"])}
        if path == "/System/Info/Public":
            return {"status": 200, "data": {"Version": "12.4.0", "Id": "fixture"}}
        if path.startswith("/Users/" + REMOTE + "/Items"):
            if not self.valid(fields.get("Token")):
                return {"status": 401, "error": "Remote server rejected the request."}
            return {"status": 200, "data": {"Items": [], "TotalRecordCount": 0}}
        return {"status": 404, "error": "Remote server rejected the request."}


@pytest.fixture
def world(monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE))
    modules = {}
    for name in ("jellyfin", "plugin", "attention", "sync"):
        spec = importlib.util.spec_from_file_location(name, SOURCE / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(__import__("sys").modules, name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    clock = [1_000_000.0]
    jellyfin = FakeJellyfin(clock)
    storage, denied = {}, set()

    def gateway(method, capability, payload):
        if capability in denied:
            raise RuntimeError("A denial may contain remote diagnostics SECRET")
        if method == "storage.get":
            return {"value": storage.get(payload["key"])}
        if method == "storage.put":
            storage[payload["key"]] = payload["value"]
            return {}
        if method == "storage.delete":
            storage.pop(payload["key"], None)
            return {}
        if method == "storage.keys":
            return {
                "keys": sorted(k for k in storage if k.startswith(payload["prefix"]))
            }
        if method == "network.request":
            return jellyfin(payload)
        return {}

    for module in modules.values():
        monkeypatch.setattr(module, "request", gateway, raising=False)
    plugin, lib = modules["plugin"], modules["jellyfin"]
    monkeypatch.setattr(
        plugin,
        "time",
        types.SimpleNamespace(time=lambda: clock[0], sleep=lambda _: None),
    )
    server = plugin.save_server(admin(url="https://jf.test", name="Fixture"))["server_id"]
    return types.SimpleNamespace(
        gateway=gateway,
        plugin=plugin,
        lib=lib,
        jellyfin=jellyfin,
        storage=storage,
        denied=denied,
        clock=clock,
        server=server,
    )


def sign_in(w, **values):
    return w.plugin.login(
        context(server_id=w.server, username="fixture-user", password=PASSWORD, **values)
    )


def quick_connect(w, **values):
    started = w.plugin.quick_connect_start(context(server_id=w.server, **values))
    assert started["ok"] and started["state"] == "pending"
    w.jellyfin.authorize(started["code"])
    return started, w.plugin.quick_connect_finish(
        context(pending_id=started["pending_id"])
    )


def works(w, account_id):
    """Would a sync with the stored credential be accepted by Jellyfin?"""
    plugin = w.plugin
    account = plugin.account_by_id(USER, account_id)
    token = plugin.account_token(USER, account, plugin.server_by_id(w.server))
    try:
        w.lib.api(
            plugin.server_by_id(w.server), token, "/Users/" + REMOTE + "/Items"
        )
    except w.lib.SyncError as exc:
        assert exc.code == "authentication" and exc.status == 401
        return False
    return True


def test_each_connection_signs_in_under_its_own_device_so_tokens_survive(world):
    """Regression: a shared DeviceId made every new sign-in revoke the earlier token."""
    w = world
    password = sign_in(w)["account_id"]
    _, quick = quick_connect(w)
    second_password = sign_in(w)["account_id"]
    assert quick["ok"] and quick["state"] == "authorized"
    accounts = [password, quick["account_id"], second_password]
    assert len(set(accounts)) == 3
    assert all(works(w, account) for account in accounts)
    assert len(set(w.jellyfin.sign_in_devices)) == 3
    assert "utp-jellyfin" not in w.jellyfin.sign_in_devices


def test_reconnecting_replaces_only_that_accounts_token(world):
    w = world
    first, second = sign_in(w)["account_id"], sign_in(w)["account_id"]
    before = w.plugin.load("secrets/accounts/" + USER + "/" + first)["token"]
    sign_in(w, account_id=first)
    after = w.plugin.load("secrets/accounts/" + USER + "/" + first)["token"]
    assert before != after and works(w, first) and works(w, second)
    _, again = quick_connect(w, account_id=first)
    assert again["account_id"] == first and works(w, first) and works(w, second)


def test_credentials_saved_before_per_device_sign_in_keep_working(world):
    w = world
    legacy = w.jellyfin._issue("utp-jellyfin")
    account = "b" * 32
    w.plugin.store(
        "accounts/" + USER + "/" + account,
        {"id": account, "server_id": w.server, "remote_user_id": REMOTE,
         "name": "fixture-user", "auth": "login", "enabled": True, "revision": 1},
    )
    w.plugin.store(
        "secrets/accounts/" + USER + "/" + account,
        {"token": legacy["AccessToken"], "url": "https://jf.test"},
    )
    assert works(w, account)
    # A request that was waiting for approval before the update still completes.
    started = w.plugin.quick_connect_start(context(server_id=w.server))
    key = "secrets/quick/" + USER + "/" + started["pending_id"]
    pending = w.plugin.load(key)
    del pending["device_id"], pending["identity"]
    w.plugin.store(key, pending)
    w.jellyfin.authorize(started["code"])
    done = w.plugin.quick_connect_finish(context(pending_id=started["pending_id"]))
    assert done["ok"] and works(w, done["account_id"])


@pytest.mark.parametrize("handler", ["login", "quick_connect_start"])
def test_refused_sign_in_is_returned_not_raised(world, handler):
    """The host shows only the text of a returned result, never an exception's text."""
    w = world
    values = context(server_id=w.server, username="fixture-user", password="wrong")
    if handler == "quick_connect_start":
        w.jellyfin.quick_enabled = False
        values = context(server_id=w.server)
    result = getattr(w.plugin, handler)(values)
    assert result["ok"] is False and result["state"] == "error"
    assert result["code"] in {"authentication", "configuration"}
    assert result["retryable"] is False
    if handler == "login":
        assert "username or password" in result["message"]
    else:
        assert "Quick Connect is disabled" in result["message"]
    assert not [k for k in w.storage if k.startswith("secrets/accounts/")]


def test_unreachable_server_and_host_denial_are_retryable_results(world):
    w = world
    w.jellyfin.failures["/Users/AuthenticateByName"] = {
        "status": 0, "code": "unreachable", "error": "Cannot reach the remote server"}
    result = sign_in(w)
    assert result["ok"] is False and result["retryable"] is True
    w.jellyfin.failures.clear()
    w.denied.add("network.outbound")
    result = w.plugin.quick_connect_start(context(server_id=w.server))
    assert result["ok"] is False and result["retryable"] is True
    assert "SECRET" not in json.dumps(result)


def test_gateway_timeouts_are_transient(world):
    w = world
    w.jellyfin.failures["/System/Info/Public"] = {"status": 408, "error": "x"}
    with pytest.raises(w.lib.SyncError) as caught:
        w.lib.api(w.plugin.server_by_id(w.server), None, "/System/Info/Public")
    assert caught.value.code == "transient" and caught.value.status == 408


def test_rejected_saved_token_names_the_fix(world):
    w = world
    account = sign_in(w)["account_id"]
    sign_in(w, account_id=account)
    old = w.plugin.load("secrets/accounts/" + USER + "/" + account)
    w.jellyfin.tokens.pop(old["token"])
    server = w.plugin.server_by_id(w.server)
    with pytest.raises(w.lib.SyncError, match="Reconnect the account") as caught:
        w.lib.api(server, old["token"], "/Users/" + REMOTE + "/Items")
    assert caught.value.code == "authentication"


def test_quick_connect_poll_states(world):
    w = world
    started = w.plugin.quick_connect_start(context(server_id=w.server))
    assert started["expires_in"] == 300 and started["poll_seconds"] == 2
    assert "secret" not in json.dumps(started).lower()
    waiting = w.plugin.quick_connect_finish(context(pending_id=started["pending_id"]))
    assert waiting["state"] == "pending" and waiting["pending"] and not waiting["ok"]
    w.clock[0] += 100
    assert w.plugin.quick_connect_finish(
        context(pending_id=started["pending_id"]))["expires_in"] == 200
    w.jellyfin.authorize(started["code"])
    done = w.plugin.quick_connect_finish(context(pending_id=started["pending_id"]))
    assert done["ok"] and done["state"] == "authorized" and works(w, done["account_id"])
    # The spent request is gone; a late poll reports it as over instead of failing.
    late = w.plugin.quick_connect_finish(context(pending_id=started["pending_id"]))
    assert late["state"] == "expired" and late["ok"] is False


def test_quick_connect_expires_by_clock_and_by_jellyfin(world):
    w = world
    started = w.plugin.quick_connect_start(context(server_id=w.server))
    w.clock[0] += 301
    over = w.plugin.quick_connect_finish(context(pending_id=started["pending_id"]))
    assert over["state"] == "expired"
    assert not [k for k in w.storage if k.startswith("secrets/quick/")]
    # Jellyfin forgetting the secret early (404) is also an expiry, not an error.
    started = w.plugin.quick_connect_start(context(server_id=w.server))
    w.jellyfin.secrets.clear()
    assert w.plugin.quick_connect_finish(
        context(pending_id=started["pending_id"]))["state"] == "expired"


def test_quick_connect_polling_survives_a_transient_failure(world):
    w = world
    started = w.plugin.quick_connect_start(context(server_id=w.server))
    w.jellyfin.failures["/QuickConnect/Connect"] = {"status": 503, "error": "x"}
    failed = w.plugin.quick_connect_finish(context(pending_id=started["pending_id"]))
    assert failed["state"] == "error" and failed["retryable"] is True
    w.jellyfin.failures.clear()
    w.jellyfin.authorize(started["code"])
    assert w.plugin.quick_connect_finish(
        context(pending_id=started["pending_id"]))["state"] == "authorized"


def test_overlapping_checks_exchange_the_secret_once(world):
    w = world
    started = w.plugin.quick_connect_start(context(server_id=w.server))
    w.jellyfin.authorize(started["code"])
    key = "secrets/quick/" + USER + "/" + started["pending_id"]
    w.plugin.store(key, {**w.plugin.load(key), "finishing_until": w.clock[0] + 20})
    busy = w.plugin.quick_connect_finish(context(pending_id=started["pending_id"]))
    assert busy["state"] == "pending"
    assert ("POST", "/Users/AuthenticateWithQuickConnect") not in w.jellyfin.requests
    w.clock[0] += 21  # a crashed exchange does not block the request for long
    assert w.plugin.quick_connect_finish(
        context(pending_id=started["pending_id"]))["state"] == "authorized"


def test_credential_survives_a_failing_optional_host_step(world):
    w = world
    started = w.plugin.quick_connect_start(context(server_id=w.server))
    w.jellyfin.authorize(started["code"])
    w.denied.add("tasks.background")
    result = w.plugin.quick_connect_finish(context(pending_id=started["pending_id"]))
    assert result["ok"] is False and "SECRET" not in json.dumps(result)
    # Jellyfin already spent the secret; the token it issued must not be lost.
    saved = [k for k in w.storage if k.startswith("secrets/accounts/")]
    assert len(saved) == 1
    assert not [k for k in w.storage if k.startswith("secrets/quick/")]
    w.denied.clear()
    account = saved[0].rsplit("/", 1)[1]
    assert works(w, account)


def test_pending_requests_are_pruned_and_bounded(world):
    w = world
    first = w.plugin.quick_connect_start(context(server_id=w.server))
    w.clock[0] += 301
    for _ in range(14):
        w.plugin.quick_connect_start(context(server_id=w.server))
    pending = [k for k in w.storage if k.startswith("secrets/quick/")]
    assert len(pending) <= w.plugin.QUICK_CONNECT_PENDING_LIMIT
    assert "secrets/quick/" + USER + "/" + first["pending_id"] not in pending


def test_reconnect_must_belong_to_the_caller_before_any_sign_in(world):
    w = world
    mine = sign_in(w)["account_id"]
    other = str(uuid4())
    before = len(w.jellyfin.requests)
    result = w.plugin.login(
        context(user=other, server_id=w.server, username="fixture-user",
                password=PASSWORD, account_id=mine)
    )
    assert result["ok"] is False and "does not belong" in result["message"]
    assert len(w.jellyfin.requests) == before


LIVE = os.environ.get("JELLYFIN_TEST_URL")


@pytest.mark.skipif(not LIVE, reason="set JELLYFIN_TEST_URL to a disposable Jellyfin server")
def test_live_server_keeps_every_connection_valid(world, monkeypatch):
    """Run against a throwaway Jellyfin: JELLYFIN_TEST_URL, JELLYFIN_TEST_USER, JELLYFIN_TEST_PASSWORD."""
    w = world

    def live(payload):
        data = json.dumps(payload["body"]).encode() if "body" in payload else None
        headers = {"Accept": "application/json", **payload["headers"]}
        if data:
            headers["Content-Type"] = "application/json"
        call = urllib.request.Request(
            payload["url"], data=data, method=payload.get("method", "GET"), headers=headers
        )
        try:
            with urllib.request.urlopen(call, timeout=10) as response:
                raw = response.read()
                return {"status": response.status, "data": json.loads(raw) if raw else {}}
        except urllib.error.HTTPError as exc:
            return {"status": exc.code, "error": "Remote server rejected the request."}

    def gateway(method, capability, payload):
        if method == "network.request":
            return live(payload)
        return w.gateway(method, capability, payload)

    for module in (w.plugin, w.lib):
        monkeypatch.setattr(module, "request", gateway, raising=False)
    server = w.plugin.save_server(admin(url=LIVE.rstrip("/"), name="Live"))["server_id"]
    values = {
        "server_id": server,
        "username": os.environ["JELLYFIN_TEST_USER"],
        "password": os.environ["JELLYFIN_TEST_PASSWORD"],
    }
    accounts = [w.plugin.login(context(**values))["account_id"] for _ in range(3)]
    for account in accounts:
        record = w.plugin.account_by_id(USER, account)
        token = w.plugin.account_token(USER, record, w.plugin.server_by_id(server))
        assert w.lib.api(w.plugin.server_by_id(server), token, "/Users/Me")["Id"]
