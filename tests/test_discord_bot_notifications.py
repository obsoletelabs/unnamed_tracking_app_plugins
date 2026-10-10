"""Regression tests for the verified Discord bot notification provider."""

import hashlib
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


def test_manifest_declares_only_required_privileges_and_known_transport():
    manifest = json.loads(
        (ROOT / "official/discord-bot-notifications/manifest.json").read_text(encoding="utf-8")
    )
    schema = json.loads((ROOT / "tools/schemas/manifest-v1.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(manifest, schema)
    ui = json.loads(
        (ROOT / "official/discord-bot-notifications/ui.json").read_text(encoding="utf-8")
    )
    assert set(manifest["ui"]["actions"]) == {item["id"] for item in ui["actions"]}
    assert set(manifest["ui"]["pages"]) == {item["id"] for item in ui["pages"]}
    assert set(manifest["ui"]["settings"]) == {item["id"] for item in ui["settings"]}
    assert "network.outbound" in {item["name"] for item in manifest["capabilities"]}
    assert "notification_providers.deliver" in {
        item["name"] for item in manifest["capabilities"]
    }
    assert manifest["ui"]["pages"] == ["admin", "account"]


def test_provider_registers_with_the_private_dm_transport(monkeypatch):
    provider = load()
    calls = []

    def fake_request(method, capability, payload):
        calls.append((method, capability, payload))
        return {"registered": True}

    monkeypatch.setattr(notifications, "request", fake_request)
    provider._register_provider()
    assert calls == [
        (
            "notification_providers.register",
            "notification_providers.register",
            {
                "provider_id": "official.discord-bot-notifications.dm",
                "name": "Discord Bot DM",
                "action_id": "deliver",
                "transport": "discord_bot_dm",
            },
        )
    ]


def test_link_code_must_be_verified_before_the_discord_identity_is_saved(monkeypatch):
    provider = load()
    storage = {}
    sent = []
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: "host-user")
    monkeypatch.setattr(provider, "_bot_config", lambda: {"token": "test-token", "guild_id": "123456789012345678"})
    monkeypatch.setattr(provider.time, "time", lambda: 1000)
    monkeypatch.setattr(provider.secrets, "randbelow", lambda maximum: 1234567)
    monkeypatch.setattr(provider, "_load", lambda key, default=None: storage.get(key, default))
    monkeypatch.setattr(provider, "_store", lambda key, value: storage.__setitem__(key, value))
    monkeypatch.setattr(provider, "_delete", lambda key: storage.pop(key, None))
    monkeypatch.setattr(
        provider,
        "_discord",
        lambda token, method, path, body=None: [
            {"user": {"username": "casey", "id": "123456789012345678"}}
        ],
    )
    monkeypatch.setattr(provider, "_send_dm", lambda token, user_id, content: sent.append(content))

    result = provider.start_link({"username": "casey"})
    assert result["ok"] is True
    assert sent and "01234567" in sent[0]
    pending = storage["pending-links/host-user"]
    assert pending["code_digest"] == hashlib.sha256(
        f"host-user:01234567:{pending['expires_at']}".encode()
    ).hexdigest()
    assert "links/host-user" not in storage

    with pytest.raises(provider.PluginError, match="incorrect"):
        provider.confirm_link({"code": "00000000"})
    assert "links/host-user" not in storage

    confirmed = provider.confirm_link({"code": "01234567"})
    assert confirmed["ok"] is True
    assert storage["links/host-user"]["discord_id"] == "123456789012345678"
    assert storage["links/host-user"]["username"] == "casey"
    assert "pending-links/host-user" not in storage


def test_username_lookup_refuses_ambiguous_matches(monkeypatch):
    provider = load()
    sent = []
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: "host-user")
    monkeypatch.setattr(provider, "_bot_config", lambda: {"token": "test-token", "guild_id": "123456789012345678"})
    monkeypatch.setattr(provider, "_load", lambda key, default=None: default)
    monkeypatch.setattr(provider, "_store", lambda key, value: None)
    monkeypatch.setattr(
        provider,
        "_discord",
        lambda token, method, path, body=None: [
            {"user": {"username": "casey", "id": "123456789012345678"}},
            {"user": {"username": "casey", "id": "223456789012345678"}},
        ],
    )
    monkeypatch.setattr(provider, "_send_dm", lambda *args: sent.append(args))
    with pytest.raises(provider.PluginError, match="exactly one"):
        provider.start_link({"username": "casey"})
    assert sent == []


def test_delivery_only_sends_to_the_current_host_users_verified_link(monkeypatch):
    provider = load()
    sent = []
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: "host-user")
    monkeypatch.setattr(
        provider,
        "_load",
        lambda key, default=None: {
            "secrets/bot-config": {"token": "test-token", "guild_id": "123456789012345678"},
            "links/host-user": {"discord_id": "123456789012345678", "username": "casey"},
        }.get(key, default),
    )
    monkeypatch.setattr(provider, "_send_dm", lambda token, user_id, content: sent.append((user_id, content)))
    result = provider.deliver(
        {
            "_plugin_context": {"user_id": "host-user"},
            "delivery": {"title": "Release", "body": "A new episode is available."},
        }
    )
    assert result == {"success": True, "retryable": False}
    assert sent == [
        ("123456789012345678", "**Release**\nA new episode is available.")
    ]


def test_delivery_without_a_verified_link_never_sends(monkeypatch):
    provider = load()
    sent = []
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: "host-user")
    monkeypatch.setattr(
        provider,
        "_load",
        lambda key, default=None: {"token": "test-token", "guild_id": "123456789012345678"}
        if key == "secrets/bot-config"
        else default,
    )
    monkeypatch.setattr(provider, "_send_dm", lambda *args: sent.append(args))
    result = provider.deliver(
        {
            "_plugin_context": {"user_id": "host-user"},
            "delivery": {"title": "Private", "body": "Do not send without linking."},
        }
    )
    assert result["success"] is False
    assert result["error"] == "recipient_not_linked"
    assert sent == []


def test_actor_normalizes_user_id_before_scoping_private_links(monkeypatch):
    provider = load()
    user_id = "12345678-1234-5678-1234-567812345678"
    assert provider._actor({"_plugin_context": {"user_id": user_id.replace("-", "")}}) == user_id


def test_status_never_returns_the_bot_token(monkeypatch):
    provider = load()
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: "12345678-1234-5678-1234-567812345678")
    monkeypatch.setattr(
        provider,
        "_load",
        lambda key, default=None: {
            "secrets/bot-config": {
                "token": "sensitive-bot-token",
                "guild_id": "123456789012345678",
                "bot_name": "Test Bot",
            }
        }.get(key, default),
    )
    result = provider.get_config(
        {
            "_plugin_context": {
                "user_id": "12345678-1234-5678-1234-567812345678",
                "is_admin": True,
            }
        }
    )
    assert result["bot_configured"] is True
    assert result["bot_name"] == "Test Bot"
    assert "token" not in result
    assert "sensitive-bot-token" not in repr(result)



def test_delivery_reports_revoked_storage_permission_without_retrying(monkeypatch):
    provider = load()
    monkeypatch.setattr(provider, "_actor", lambda values, admin=False: "host-user")

    def denied_storage(key, default=None):
        raise GatewayRequestError("permission denied", {"code": "forbidden"})

    monkeypatch.setattr(provider, "_load", denied_storage)
    result = provider.deliver(
        {
            "_plugin_context": {"user_id": "host-user"},
            "delivery": {"title": "Private", "body": "No delivery."},
        }
    )
    assert result["success"] is False
    assert result["retryable"] is False
    assert result["error"] == "discord_permission_denied"
