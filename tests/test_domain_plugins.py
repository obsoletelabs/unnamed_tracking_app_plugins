from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))


def load_plugin(name: str):
    source = ROOT / "examples" / name / "plugin.py"
    spec = importlib.util.spec_from_file_location(f"domain_{name.replace('-', '_')}", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        (
            "scoped-document-viewer",
            {"documents.read", "backend.routes.plugin", "frontend.context.documents", "plugin.settings",
             "frontend.native", "frontend.settings", "frontend.navigation.settings",
             "frontend.placement.settings.admin"},
        ),
        (
            "self-service-session-manager",
            {
                "sessions.read",
                "sessions.revoke",
                "sessions.admin.read",
                "sessions.admin.revoke",
                "backend.routes.plugin",
                "frontend.page.replace.sessions",
                "frontend.page.replace.admin-sessions",
                "frontend.native",
                "sessions.geoip.read",
                "sessions.geoip.configure",
            },
        ),
        (
            "discord-delivery-provider",
            {
                "notification_providers.register",
                "notification_providers.deliver",
                "plugin.storage",
                "frontend.navigation.main",
            },
        ),
    ],
)
def test_domain_manifests_are_minimally_scoped(name: str, expected: set[str]) -> None:
    manifest = json.loads((ROOT / "examples" / name / "manifest.json").read_text(encoding="utf-8"))
    declared = {item["name"] for item in manifest["capabilities"]}
    requested = {item["capability"]["name"] for item in manifest["permissions"]}

    assert declared == expected
    assert requested == expected
    assert all(item["rationale"].strip() for item in manifest["permissions"])
    assert manifest["frontend"]["entry"] == "frontend/index.html"


def test_document_viewer_uses_opaque_public_document_methods(monkeypatch) -> None:
    plugin = load_plugin("scoped-document-viewer")
    calls = []
    monkeypatch.setattr(
        plugin,
        "request",
        lambda method, capability, payload: (
            calls.append((method, capability, payload))
            or ({"value": 0} if method == "settings.get" else {"documents": []})
        ),
    )

    assert plugin.list_documents({"limit": 500}) == {"documents": []}
    plugin.read_document({"document_id": "opaque-document-id"})

    assert calls == [
        ("documents.list", "documents.read", {"limit": 32}),
        ("settings.get", "plugin.settings", {"key": "max_preview_mb"}),
        (
            "documents.read",
            "documents.read",
            {
                "document_id": "opaque-document-id",
                "chunk_bytes": 24 * 1024,
                "max_bytes": 0,
            },
        ),
    ]
    source = (ROOT / "examples" / "scoped-document-viewer" / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "textContent = text" in source
    assert "DOMPurify.sanitize" in source
    assert "text/plain" in source


def test_document_viewer_namespaced_routes_keep_gateway_ownership_checks(
    monkeypatch,
) -> None:
    plugin = load_plugin("scoped-document-viewer")
    calls = []
    monkeypatch.setattr(
        plugin,
        "request",
        lambda method, capability, payload: (
            calls.append((method, capability, payload)) or {"documents": []}
        ),
    )

    listed = plugin.list_documents_route({"query": {"limit": ["25"]}})
    opened = plugin.read_document_route({"path_parameters": {"document_id": "opaque-document-id"}})

    assert listed == {"status_code": 200, "body": {"documents": []}}
    assert opened["status_code"] == 200
    assert calls == [
        ("documents.list", "documents.read", {"limit": 25, "offset": 0}),
        ("settings.get", "plugin.settings", {"key": "max_preview_mb"}),
        (
            "documents.read",
            "documents.read",
            {
                "document_id": "opaque-document-id",
                "chunk_bytes": 24 * 1024,
                "max_bytes": 0,
            },
        ),
    ]


def test_session_manager_separates_read_and_revoke_capabilities(monkeypatch) -> None:
    plugin = load_plugin("self-service-session-manager")
    calls = []
    monkeypatch.setattr(
        plugin,
        "request",
        lambda method, capability, payload: (
            calls.append((method, capability, payload)) or {"revoked": True}
        ),
    )

    plugin.list_sessions({})
    plugin.revoke_session(
        {
            "session_id": "00000000-0000-0000-0000-000000000001",
            "_plugin_context": {"confirmed": True},
        }
    )

    assert calls[0][:2] == ("sessions.list", "sessions.read")
    assert calls[1] == (
        "sessions.revoke",
        "sessions.revoke",
        {"session_id": "00000000-0000-0000-0000-000000000001", "confirmed": True},
    )
    ui = json.loads((ROOT / "examples" / "self-service-session-manager" / "ui.json").read_text(encoding="utf-8"))
    revoke = next(action for action in ui["actions"] if action["id"] == "revoke-session")
    assert revoke["confirmation"]


def test_session_manager_routes_preserve_self_service_and_admin_capabilities(
    monkeypatch,
) -> None:
    plugin = load_plugin("self-service-session-manager")
    calls = []
    monkeypatch.setattr(
        plugin,
        "request",
        lambda method, capability, payload: (
            calls.append((method, capability, payload)) or {"ok": True}
        ),
    )

    own = plugin.revoke_session_route(
        {
            "path_parameters": {"session_id": "00000000-0000-0000-0000-000000000001"},
            "body": {"confirmed": True},
        }
    )
    admin = plugin.revoke_admin_session_route(
        {
            "path_parameters": {"session_id": "00000000-0000-0000-0000-000000000002"},
            "body": {"confirmed": True},
        }
    )

    assert own["status_code"] == admin["status_code"] == 200
    assert calls == [
        (
            "sessions.revoke",
            "sessions.revoke",
            {"session_id": "00000000-0000-0000-0000-000000000001", "confirmed": True},
        ),
        (
            "sessions.admin.revoke",
            "sessions.admin.revoke",
            {"session_id": "00000000-0000-0000-0000-000000000002", "confirmed": True},
        ),
    ]
    manifest = json.loads(
        (ROOT / "examples" / "self-service-session-manager" / "manifest.json").read_text(encoding="utf-8")
    )
    admin_routes = [
        route for route in manifest["backend_routes"] if route["path"].startswith("admin/")
    ]
    assert admin_routes
    assert all(route["authorization"] == "admin" for route in admin_routes)


def test_delivery_provider_registers_namespaced_provider(monkeypatch) -> None:
    plugin = load_plugin("discord-delivery-provider")
    calls = []

    def fake_request(method, capability, payload):
        calls.append((method, capability, payload))
        raise StopIteration

    monkeypatch.setattr(plugin, "request", fake_request)
    with pytest.raises(StopIteration):
        plugin.main()

    assert calls == [
        (
            "notification_providers.register",
            "notification_providers.register",
            {
                "provider_id": "example.discord-delivery-provider.discord",
                "name": "Discord (plugin)",
                "action_id": "deliver",
            },
        )
    ]


def test_delivery_provider_returns_bounded_work_without_a_secret() -> None:
    plugin = load_plugin("discord-delivery-provider")
    result = plugin.deliver(
        {
            "delivery": {
                "notification_id": "notification-id",
                "title": "T" * 400,
                "body": "B" * 5000,
                "event_at": 1,
            }
        }
    )

    assert result["discord"] is True
    assert len(result["content"]) <= 2000
    assert "webhook" not in result


def test_delivery_provider_rejects_malformed_work() -> None:
    plugin = load_plugin("discord-delivery-provider")
    assert plugin.deliver({"delivery": {}}) == {
        "success": False,
        "retryable": False,
        "error": "Invalid delivery work.",
    }


def test_reference_frontends_use_only_the_host_bridge() -> None:
    for name in (
        "scoped-document-viewer",
        "self-service-session-manager",
        "discord-delivery-provider",
    ):
        script = (ROOT / "examples" / name / "frontend" / "app.js").read_text(encoding="utf-8")
        assert "plugin-api-request" in script
        assert "window.parent.postMessage" in script
        assert "fetch(" not in script
