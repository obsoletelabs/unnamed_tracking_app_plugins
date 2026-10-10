"""Regression tests for the verified Discord bot notification provider."""

import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from sdk import notifications
from sdk.plugin_protocol import GatewayRequestError

ROOT = Path(__file__).parents[1]
PLUGIN_PATH = ROOT / "official/discord-bot-notifications/plugin.py"


def load():
    spec = importlib.util.spec_from_file_location("discord_bot_notifications", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_manifest_declares_required_privileges_and_private_transport():
    manifest = json.loads((ROOT / "official/discord-bot-notifications/manifest.json").read_text(encoding="utf-8"))
    schema = json.loads((ROOT / "tools/schemas/manifest-v1.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema)
    assert "network.outbound" in {item["name"] for item in manifest["capabilities"]}
    assert "notification_providers.deliver" in {item["name"] for item in manifest["capabilities"]}
    assert manifest["ui"]["pages"] == ["admin", "account"]


def test_provider_registers_as_generic_private_plugin_destination(monkeypatch):
    provider = load()
    calls = []

    def fake_request(method, capability, payload):
        calls.append((method, capability, payload))
        return {"registered": True}

    monkeypatch.setattr(notifications, "request", fake_request)
    provider._register_provider()
    assert calls == [("notification_providers.register", "notification_providers.register", {
        "provider_id": "official.discord-bot-notifications.dm", "name": "Discord Bot DM", "action_id": "deliver",
        "transport": "plugin", "definition": {
            "destinations": [{"kind": "discord_bot_dm", "label": "Discord Bot DM", "privacy": "PRIVATE", "fields": []}],
            "configure_action": "configure-destination", "retire_action": "retire-destination", "test_action": "test-dm",
            "features": {"critical_supported": False, "multiple_destinations": False},
        },
    })]


def test_link_code_must_be_verified_before_identity_is_saved(monkeypatch):
    provider = load()
    storage = {}
    sent = []
    user_id = "12345678-1234-5678-1234-567812345678"
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)
    monkeypatch.setattr(provider, "_bot_config", lambda: {"token": "test-token", "guild_id": "123456789012345678"})
    monkeypatch.setattr(provider.time, "time", lambda: 1000)
    monkeypatch.setattr(provider.secrets, "randbelow", lambda maximum: 1234567)
    monkeypatch.setattr(provider, "_load", lambda key, default=None: storage.get(key, default))
    monkeypatch.setattr(provider, "_store", lambda key, value: storage.__setitem__(key, value))
    monkeypatch.setattr(provider, "_delete", lambda key: storage.pop(key, None))
    monkeypatch.setattr(provider, "_discord", lambda token, method, path, body=None: [{"user": {"username": "casey", "id": "123456789012345678"}}])
    monkeypatch.setattr(provider, "_send_dm", lambda token, user_id, content: sent.append(content))

    result = provider.start_link({"username": "casey"})
    assert result["ok"] is True
    assert result["expires_in_seconds"] == 600
    assert sent and "01234567" in sent[0]
    assert "links/" + user_id not in storage

    with pytest.raises(provider.PluginError, match="incorrect"):
        provider.confirm_link({"code": "00000000"})
    assert "links/" + user_id not in storage

    confirmed = provider.confirm_link({"code": "01234567"})
    assert confirmed["ok"] is True
    assert storage["links/" + user_id]["discord_id"] == "123456789012345678"
    assert "linked_at" in storage["links/" + user_id]
    assert "pending-links/" + user_id not in storage


def test_username_lookup_refuses_ambiguous_matches(monkeypatch):
    provider = load()
    monkeypatch.setattr(provider, "_discord", lambda token, method, path, body=None: [
        {"user": {"username": "casey", "id": "123456789012345678"}},
        {"user": {"username": "casey", "id": "223456789012345678"}},
    ])
    with pytest.raises(provider.PluginError, match="more than one"):
        provider._member_by_username("token", "123456789012345678", "casey")


def test_delivery_only_sends_to_the_current_users_verified_link(monkeypatch):
    provider = load()
    sent = []
    user_id = "12345678-1234-5678-1234-567812345678"
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)
    monkeypatch.setattr(provider, "_load", lambda key, default=None: {
        "secrets/bot-config": {"token": "test-token", "guild_id": "123456789012345678"},
        "links/" + user_id: {"discord_id": "123456789012345678", "username": "casey"},
    }.get(key, default))
    monkeypatch.setattr(provider, "_store", lambda key, value: None)
    monkeypatch.setattr(provider, "_send_dm", lambda token, user_id, content: sent.append((user_id, content)))
    result = provider.deliver({"_plugin_context": {"user_id": user_id}, "_notification_context": {"operation": "deliver", "destination": {"kind": "discord_bot_dm", "id": "12345678-1234-5678-1234-567812345678", "revision": 1}}, "delivery": {"title": "Release", "body": "A new episode is available."}})
    assert result == {"success": True, "retryable": False}
    assert sent == [("123456789012345678", "**Release**\nA new episode is available.")]


def test_delivery_without_verified_link_never_sends(monkeypatch):
    provider = load()
    sent = []
    user_id = "12345678-1234-5678-1234-567812345678"
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)
    monkeypatch.setattr(provider, "_load", lambda key, default=None: {"token": "test-token", "guild_id": "123456789012345678"} if key == "secrets/bot-config" else default)
    monkeypatch.setattr(provider, "_send_dm", lambda *args: sent.append(args))
    result = provider.deliver({"_plugin_context": {"user_id": user_id}, "_notification_context": {"operation": "deliver", "destination": {"kind": "discord_bot_dm", "id": "12345678-1234-5678-1234-567812345678", "revision": 1}}, "delivery": {"title": "Private", "body": "Do not send without linking."}})
    assert result["success"] is False
    assert result["error"] == "recipient_not_linked"
    assert sent == []


def test_status_never_returns_the_bot_token(monkeypatch):
    provider = load()
    user_id = "12345678-1234-5678-1234-567812345678"
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)
    monkeypatch.setattr(provider, "_load", lambda key, default=None: {"secrets/bot-config": {"token": "sensitive-bot-token", "guild_id": "123456789012345678"}}.get(key, default))
    monkeypatch.setattr(provider, "_bot_snapshot", lambda token, guild_id: {
        "bot": {"id": "123456789012345678", "username": "Tracking Bot", "global_name": "Tracking Bot", "avatar_url": None, "verified": True},
        "guild": {"id": guild_id, "name": "Tracking Server", "features": [], "member_count": 42, "online_count": 7},
        "bot_member": {"role_names": ["Bot"], "role_count": 1, "permissions": 2048, "permission_names": ["SEND_MESSAGES"]},
        "health": {"api_ok": True, "request_ms": 31},
    })
    result = provider.get_config({"_plugin_context": {"user_id": user_id}})
    assert result["bot_configured"] is True
    assert result["bot"]["username"] == "Tracking Bot"
    assert result["guild"]["member_count"] == 42
    assert result["health"]["request_ms"] == 31
    assert "token" not in result
    assert "sensitive-bot-token" not in repr(result)


def test_bot_snapshot_exposes_identity_server_membership_and_permissions(monkeypatch):
    provider = load()
    responses = {
        "/users/@me": {"id": "123456789012345678", "username": "Tracking Bot", "global_name": "Tracking Bot", "bot": True, "verified": True, "avatar": "avatarhash"},
        "/guilds/123456789012345678?with_counts=true": {"id": "123456789012345678", "name": "Tracking Server", "owner_id": "987654321098765432", "approximate_member_count": 100, "approximate_presence_count": 12, "features": ["COMMUNITY"], "verification_level": 2, "premium_tier": 1, "preferred_locale": "en-US", "nsfw_level": 0},
        "/guilds/123456789012345678/members/123456789012345678": {"nick": "Tracker", "joined_at": "2026-01-01T00:00:00.000000+00:00", "pending": False, "roles": ["123456789012345678", "223456789012345678"]},
        "/guilds/123456789012345678/roles": [{"id": "123456789012345678", "name": "@everyone", "permissions": "1024"}, {"id": "223456789012345678", "name": "Bot", "permissions": "2048"}],
    }
    monkeypatch.setattr(provider, "_discord", lambda token, method, path, body=None: responses[path])
    snapshot = provider._bot_snapshot("token", "123456789012345678")
    assert snapshot["bot"]["username"] == "Tracking Bot"
    assert snapshot["guild"]["member_count"] == 100
    assert snapshot["guild"]["features"] == ["COMMUNITY"]
    assert snapshot["bot_member"]["role_names"] == ["@everyone", "Bot"]
    assert snapshot["bot_member"]["permissions"] == 3072
    assert "VIEW_CHANNEL" in snapshot["bot_member"]["permission_names"]
    assert "SEND_MESSAGES" in snapshot["bot_member"]["permission_names"]


def test_delivery_reports_gateway_permission_errors_without_retrying(monkeypatch):
    provider = load()
    user_id = "12345678-1234-5678-1234-567812345678"
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)

    def denied_storage(key, default=None):
        raise GatewayRequestError("permission denied", {"code": "forbidden"})

    monkeypatch.setattr(provider, "_load", denied_storage)
    result = provider.deliver({"_plugin_context": {"user_id": user_id}, "_notification_context": {"operation": "deliver", "destination": {"kind": "discord_bot_dm", "id": "12345678-1234-5678-1234-567812345678", "revision": 1}}, "delivery": {"title": "Private", "body": "No delivery."}})
    assert result["success"] is False
    assert result["retryable"] is False
    assert result["error"] == "discord_permission_denied"


def test_generic_destination_requires_a_verified_link(monkeypatch):
    provider = load()
    user_id = "12345678-1234-5678-1234-567812345678"
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)
    monkeypatch.setattr(provider, "_load", lambda key, default=None: None)
    with pytest.raises(provider.PluginError, match="Link and verify"):
        provider.configure_destination({"_plugin_context": {"user_id": user_id}})


def test_retiring_destination_removes_link_and_pending_challenge(monkeypatch):
    provider = load()
    user_id = "12345678-1234-5678-1234-567812345678"
    deleted = []
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)
    monkeypatch.setattr(provider, "_delete", deleted.append)
    result = provider.retire_destination({"_plugin_context": {"user_id": user_id}})
    assert result["ok"] is True
    assert deleted == ["links/" + user_id, "pending-links/" + user_id]


def test_delivery_rejects_forged_or_missing_core_destination_context(monkeypatch):
    provider = load()
    user_id = "12345678-1234-5678-1234-567812345678"
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)
    result = provider.deliver({"_plugin_context": {"user_id": user_id}, "delivery": {"title": "No context"}})
    assert result == {"success": False, "retryable": False, "error": "notification_context_invalid"}


def test_discord_uses_host_outbound_gateway_data_contract(monkeypatch):
    provider = load()
    captured = {}

    def fake_request(method, capability, payload):
        captured.update(method=method, capability=capability, payload=payload)
        return {"status": 200, "data": {"id": "123456789012345678", "username": "Tracking Bot"}}

    monkeypatch.setattr(provider, "request", fake_request)
    result = provider._discord("test-token", "POST", "/example", {"hello": "world"})
    assert result == {"id": "123456789012345678", "username": "Tracking Bot"}
    assert captured["method"] == "network.request"
    assert captured["capability"] == "network.outbound"
    assert captured["payload"]["body"] == {"hello": "world"}
    assert "json" not in captured["payload"]
    assert captured["payload"]["headers"]["Authorization"] == "Bot test-token"
    assert "User-Agent" in captured["payload"]["headers"]


@pytest.mark.parametrize(
    ("status", "message"),
    [
        (401, "rejected the bot token"),
        (403, "denied access"),
        (404, "could not find the requested server"),
        (429, "rate limiting"),
    ],
)
def test_discord_http_errors_are_actionable(monkeypatch, status, message):
    provider = load()
    monkeypatch.setattr(
        provider,
        "request",
        lambda *args, **kwargs: {"status": status, "error": "Remote server rejected the request."},
    )
    with pytest.raises(provider.PluginError, match=message):
        provider._discord("test-token", "GET", "/users/@me")


def test_save_config_allows_incomplete_bot_identity_but_rejects_bad_credentials(monkeypatch):
    provider = load()
    saved = {}
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: "12345678-1234-5678-1234-567812345678")

    def incomplete_identity(token, guild_id):
        raise provider.PluginError("Discord did not return the configured bot identity.")

    monkeypatch.setattr(provider, "_bot_snapshot", incomplete_identity)
    monkeypatch.setattr(provider, "_store", lambda key, value: saved.update({key: value}))
    result = provider.save_bot_config({"token": "possibly-valid-token", "guild_id": "123456789012345678"})
    assert result["ok"] is True
    assert "warning" in result
    assert saved["secrets/bot-config"] == {
        "token": "possibly-valid-token",
        "guild_id": "123456789012345678",
    }

    def invalid_token(token, guild_id):
        raise provider.PluginError("Discord rejected the bot token. Check that it is the current bot token.")

    monkeypatch.setattr(provider, "_bot_snapshot", invalid_token)
    with pytest.raises(provider.PluginError, match="rejected the bot token"):
        provider.save_bot_config({"token": "bad-token", "guild_id": "123456789012345678"})



def test_multiple_verified_accounts_are_preserved_and_unlinked_individually(monkeypatch):
    provider = load()
    storage = {}
    user_id = "12345678-1234-5678-1234-567812345678"
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)
    monkeypatch.setattr(provider, "_load", lambda key, default=None: storage.get(key, default))
    monkeypatch.setattr(provider, "_store", lambda key, value: storage.__setitem__(key, value))
    monkeypatch.setattr(provider, "_delete", lambda key: storage.pop(key, None))

    provider._save_linked_accounts(user_id, [
        {"discord_id": "123456789012345678", "linked_at": 100},
        {"discord_id": "223456789012345678", "linked_at": 200},
    ])
    saved = storage["links/" + user_id]
    assert [item["discord_id"] for item in provider._linked_accounts(saved)] == [
        "123456789012345678", "223456789012345678"
    ]
    assert saved["discord_id"] == "123456789012345678"

    result = provider.unlink({"discord_id": "123456789012345678"})
    assert result["ok"] is True
    remaining = provider._linked_accounts(storage["links/" + user_id])
    assert [item["discord_id"] for item in remaining] == ["223456789012345678"]
    assert storage["links/" + user_id]["discord_id"] == "223456789012345678"


def test_delivery_sends_to_every_verified_account(monkeypatch):
    provider = load()
    sent = []
    user_id = "12345678-1234-5678-1234-567812345678"
    storage = {
        "secrets/bot-config": {"token": "test-token", "guild_id": "123456789012345678"},
        "links/" + user_id: {"accounts": [
            {"discord_id": "123456789012345678", "linked_at": 100},
            {"discord_id": "223456789012345678", "linked_at": 200},
        ]},
    }
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: user_id)
    monkeypatch.setattr(provider, "_load", lambda key, default=None: storage.get(key, default))
    monkeypatch.setattr(provider, "_store", lambda key, value: storage.__setitem__(key, value))
    monkeypatch.setattr(provider, "_send_dm", lambda token, discord_id, content: sent.append((discord_id, content)))
    monkeypatch.setattr(provider.time, "time", lambda: 500)

    result = provider.deliver({
        "_plugin_context": {"user_id": user_id},
        "_notification_context": {"operation": "deliver", "destination": {"kind": "discord_bot_dm", "id": "dest", "revision": 1}},
        "delivery": {"title": "Release", "body": "A new episode is available."},
    })
    assert result == {"success": True, "retryable": False}
    assert [recipient for recipient, _ in sent] == ["123456789012345678", "223456789012345678"]
    assert all(content == "**Release**\nA new episode is available." for _, content in sent)
    assert all(account["last_delivery_at"] == 500 for account in storage["links/" + user_id]["accounts"])


def test_legacy_single_link_is_read_as_one_account():
    provider = load()
    account = {"discord_id": "123456789012345678", "linked_at": 100}
    assert provider._linked_accounts(account) == [account]
