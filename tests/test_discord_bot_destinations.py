"""Per-account generic configuration and transport, independent of host internals."""
import copy
from uuid import uuid4

import pytest

from sdk.plugin_protocol import GatewayRequestError
import importlib.util
from pathlib import Path

def load():
    spec = importlib.util.spec_from_file_location('discord_bot_accounts', Path(__file__).parents[1] / 'official/discord-bot-notifications/plugin.py')
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    return plugin

OWNER = str(uuid4())
INSTALLATION = str(uuid4())
GUILD = "123456789012345678"
ACCOUNTS = {"casey": "223456789012345678", "other": "323456789012345678"}


def context(plugin, operation, *, scope="destination", revision=1, destination=None):
    authority = {"operation": operation, "scope": scope, "installation_id": INSTALLATION}
    if operation == "deliver":
        authority.update(server_revision=1, attempt_id=str(uuid4()))
    else:
        authority["provider_id"] = plugin.ACCOUNT_PROVIDER_ID
    if scope == "server":
        authority["revision"] = revision
    else:
        authority["destination"] = {"id": destination or str(uuid4()), "revision": revision, "kind": "discord_account_dm"}
    return authority


def values(authority, configuration=None, *, actor=OWNER, admin=False):
    return {"_notification_context": authority, "_plugin_context": {"user_id": actor, "is_admin": admin},
            "configuration": configuration or {}}


@pytest.fixture
def provider(monkeypatch):
    plugin = load()
    storage, sent = {}, []
    monkeypatch.setattr(plugin, "_load", lambda key, default=None: copy.deepcopy(storage.get(key, default)))
    monkeypatch.setattr(plugin, "_store", lambda key, record: storage.__setitem__(key, copy.deepcopy(record)))
    monkeypatch.setattr(plugin, "_bot_snapshot", lambda token, guild: {})
    monkeypatch.setattr(plugin, "_member_by_username", lambda token, guild, username: {"id": ACCOUNTS[username]} if username in ACCOUNTS else None)
    monkeypatch.setattr(plugin, "_send_dm", lambda token, discord_id, body: sent.append((token, discord_id, body)))
    server = context(plugin, "configure", scope="server")
    assert plugin.configure_account_destination(values(server, {"token": "per-account-token", "guild_id": GUILD}, admin=True)) == {"configured": True}
    return plugin, storage, sent


def enroll(plugin, username="casey", *, destination=None, revision=1):
    authority = context(plugin, "configure", destination=destination, revision=revision)
    result = plugin.configure_account_destination(values(authority, {"username": username}))
    assert result == {"configured": True} and "verified" not in result
    return authority


def send(plugin, authority, *, actor=OWNER, body="Your verification code is 12345678."):
    authority = {**authority, "operation": "deliver", "server_revision": 1, "attempt_id": str(uuid4())}
    authority.pop("provider_id", None)
    payload = values(authority, actor=actor)
    payload["delivery"] = {"title": "Verify destination", "body": body, "link": None}
    return plugin.deliver_account(payload)


def test_private_enrollment_requires_no_dm_or_plugin_proof_and_sends_only_one_account(provider):
    plugin, storage, sent = provider
    first, second = enroll(plugin), enroll(plugin, "other")
    assert sent == []
    assert send(plugin, first) == {"success": True, "retryable": False}
    assert sent == [("per-account-token", ACCOUNTS["casey"], "**Verify destination**\nYour verification code is 12345678.")]
    assert send(plugin, second)["success"]
    assert sent[-1][1] == ACCOUNTS["other"]
    assert not any("verified" in record or "code_hash" in record for record in storage.values())


@pytest.mark.parametrize("change", ["owner", "installation", "revision", "server", "retired", "missing", "legacy"])
def test_changed_authority_never_broadcasts_to_legacy_accounts(provider, change):
    plugin, storage, sent = provider
    authority = enroll(plugin)
    storage["links/" + OWNER] = {"accounts": [{"discord_id": account} for account in ACCOUNTS.values()]}
    storage["secrets/bot-config"] = {"token": "legacy-token", "guild_id": GUILD}
    actor = OWNER
    if change == "owner":
        actor = str(uuid4())
    elif change == "installation":
        authority["installation_id"] = str(uuid4())
    elif change == "revision":
        authority["destination"]["revision"] += 1
    elif change == "server":
        storage[plugin._account_server_key(authority)]["revision"] = 2
    elif change == "retired":
        retirement = {**authority, "operation": "retire", "destination": {**authority["destination"], "revision": 2}}
        assert plugin.retire_account_destination(values(retirement)) == {"retired": True}
    elif change == "missing":
        storage.pop(plugin._account_key(authority))
    else:
        authority["destination"]["kind"] = "discord_bot_dm"
    assert not send(plugin, authority, actor=actor)["success"]
    assert sent == []


def test_server_configuration_requires_admin_core_context_and_cannot_use_legacy_secret(provider):
    plugin, storage, sent = provider
    server = context(plugin, "configure", scope="server", revision=2)
    with pytest.raises(plugin.PluginError, match="Administrator"):
        plugin.configure_account_destination(values(server, {"guild_id": GUILD}))
    with pytest.raises(plugin.PluginError):
        plugin.configure_account_destination({"_plugin_context": {"user_id": OWNER, "is_admin": True}, "configuration": {"token": "forged"}})
    storage["secrets/bot-config"] = {"token": "changed-legacy-token", "guild_id": "423456789012345678"}
    authority = enroll(plugin)
    assert send(plugin, authority)["success"]
    assert sent[-1][0] == "per-account-token"
    storage.pop(plugin._account_server_key(server))
    assert not send(plugin, authority)["success"]
    assert len(sent) == 1


def test_retirement_tombstone_and_new_installation_cannot_reclaim_old_target(provider):
    plugin, storage, sent = provider
    authority = enroll(plugin)
    retired = {**authority, "operation": "retire", "destination": {**authority["destination"], "revision": 2}}
    plugin.retire_account_destination(values(retired))
    record = storage[plugin._account_key(authority)]
    assert record == {"revision": 2, "retired": True}
    for revision in (1, 2, 3):
        with pytest.raises(plugin.PluginError, match="stale or retired"):
            enroll(plugin, destination=authority["destination"]["id"], revision=revision)
    replacement = {**authority, "installation_id": str(uuid4())}
    with pytest.raises(plugin.PluginError, match="administrator"):
        plugin.configure_account_destination(values(replacement, {"username": "casey"}))
    assert sent == []


def test_stale_configuration_and_transport_failures_are_safe(provider, monkeypatch):
    plugin, storage, sent = provider
    authority = enroll(plugin)
    with pytest.raises(plugin.PluginError, match="stale"):
        plugin.configure_account_destination(values(authority, {"username": "other"}))
    assert storage[plugin._account_key(authority)]["discord_id"] == ACCOUNTS["casey"]
    def unavailable(*args):
        raise GatewayRequestError("secret-token and remote body must not escape", {"code": "unavailable"})
    monkeypatch.setattr(plugin, "_send_dm", unavailable)
    result = send(plugin, authority)
    assert result == {"success": False, "retryable": True, "error": "discord_gateway_failed"}
    assert "secret-token" not in str(result)


def test_provider_definition_does_not_claim_secure_trust_and_legacy_remains_private(provider):
    plugin, _, _ = provider
    choice = plugin.ACCOUNT_DEFINITION["destinations"][0]
    assert choice["privacy"] == "PRIVATE"
    assert choice["verification_supported"] and choice["sensitive_supported"] and choice["recovery_supported"]
    assert plugin.ACCOUNT_DEFINITION["features"]["multiple_destinations"]


@pytest.mark.parametrize("status", [0, 429, 500, 503])
def test_discord_transient_http_failures_enter_core_retry(provider, monkeypatch, status):
    plugin, _, _ = provider
    authority = enroll(plugin)
    monkeypatch.setattr(plugin, "request", lambda *args: {"status": status})
    def failed_send(*args):
        plugin._discord("token", "POST", "/users/@me/channels", {})
    monkeypatch.setattr(plugin, "_send_dm", failed_send)
    assert send(plugin, authority) == {"success": False, "retryable": True, "error": "discord_temporarily_unavailable"}


def test_oversized_recovery_content_is_rejected_instead_of_silently_truncated(provider):
    plugin, _, sent = provider
    authority = enroll(plugin)
    assert not send(plugin, authority, body="sensitive-content-" * 200)["success"]
    assert sent == []
