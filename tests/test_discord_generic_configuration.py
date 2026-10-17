"""Generic opaque configuration and actual standalone webhook package regression coverage."""
import copy
import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from uuid import uuid4

import jsonschema
import pytest

from sdk import notifications
from sdk.plugin_protocol import GatewayRequestError

ROOT = Path(__file__).parents[1]
ID = "official.discord-notifications"
URL = "https://discord.com/api/webhooks/123456/test-token"


def load():
    spec = importlib.util.spec_from_file_location("official_discord_notifications", ROOT / "official/discord-notifications/plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def context(operation="configure", revision=1):
    value = {"operation": operation, "scope": "destination", "installation_id": str(uuid4()),
             "destination": {"id": str(uuid4()), "revision": revision, "kind": "discord_webhook"}}
    if operation == "deliver":
        value.update(attempt_id=str(uuid4()), server_revision=1)
    else:
        value["provider_id"] = ID + ".webhook"
    return value


@pytest.fixture
def provider(monkeypatch):
    module = load()
    storage, calls, response = {}, [], {"status": 204, "text": ""}
    def request(method, capability, payload):
        calls.append((method, capability, payload))
        if method == "storage.get":
            return {"value": storage.get(payload["key"])}
        if method == "storage.put":
            storage[payload["key"]] = payload["value"]
            return {}
        assert method == "network.request" and capability == "network.outbound"
        return response
    monkeypatch.setattr(module, "request", request)
    return module, storage, calls, response


def test_registration_declares_generic_configuration_and_recovers_transient_startup(monkeypatch):
    provider = load()
    calls, delays = [], []
    def request(method, capability, payload):
        calls.append((method, capability, payload))
        if len(calls) < 4:
            raise GatewayRequestError("Starting", {"code": "unavailable"})
        return {"registered": True}
    monkeypatch.setattr(notifications, "request", request)
    monkeypatch.setattr(provider.time, "sleep", delays.append)
    provider._register_provider()
    assert delays == [1, 2, 4]
    assert all(call == calls[0] for call in calls)
    assert calls[0] == ("notification_providers.register", "notification_providers.register", {
        "provider_id": ID + ".webhook", "name": "Discord Webhook", "action_id": "deliver",
        "transport": "plugin", "definition": provider.DEFINITION})
    jsonschema.validate(calls[0][2], json.loads((ROOT / "tools/schemas/notification-provider-v1.schema.json").read_bytes()))


@pytest.mark.parametrize("code", ["forbidden", "invalid_request", "conflict", "internal", None])
def test_registration_does_not_hide_permanent_failure(monkeypatch, code):
    provider = load()
    def rejected(*args):
        raise GatewayRequestError("Rejected", {"code": code})
    monkeypatch.setattr(notifications, "request", rejected)
    monkeypatch.setattr(provider.time, "sleep", lambda _: pytest.fail("Permanent denial must not retry"))
    with pytest.raises(GatewayRequestError, match="Rejected"):
        provider._register_provider()


def test_configuration_is_opaque_revision_bound_and_secret_replacement_is_write_only(provider):
    plugin, storage, calls, _ = provider
    authority = context()
    values = {"_notification_context": authority, "configuration": {"url": URL}}
    assert plugin.configure(values) == {"configured": True}
    assert list(storage) == [f"webhooks/{authority['installation_id']}/{authority['destination']['id']}"]
    changed = copy.deepcopy(authority)
    changed["destination"]["revision"] = 2
    assert plugin.configure({"_notification_context": changed, "configuration": {}}) == {"configured": True}
    assert json.loads(next(iter(storage.values()))) == {"url": URL, "revision": 2}
    with pytest.raises(plugin.PluginError, match="stale"):
        plugin.configure(values)
    assert not any(call[0] == "network.request" for call in calls)


@pytest.mark.parametrize("url", [
    "http://discord.com/api/webhooks/123/token", "https://example.com/api/webhooks/123/token",
    "https://discord.com:443/api/webhooks/123/token", "https://discord.com/api/webhooks/123/token?wait=true",
    "https://discord.com/api/webhooks/123/token#secret", "https://user:secret@discord.com/api/webhooks/123/token",
    "https://discord.com/api/webhooks/not-an-id/token", "https://discord.com/api/webhooks/123/token/extra",
    "https://discord.com/api/webhooks/123/%74oken", "https://discord.com/api/webhooks/123/token\n",
])
def test_invalid_webhook_never_stores_or_sends(provider, url):
    plugin, storage, calls, _ = provider
    with pytest.raises(plugin.PluginError) as rejected:
        plugin.configure({"_notification_context": context(), "configuration": {"url": url}})
    assert url not in str(rejected.value)
    assert storage == {} and not any(call[0] == "network.request" for call in calls)


@pytest.mark.parametrize("status,retryable,success", [(204, False, True), (200, False, True), (429, True, False), (503, True, False), (0, True, False), (401, False, False), (404, False, False), ("204", True, False)])
def test_delivery_respects_http_status_and_uses_approved_content_only(provider, status, retryable, success):
    plugin, storage, calls, response = provider
    authority = context()
    plugin.configure({"_notification_context": authority, "configuration": {"url": URL}})
    authority = {**authority, "operation": "deliver", "attempt_id": str(uuid4()), "server_revision": 1}
    authority.pop("provider_id")
    response.update(status=status, text="remote-secret-body")
    result = plugin.deliver({"_notification_context": authority, "delivery": {
        "title": "Released", "body": "@everyone Public facts", "event_at": 1234567890,
        "link": "https://app.example.test/"}, "private": "never append"})
    assert result["success"] is success and result["retryable"] is retryable
    assert "remote-secret-body" not in str(result)
    sent = calls[-1][2]
    assert sent["response_format"] == "text"
    assert sent["body"]["allowed_mentions"] == {"parse": []}
    assert sent["body"]["embeds"][0]["title"] == "Released"
    assert "never append" not in json.dumps(sent["body"])
    assert URL not in json.dumps(sent["body"])


def test_retirement_erases_secret_and_blocks_stale_callbacks_and_handoffs(provider):
    plugin, storage, calls, _ = provider
    authority = context()
    plugin.configure({"_notification_context": authority, "configuration": {"url": URL}})
    retired = copy.deepcopy(authority)
    retired.update(operation="retire")
    retired["destination"]["revision"] = 2
    assert plugin.retire({"_notification_context": retired}) == {"retired": True}
    assert URL not in json.dumps(storage)
    with pytest.raises(plugin.PluginError, match="retired"):
        plugin.configure({"_notification_context": authority, "configuration": {"url": URL}})
    delivery = {**authority, "operation": "deliver", "server_revision": 1, "attempt_id": str(uuid4())}
    delivery.pop("provider_id")
    assert not plugin.deliver({"_notification_context": delivery, "delivery": {"title": "X", "body": "X"}})["success"]
    assert not any(call[0] == "network.request" for call in calls)


def test_configuration_rejects_ui_identity_and_installation_cannot_claim_old_secrets(provider):
    plugin, storage, calls, _ = provider
    with pytest.raises(plugin.PluginError):
        plugin.configure({"_plugin_context": {"user_id": str(uuid4())}, "configuration": {"url": URL}})
    authority = context()
    plugin.configure({"_notification_context": authority, "configuration": {"url": URL}})
    replacement = {**authority, "installation_id": str(uuid4())}
    with pytest.raises(plugin.PluginError):
        plugin.configure({"_notification_context": replacement, "configuration": {}})
    assert len(storage) == 1


def test_actual_package_is_standalone_with_exact_minimal_grants(current_packages, tmp_path):
    with zipfile.ZipFile(current_packages[ID]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["api_contract_version"] == "1.1.14"
        assert {cap["name"] for cap in manifest["capabilities"]} == {
            "notification_providers.register", "notification_providers.deliver", "plugin.storage", "network.outbound"}
        assert manifest.get("storage") and not manifest.get("frontend")
        assert not any("frontend/" in name for name in archive.namelist())
        for name in archive.namelist():
            if name.startswith("payload/") and not name.endswith("/"):
                target = tmp_path / name.removeprefix("payload/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
    result = subprocess.run([sys.executable, "-c", "import plugin; assert plugin.DEFINITION['destinations'][0]['privacy']=='PUBLIC'; assert not plugin.deliver({})['success']"], cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
