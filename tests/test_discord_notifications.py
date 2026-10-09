"""Maintained consumer and actual independently packaged protected renderer."""

import importlib.util
import json
import subprocess
import sys
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


def test_render_is_an_approved_field_layout_even_with_unrelated_private_values():
    provider = load()
    result = provider.render({"delivery": {"body": "approved"}, "private_data": "never include"})
    assert result == {"style": "embed", "fields": ["title", "body", "event_at", "link"]}
    schema = json.loads((ROOT / "tools/schemas/notification-layout-v1.schema.json").read_bytes())
    jsonschema.validate(result, schema)
    assert "never include" not in json.dumps(result)


def test_registration_recovers_without_broadening_permissions(monkeypatch):
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
    assert all(call == calls[0] for call in calls)
    assert calls[0] == ("notification_providers.register", "notification_providers.register", {
        "provider_id": ID + ".webhook", "name": "Discord", "action_id": "render", "transport": "discord_webhook"})
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


def test_package_is_standalone_and_has_no_endpoint_storage(current_packages, tmp_path):
    with zipfile.ZipFile(current_packages[ID]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert {cap["name"] for cap in manifest["capabilities"]} == {
            "notification_providers.register", "notification_providers.deliver"}
        assert not manifest.get("storage") and not manifest.get("frontend")
        for name in archive.namelist():
            if name.startswith("payload/") and not name.endswith("/"):
                target = tmp_path / name.removeprefix("payload/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
    result = subprocess.run([sys.executable, "-c", "import plugin; assert plugin.render({})['style'] == 'embed'"],
                            cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
