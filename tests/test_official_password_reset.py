"""The maintained contribution uses only public host auth primitives."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def plugin(monkeypatch):
    path = Path(__file__).parents[1] / "official/password-reset/plugin.py"
    spec = importlib.util.spec_from_file_location("official_reset", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls, storage = [], {}
    def gateway(method, capability, payload):
        calls.append((method, capability, payload))
        if method == "storage.put":
            storage[payload["key"]] = payload["value"]
        if method == "storage.get":
            return {"value": storage.get(payload["key"])}
        return {"registered": method.endswith("register") and not method.endswith("unregister")}
    monkeypatch.setattr(module, "request", gateway)
    return module, calls, storage


def test_enable_has_no_credentials_account_queries_or_direct_notification_sender(plugin):
    module, calls, storage = plugin
    assert module.enable({"token_lifetime_seconds": 900}) == {"enabled": True, "token_lifetime_seconds": 900, "registered": True}
    assert calls[0] == ("auth_flows.password_reset.register", "auth.password_reset", {"mode": "password_reset", "name": "Password Reset", "token_lifetime_seconds": 900})
    assert json.loads(storage[module.KEY])["enabled"] is True
    assert {capability for _, capability, _ in calls} == {"auth.password_reset", "plugin.storage"}


@pytest.mark.parametrize("lifetime", [True, "1200", 1200.5, 599, 3601, None])
def test_host_lifetime_bounds_are_validated_without_sending_invalid_requests(plugin, lifetime):
    module, calls, _ = plugin
    with pytest.raises(ValueError):
        module.enable({"token_lifetime_seconds": lifetime})
    assert not calls


def test_installation_starts_disabled_and_explicit_activation_survives_restart(plugin):
    module, calls, _ = plugin
    module.restore_configuration()
    assert all(method != "auth_flows.password_reset.register" for method, _, _ in calls)
    module.enable({})
    calls.clear()
    module.restore_configuration()
    assert calls[-1][0] == "auth_flows.password_reset.restore"
    module.disable({})
    assert calls[-2] == ("auth_flows.password_reset.unregister", "auth.password_reset", {})
    calls.clear()
    module.restore_configuration()
    assert all(method != "auth_flows.password_reset.register" for method, _, _ in calls)


def test_failed_host_activation_does_not_persist_enabled_configuration(plugin, monkeypatch):
    module, _, storage = plugin
    def reject(method, capability, payload):
        raise PermissionError("Missing administrator authority")
    monkeypatch.setattr(module, "request", reject)
    with pytest.raises(PermissionError):
        module.enable({})
    assert not storage


def test_declared_admin_controls_and_signed_official_identity():
    source = Path(__file__).parents[1] / "official/password-reset"
    manifest = json.loads((source / "manifest.json").read_text())
    document = json.loads((source / "ui.json").read_text())
    assert manifest["plugin_id"] == "official.password-reset"
    assert manifest["api_contract_version"] == document["api_contract_version"] == "1.1.10"
    assert {item["name"] for item in manifest["capabilities"]} == {"auth.password_reset", "plugin.storage", "frontend.settings", "frontend.placement.settings.admin"}
    assert document["settings_sections"][0]["visibility"]["admin_only"] is True
    assert json.loads((source / "release.json").read_text())["publisher"] == "Unnamed Tracking Official"

def test_status_asks_the_host_instead_of_trusting_saved_activation(plugin):
    module, calls, storage = plugin
    storage[module.KEY] = json.dumps({"enabled": True})
    assert module.status({"include_tokens": True}) == {"registered": False}
    assert calls == [("auth_flows.password_reset.status", "auth.password_reset", {})]
