"""Tests for the plugin-owned Discord webhook provider."""

import importlib.util
import json
import zipfile
from pathlib import Path
from uuid import uuid4

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
            "transport": "plugin",
            "definition": provider.DEFINITION,
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


def test_webhook_storage_is_core_destination_scoped_and_validates_discord_urls(monkeypatch):
    provider = load()
    installation, destination = str(uuid4()), str(uuid4())
    context = {"operation": "configure", "scope": "destination", "provider_id": ID + ".webhook",
               "installation_id": installation,
               "destination": {"id": destination, "revision": 1, "kind": "discord_webhook"}}
    values = {"_notification_context": context, "configuration": {"url": "https://discord.com/api/webhooks/123/token"}}
    stored = []
    monkeypatch.setattr(provider, "request", lambda method, capability, payload: stored.append((method, capability, payload)) or {"ok": True})
    assert provider.configure(values) == {"configured": True}
    assert stored[-1][2]["key"] == f"webhooks/{installation}/{destination}"
    assert "discord.com/api/webhooks/123/token" in stored[-1][2]["value"]

    with pytest.raises(provider.PluginError):
        provider.configure({"_notification_context": context, "configuration": {"url": "https://example.com/webhook"}})


def test_package_contains_plugin_owned_configuration_without_redundant_frontend(current_packages):
    with zipfile.ZipFile(current_packages[ID]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert {cap["name"] for cap in manifest["capabilities"]} >= {
            "notification_providers.register",
            "notification_providers.deliver",
            "plugin.storage",
            "network.outbound",
        }
        assert manifest.get("storage")
        assert not manifest.get("frontend")
        assert not any("frontend/" in name for name in archive.namelist())
