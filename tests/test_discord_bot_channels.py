"""PUBLIC bot channels use core authority and administrator policy, never DM proof."""
import copy
from uuid import uuid4

import pytest

from test_discord_bot_destinations import load, OWNER, INSTALLATION, GUILD, values
from sdk.plugin_protocol import GatewayRequestError

CHANNEL = "423456789012345678"


def authority(plugin, operation="configure", *, scope="destination", revision=1):
    context = {"operation": operation, "scope": scope, "installation_id": INSTALLATION}
    if operation == "deliver":
        context.update(server_revision=1, attempt_id=str(uuid4()))
    else:
        context["provider_id"] = plugin.CHANNEL_PROVIDER_ID
    if scope == "server":
        context["revision"] = revision
    else:
        context["destination"] = {"id": str(uuid4()), "revision": revision, "kind": "discord_bot_channel"}
    return context


@pytest.fixture
def channel(monkeypatch):
    plugin = load()
    storage, sent, calls = {}, [], []
    monkeypatch.setattr(plugin, "_load", lambda key, default=None: copy.deepcopy(storage.get(key, default)))
    monkeypatch.setattr(plugin, "_store", lambda key, record: storage.__setitem__(key, copy.deepcopy(record)))
    monkeypatch.setattr(plugin, "_bot_snapshot", lambda *args: {})
    monkeypatch.setattr(plugin, "_bot_config", lambda: {"token": "native-token", "guild_id": GUILD})
    def discord(token, method, path, body=None):
        calls.append((token, method, path, body))
        item = {"id": CHANNEL, "guild_id": GUILD, "type": 0, "name": "announcements"}
        if path == "/channels/" + CHANNEL:
            return item
        if path.endswith("/channels"):
            return [item, {"id": "523456789012345678", "type": 2, "name": "voice"}]
        if "members?" in path:
            return [{"user": {"id": "623456789012345678", "username": "casey", "token": "never-return"}, "nick": "Casey"}]
        raise AssertionError(path)
    monkeypatch.setattr(plugin, "_discord", discord)
    monkeypatch.setattr(plugin, "_send_channel", lambda *args: sent.append(args))
    plugin.allow_channels({"_plugin_context": {"user_id": OWNER, "is_admin": True}, "channel_ids": [CHANNEL]})
    server = authority(plugin, scope="server")
    plugin.configure_channel_destination(values(server, {"token": "channel-token", "guild_id": GUILD}, admin=True))
    context = authority(plugin)
    plugin.configure_channel_destination(values(context, {"channel_id": CHANNEL}))
    return plugin, storage, sent, calls, context


def deliver(plugin, context, **overrides):
    context = {**context, "operation": "deliver", "attempt_id": str(uuid4()), "server_revision": 1}
    context.pop("provider_id", None)
    payload = values(context)
    payload["delivery"] = {"title": "Public release", "body": "A release is available.", **overrides}
    return plugin.deliver_channel(payload)


def test_channel_sends_to_exact_id_and_cannot_claim_secure_or_recovery(channel):
    plugin, _, sent, _, context = channel
    assert deliver(plugin, context) == {"success": True, "retryable": False}
    assert sent == [("channel-token", CHANNEL, "**Public release**\nA release is available.")]
    declaration = plugin.CHANNEL_DEFINITION["destinations"][0]
    assert declaration["privacy"] == "PUBLIC"
    assert not any(declaration.get(key) for key in ("verification_supported", "sensitive_supported", "recovery_supported"))


@pytest.mark.parametrize("change", ["owner", "installation", "revision", "server", "removed", "retired", "dm_kind", "wrong_guild", "voice"])
def test_changed_route_or_policy_never_delivers(channel, monkeypatch, change):
    plugin, storage, sent, _, context = channel
    record = storage[plugin._channel_key(context)]
    if change == "owner":
        record["user_id"] = str(uuid4())
    elif change == "installation":
        context["installation_id"] = str(uuid4())
    elif change == "revision":
        context["destination"]["revision"] += 1
    elif change == "server":
        storage[plugin._channel_server_key(context)]["revision"] += 1
    elif change == "removed":
        storage["channel-policy/" + GUILD] = []
    elif change == "retired":
        plugin.retire_channel_destination(values({**context, "operation": "retire"}))
    elif change == "dm_kind":
        context["destination"]["kind"] = "discord_account_dm"
    else:
        monkeypatch.setattr(plugin, "_discord", lambda *args: {"id": CHANNEL, "guild_id": "wrong" if change == "wrong_guild" else GUILD, "type": 2 if change == "voice" else 0})
    assert not deliver(plugin, context)["success"]
    assert sent == []


@pytest.mark.parametrize("purpose", ["verification", "recovery", "invitation"])
def test_transactional_secrets_are_rejected(channel, purpose):
    plugin, _, sent, _, context = channel
    assert not deliver(plugin, context, purpose=purpose)["success"]
    assert sent == []


def test_admin_directory_is_scoped_and_returns_only_safe_member_fields(channel):
    plugin, _, _, _, _ = channel
    with pytest.raises(plugin.PluginError, match="Administrator"):
        plugin.list_directory({"_plugin_context": {"user_id": OWNER}})
    result = plugin.list_directory({"_plugin_context": {"user_id": OWNER, "is_admin": True}})
    assert result["channels"] == [{"id": CHANNEL, "name": "announcements"}]
    assert result["users"] == [{"id": "623456789012345678", "username": "casey", "label": "Casey"}]
    assert result["next_after"] is None
    assert "token" not in str(result)


def test_directory_cursor_and_allowlist_reject_forged_or_foreign_channels(channel):
    plugin, storage, _, _, _ = channel
    actor = {"_plugin_context": {"user_id": OWNER, "is_admin": True}}
    for ids in [["bad"], [CHANNEL, CHANNEL], ["523456789012345678"], ["723456789012345678"]]:
        with pytest.raises(plugin.PluginError):
            plugin.allow_channels({**actor, "channel_ids": ids})
    with pytest.raises(plugin.PluginError, match="cursor"):
        plugin.list_directory({**actor, "after": "../other-guild"})
    assert storage["channel-policy/" + GUILD][0]["id"] == CHANNEL


def test_user_selection_applies_only_to_new_own_destinations(channel):
    plugin, storage, _, _, original = channel
    actor = {"_plugin_context": {"user_id": OWNER}}
    plugin.select_channel({**actor, "channel_id": CHANNEL})
    choice = plugin.channel_choices(actor)
    assert choice["selected"] == CHANNEL and choice["channels"][0]["id"] == CHANNEL
    new = authority(plugin)
    plugin.configure_channel_destination(values(new))
    assert storage[plugin._channel_key(new)]["channel_id"] == CHANNEL
    assert storage[plugin._channel_key(original)]["revision"] == 1
    with pytest.raises(plugin.PluginError):
        plugin.configure_channel_destination(values(authority(plugin), actor=str(uuid4())))


def test_core_configuration_and_tombstones_cannot_be_forged(channel):
    plugin, _, _, _, context = channel
    with pytest.raises(plugin.PluginError):
        plugin.configure_channel_destination({"_plugin_context": {"user_id": OWNER}, "configuration": {"channel_id": CHANNEL}})
    plugin.retire_channel_destination(values({**context, "operation": "retire"}))
    with pytest.raises(plugin.PluginError, match="stale or retired"):
        plugin.configure_channel_destination(values({**context, "destination": {**context["destination"], "revision": 2}}, {"channel_id": CHANNEL}))


def test_channel_failure_is_redacted_and_core_can_retry(channel, monkeypatch):
    plugin, _, sent, _, context = channel
    def unavailable(*args):
        raise GatewayRequestError("private token and transport body", {"code": "unavailable"})
    monkeypatch.setattr(plugin, "_send_channel", unavailable)
    assert deliver(plugin, context) == {"success": False, "retryable": True, "error": "discord_gateway_failed"}
    assert sent == []
