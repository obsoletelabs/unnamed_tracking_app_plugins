"""Tests for the plugin-owned Discord webhook provider."""

import importlib.util
import json
import zipfile
from pathlib import Path

import jsonschema
import pytest

from sdk import notifications
from sdk.plugin_protocol import GatewayRequestError

ROOT = Path(__file__).parents[1]
ID = "official.discord-notifications"


def load():
    spec = importlib.util.spec_from_file_location("official_discord_notifications", ROOT / "official/discord-notifications/plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registration_declares_plugin_owned_public_destination(monkeypatch):
    provider = load()
    calls, delays = [], []

    def request(method, capability, payload):
        calls.append((method, capability, payload))
        if len(calls) < 4:
            raise GatewayRequestError("Host starting", {"code": "unavailable"})
        return {"registered": True}

    monkeypatch.setattr(notifications, "request", request)
    monkeypatch.setattr(provider.time, "sleep", delays.append)
    provider._register_provider()
    assert delays == [1, 2, 4]
    assert calls[0] == (
        "notification_providers.register",
        "notification_providers.register",
        {
            "provider_id": ID + ".webhook",
            "name": "Discord Webhook",
            "action_id": "deliver",
            "destination_kind": "discord_webhook",
            "privacy": "PUBLIC",
            "channel_context": "external",
            "transport": "plugin_public",
        },
    )
    jsonschema.validate(
        calls[0][2],
        json.loads((ROOT / "tools/schemas/notification-provider-v1.schema.json").read_bytes()),
    )


@pytest.mark.parametrize("code", ["forbidden", "invalid_request", "conflict", "internal", None])
def test_registration_does_not_hide_permanent_failure(monkeypatch, code):
    provider = load()

    def rejected(*args):
        raise GatewayRequestError("Rejected", {"code": code})

    monkeypatch.setattr(notifications, "request", rejected)
    monkeypatch.setattr(provider.time, "sleep", lambda _: pytest.fail("Permanent denial must not retry"))
    with pytest.raises(GatewayRequestError, match="Rejected"):
        provider._register_provider()


def test_webhook_storage_is_user_scoped_and_validates_discord_urls(monkeypatch):
    provider = load()
    values = {"_plugin_context": {"user_id": "1234"}, "url": "https://discord.com/api/webhooks/123/token"}
    stored = []
    monkeypatch.setattr(provider, "request", lambda method, capability, payload: stored.append((method, capability, payload)) or {"ok": True})
    assert provider.save_webhook(values)["ok"]
    assert stored[-1][2]["key"] == "webhooks/1234"
    assert "discord.com/api/webhooks/123/token" in stored[-1][2]["value"]

    with pytest.raises(provider.PluginError):
        provider.save_webhook({"_plugin_context": {"user_id": "1234"}, "url": "https://example.com/webhook"})


def test_package_contains_plugin_owned_configuration_and_frontend(current_packages):
    with zipfile.ZipFile(current_packages[ID]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert {cap["name"] for cap in manifest["capabilities"]} >= {
            "notification_providers.register",
            "notification_providers.deliver",
            "plugin.storage",
            "network.outbound",
        }
        assert manifest.get("storage")
        assert manifest.get("frontend")
        assert "payload/frontend/index.html" in archive.namelist()
