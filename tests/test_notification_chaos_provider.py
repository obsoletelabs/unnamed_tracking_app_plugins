"""Standalone protected demo consumer, bounded simulation and malformed layouts."""

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
ID = "example.notification-chaos-provider"


@pytest.fixture
def demo(monkeypatch):
    spec = importlib.util.spec_from_file_location("chaos", ROOT / "examples/notification-chaos-provider/plugin.py")
    plugin = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plugin)
    state, calls = {"mode": None}, []

    def request(method, capability, payload):
        calls.append((method, capability, payload))
        if method == "settings.get":
            assert capability == "plugin.settings" and payload == {"key": "mode"}
            return {"value": state["mode"]}
        assert capability == "plugin.storage"
        if method == "storage.get":
            return {"value": state.get(payload["key"])}
        assert method == "storage.put"
        state[payload["key"]] = payload["value"]
        return {}

    monkeypatch.setattr(plugin, "request", request)
    return plugin, state, calls


@pytest.mark.parametrize("mode,style", [(None, "embed"), ("embed", "embed"), ("plain", "plain")])
def test_success_references_approved_fields_only(demo, mode, style):
    plugin, state, calls = demo
    state["mode"] = mode
    layout = plugin.render({"delivery": {"body": "approved"}, "private": "never append"})
    assert layout == {"style": style, "fields": ["link", "event_at", "body", "title"]}
    jsonschema.validate(layout, json.loads((ROOT / "tools/schemas/notification-layout-v1.schema.json").read_text()))
    assert "never append" not in json.dumps(layout)
    assert len(calls) == 1


def test_first_failure_is_persistent_bounded_and_contains_no_content(demo):
    plugin, state, _ = demo
    state["mode"] = "fail_first"
    first = str(uuid4())
    work = {"delivery": {"notification_id": first, "body": "private content", "title": "private title"}}
    with pytest.raises(RuntimeError, match="first render"):
        plugin.render(work)
    assert json.loads(state[plugin.LEDGER_KEY]) == [first]
    assert plugin.render(work)["style"] == "embed"
    for _ in range(plugin.LEDGER_LIMIT):
        with pytest.raises(RuntimeError, match="first render"):
            plugin.render({"delivery": {"notification_id": str(uuid4())}})
    ledger = json.loads(state[plugin.LEDGER_KEY])
    assert len(ledger) == plugin.LEDGER_LIMIT and first not in ledger
    assert "private" not in state[plugin.LEDGER_KEY]


@pytest.mark.parametrize("raw", ["{}", "not JSON", '["not UUID"]', json.dumps([str(uuid4())] * 101)])
def test_corrupt_or_oversized_ledger_fails_closed(demo, raw):
    plugin, state, _ = demo
    state.update(mode="fail_first")
    state[plugin.LEDGER_KEY] = raw
    with pytest.raises(ValueError, match="ledger is invalid"):
        plugin.render({"delivery": {"notification_id": str(uuid4())}})
    assert state[plugin.LEDGER_KEY] == raw


@pytest.mark.parametrize("identity", [None, "not UUID", 4])
def test_first_failure_requires_core_identity_before_writing(demo, identity):
    plugin, state, calls = demo
    state["mode"] = "fail_first"
    with pytest.raises(ValueError, match="identity is required"):
        plugin.render({"delivery": {"notification_id": identity}})
    assert len(calls) == 1 and plugin.LEDGER_KEY not in state


def test_repeatable_failure_and_schema_rejection_are_distinct(demo):
    plugin, state, _ = demo
    state["mode"] = "always_fail"
    for _ in range(3):
        with pytest.raises(RuntimeError, match="every render"):
            plugin.render({})
    state["mode"] = "invalid_layout"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(plugin.render({}), json.loads((ROOT / "tools/schemas/notification-layout-v1.schema.json").read_text()))
    assert plugin.LEDGER_KEY not in state


@pytest.mark.parametrize("mode", ["unknown", 2, {"style": "plain"}])
def test_unknown_mode_does_not_silently_deliver(demo, mode):
    plugin, state, _ = demo
    state["mode"] = mode
    with pytest.raises(ValueError, match="valid demo failure mode"):
        plugin.render({})


def test_registration_recovers_only_transient_host_unavailability(demo, monkeypatch):
    plugin, _, _ = demo
    calls, delays = [], []

    def request(method, capability, payload):
        calls.append((method, capability, payload))
        if len(calls) < 3:
            raise GatewayRequestError("Starting", {"code": "unavailable"})
        return {"registered": True}

    monkeypatch.setattr(notifications, "request", request)
    monkeypatch.setattr(plugin.time, "sleep", delays.append)
    plugin._register_provider()
    assert delays == [1, 2] and all(call == calls[0] for call in calls)
    assert calls[0] == ("notification_providers.register", "notification_providers.register", {
        "provider_id": ID + ".webhook", "name": "Notification Chaos Demo", "action_id": "render", "transport": "discord_webhook"})
    def denied(*args):
        raise GatewayRequestError("Denied", {"code": "forbidden"})
    monkeypatch.setattr(notifications, "request", denied)
    with pytest.raises(GatewayRequestError, match="Denied"):
        plugin._register_provider()
    assert delays == [1, 2]


def test_actual_preview_is_standalone_and_has_exact_minimal_grants(current_packages, tmp_path):
    with zipfile.ZipFile(current_packages[ID]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert {cap["name"] for cap in manifest["capabilities"]} == {
            "notification_providers.register", "notification_providers.deliver", "plugin.settings", "plugin.storage"}
        assert manifest["name"] == "Notification Chaos Demo" and manifest["storage"] == {"quota_mb": 1}
        assert not manifest.get("frontend")
        for name in archive.namelist():
            if name.startswith("payload/") and not name.endswith("/"):
                target = tmp_path / name.removeprefix("payload/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(name))
    result = subprocess.run([sys.executable, "-c", "import plugin; plugin.request=lambda *a: {}; assert plugin.render({})['style']=='embed'"],
                            cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
