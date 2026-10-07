from __future__ import annotations

import json
from pathlib import Path

import pytest

from sdk.plugin_protocol import route_query_value, route_response

from test_domain_plugins import plugin_root

ROOT = Path(__file__).parents[1]


def test_route_response_is_bounded_to_public_status_range() -> None:
    assert route_response({"ok": True}) == {
        "status_code": 200,
        "body": {"ok": True},
    }
    with pytest.raises(ValueError):
        route_response({}, 199)


def test_route_query_reads_only_normalized_values() -> None:
    assert route_query_value({"query": {"limit": ["25", "50"]}}, "limit") == "25"
    assert route_query_value({"query": {"limit": "25"}}, "limit") is None


def test_reference_backend_routes_are_namespaced_and_capability_declared() -> None:
    for name in ("scoped-document-viewer", "extended-session-manager"):
        manifest = json.loads((plugin_root(name) / "manifest.json").read_text(encoding="utf-8"))
        capabilities = {item["name"] for item in manifest["capabilities"]}
        assert "backend.routes.plugin" in capabilities
        assert manifest["backend_routes"]
        assert all(route["scope"] == "plugin" for route in manifest["backend_routes"])
        assert all(
            not route["path"].startswith("/") for route in manifest["backend_routes"]
        )


def test_plugins_remain_independent_of_host_source() -> None:
    for name in ("scoped-document-viewer", "extended-session-manager"):
        source = (plugin_root(name) / "plugin.py").read_text(encoding="utf-8")
        assert "src." not in source
        assert "sqlalchemy" not in source
        assert "fastapi" not in source
