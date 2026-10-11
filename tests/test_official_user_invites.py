"""The maintained contribution uses only public host auth primitives."""

import importlib.util
import json
from pathlib import Path

import pytest


@pytest.fixture
def plugin(monkeypatch):
    path = Path(__file__).parents[1] / "official/user-invites/plugin.py"
    spec = importlib.util.spec_from_file_location("official_invites", path)
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
    assert module.enable({"token_lifetime_seconds": 7200}) == {"registered": True}
    assert calls[1] == ("auth_flows.user_invites.register", "auth.user_invites", {"mode": "user_invite", "name": "User Invites", "token_lifetime_seconds": 7200})
    assert json.loads(storage[module.KEY])["enabled"] is True
    assert {capability for _, capability, _ in calls} == {"auth.user_invites", "plugin.storage"}


@pytest.mark.parametrize("lifetime", [True, "86400", 86400.5, 3599, 604801, None])
def test_host_lifetime_bounds_are_validated_without_sending_invalid_requests(plugin, lifetime):
    module, calls, _ = plugin
    with pytest.raises(ValueError):
        module.enable({"token_lifetime_seconds": lifetime})
    assert not any(method.startswith("auth_flows.") for method, _, _ in calls)


def test_installation_starts_disabled_and_explicit_activation_survives_restart(plugin):
    module, calls, _ = plugin
    module.restore_configuration()
    assert all(method != "auth_flows.user_invites.register" for method, _, _ in calls)
    module.enable({})
    calls.clear()
    module.restore_configuration()
    assert calls[-1][0] == "auth_flows.user_invites.restore"
    module.disable({})
    assert ("auth_flows.user_invites.unregister", "auth.user_invites", {}) in calls
    calls.clear()
    module.restore_configuration()
    assert all(method != "auth_flows.user_invites.register" for method, _, _ in calls)


def test_failed_host_activation_does_not_persist_enabled_configuration(plugin, monkeypatch):
    module, _, storage = plugin
    def reject(method, capability, payload):
        raise PermissionError("Missing administrator authority")
    monkeypatch.setattr(module, "request", reject)
    with pytest.raises(PermissionError):
        module.enable({})
    assert not storage


def test_declared_admin_controls_and_signed_official_identity():
    source = Path(__file__).parents[1] / "official/user-invites"
    manifest = json.loads((source / "manifest.json").read_text())
    document = json.loads((source / "ui.json").read_text())
    assert manifest["plugin_id"] == "official.user-invites"
    assert manifest["api_contract_version"] == document["api_contract_version"] == "1.1.11"
    assert {item["name"] for item in manifest["capabilities"]} == {"auth.user_invites", "plugin.storage", "frontend.navigation.admin", "frontend.settings"}
    assert not document["settings_sections"]
    assert json.loads((source / "release.json").read_text())["publisher"] == "Unnamed Tracking Official"


def test_admin_actions_forward_only_scoped_inputs(plugin):
    module, calls, _ = plugin
    module.issue({"email": "recipient@example.test", "is_admin": True, "smtp_password": "unrelated"})
    module.list_invites({"user_id": "someone-else"})
    module.status({"include_tokens": True})
    module.revoke({"id": "invite-id", "token": "must-not-forward"})
    assert calls == [
        ("auth_flows.user_invites.issue", "auth.user_invites", {"email": "recipient@example.test"}),
        ("auth_flows.user_invites.list", "auth.user_invites", {}),
        ("auth_flows.user_invites.status", "auth.user_invites", {}),
        ("storage.get", "plugin.storage", {"key": module.KEY}),
        ("auth_flows.user_invites.revoke", "auth.user_invites", {"id": "invite-id"}),
    ]


def test_plugin_owned_admin_ui_uses_public_bridge_and_safe_text_rendering():
    source = Path(__file__).parents[1] / "official/user-invites"
    manifest = json.loads((source / "manifest.json").read_text())
    assert manifest["frontend"]["entry"] == "frontend/index.html"
    assert manifest["frontend"]["inline_assets"] is True
    script = (source / "frontend/app.js").read_text()
    assert "plugin.run-action" in script and "textContent" in script
    assert "fetch(" not in script and "innerHTML" not in script




def test_sandbox_controls_use_bridge_instead_of_blocked_native_form_navigation():
    source = Path(__file__).parents[1] / "official/user-invites/frontend"
    html = (source / "index.html").read_text()
    script = (source / "app.js").read_text()
    assert 'type="submit"' not in html
    assert "form.reportValidity()" in script and "event.preventDefault()" in script

def test_invite_action_is_a_user_admin_dialog_and_configuration_is_separate():
    source = Path(__file__).parents[1] / "official/user-invites"
    document = json.loads((source / "ui.json").read_text())
    assert document["extensions"] == [
        {"id": "invite-user", "slot": "administration.users.actions", "page_id": "invite"},
        {"id": "configuration", "slot": "administration.users.settings", "page_id": "configure"},
    ]
    assert not document["settings_sections"]
    assert not document["navigation"]
    page = next(p for p in document["pages"] if p["id"] == "invite")
    assert "enable" not in page["actions"]


def test_save_while_disabled_keeps_settings_without_enabling_and_disable_preserves_them(plugin):
    module, calls, storage = plugin
    module.save({"token_lifetime_seconds": 172800, "sender_name": "Library team", "welcome_message": "Welcome!"})
    saved = json.loads(storage[module.KEY])
    assert saved["enabled"] is False and saved["sender_name"] == "Library team"
    assert not any(method.endswith(".register") for method, _, _ in calls)
    module.enable({})
    assert calls[-2][2]["welcome_message"] == "Welcome!"
    module.disable({})
    disabled = json.loads(storage[module.KEY])
    assert disabled == {**saved, "enabled": False}
    assert module.status({})["token_lifetime_seconds"] == 172800


@pytest.mark.parametrize("values", [
    {"sender_name": "Team\r\nBcc: anyone"}, {"email_subject": " "},
    {"accent_color": "red"}, {"email_layout": "html"}, {"greeting": "unknown"},
    {"welcome_message": "x" * 2001},
])
def test_invalid_email_presentation_never_reaches_host_registration(plugin, values):
    module, calls, _ = plugin
    with pytest.raises(ValueError):
        module.enable(values)
    assert not any(method.startswith("auth_flows.") for method, _, _ in calls)
