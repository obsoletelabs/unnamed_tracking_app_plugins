"""Parity contract tests; real authorization belongs to host HTTP tests."""

import json

import pytest
from test_domain_plugins import ROOT, load_plugin

SESSION_ID = "00000000-0000-0000-0000-000000000001"


def test_session_listing_forwards_filters_and_host_context(monkeypatch):
    plugin = load_plugin("extended-session-manager")
    calls = []
    monkeypatch.setattr(
        plugin,
        "request",
        lambda *args: calls.append(args) or {"sessions": [], "next_cursor": "next"},
    )
    result = plugin.list_sessions(
        {
            "q": "device",
            "state": "active",
            "country": "Australia",
            "anomaly": True,
            "cursor": SESSION_ID,
            "_plugin_context": {"session_id": SESSION_ID, "is_admin": True},
        }
    )
    assert result["is_admin"] is True and result["next_cursor"] == "next"
    assert calls[0] == (
        "sessions.list",
        "sessions.read",
        {
            "q": "device",
            "state": "active",
            "country": "Australia",
            "anomaly": True,
            "cursor": SESSION_ID,
            "limit": 200,
            "current_session_id": SESSION_ID,
        },
    )


@pytest.mark.parametrize(
    "handler",
    [
        "revoke_session",
        "revoke_all_sessions",
        "revoke_admin_session",
        "revoke_all_admin_sessions",
        "revoke_user_sessions",
    ],
)
def test_every_destructive_action_rejects_missing_confirmation(monkeypatch, handler):
    plugin = load_plugin("extended-session-manager")
    monkeypatch.setattr(
        plugin, "request", lambda *_args: pytest.fail("must not call gateway")
    )
    with pytest.raises(ValueError, match="confirmation"):
        getattr(plugin, handler)(
            {"session_id": SESSION_ID, "user_id": SESSION_ID, "confirmed": True}
        )


@pytest.mark.parametrize("value", [None, "", "invalid", "../../sessions", 1, [], {}])
def test_invalid_session_identifiers_never_reach_gateway(monkeypatch, value):
    plugin = load_plugin("extended-session-manager")
    monkeypatch.setattr(
        plugin, "request", lambda *_args: pytest.fail("must not call gateway")
    )
    result = plugin.revoke_session_route(
        {"path_parameters": {"session_id": value}, "body": {"confirmed": True}}
    )
    assert result["status_code"] == 422


def test_bulk_routes_use_distinct_self_service_and_admin_grants(monkeypatch):
    plugin = load_plugin("extended-session-manager")
    calls = []
    monkeypatch.setattr(
        plugin, "request", lambda *args: calls.append(args) or {"revoked": 1}
    )
    plugin.revoke_all_sessions_route({"body": {"confirmed": True}})
    plugin.revoke_user_sessions_route(
        {"body": {"confirmed": True}, "path_parameters": {"user_id": SESSION_ID}}
    )
    assert calls == [
        ("sessions.revoke_all", "sessions.revoke", {"confirmed": True}),
        (
            "sessions.admin.revoke_user",
            "sessions.admin.revoke",
            {"confirmed": True, "user_id": SESSION_ID},
        ),
    ]


def test_native_settings_and_all_destructive_actions_are_declared():
    root = ROOT / "official" / "extended-session-manager"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    ui = json.loads((root / "ui.json").read_text(encoding="utf-8"))
    from tools.distribution import version_key
    assert version_key(manifest["version"]) >= (2, 0, 0)
    assert manifest["native_frontend"]["entry"] == "native/index.js"
    assert {section["page"] for section in ui["page_replacements"]} == {
        "sessions",
        "admin-sessions",
    }
    assert not ui.get("settings_sections")
    assert all(item["page"] == item["page_id"] for item in ui["page_replacements"])
    assert all(
        action.get("confirmation")
        for action in ui["actions"]
        if action["id"].startswith("revoke")
    )
    assert not any(page.get("navigation") for page in ui["pages"])
    assert "api.full" not in {cap["name"] for cap in manifest["capabilities"]}
