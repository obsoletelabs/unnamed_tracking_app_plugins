"""A startup provider can wait for the app while retaining permanent failures."""

import importlib.util
from pathlib import Path

import pytest

from sdk import notifications
from sdk.plugin_protocol import GatewayRequestError


def load_provider():
    """Import maintained plugin source without any host internals."""
    source = Path(__file__).parents[1] / "official/discord-notifications/plugin.py"
    spec = importlib.util.spec_from_file_location("startup_provider", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_registration_recovers_after_host_appears(monkeypatch, capsys):
    """Temporary failures back off, then the same idempotent registration succeeds."""
    provider = load_provider()
    calls = []
    delays = []

    def register(method, capability, payload):
        calls.append((method, capability, payload))
        if len(calls) < 8:
            raise GatewayRequestError("Host is starting.", {"code": "unavailable"})
        return {"registered": True}

    monkeypatch.setattr(notifications, "request", register)
    monkeypatch.setattr(provider.time, "sleep", delays.append)
    provider._register_provider()
    assert delays == [1, 2, 4, 8, 16, 30, 30]
    assert all(call == calls[0] for call in calls)
    assert calls[0][2]["provider_id"] == "official.discord-notifications.webhook"
    assert "Waiting for the host gateway" in capsys.readouterr().err


@pytest.mark.parametrize("code", ["forbidden", "invalid_request", "conflict", "internal", None])
def test_registration_does_not_retry_permanent_errors(monkeypatch, code):
    """A missing grant or permanent error is never hidden by the readiness wait."""
    provider = load_provider()
    delays = []

    def rejected(*_arguments):
        raise GatewayRequestError("Registration was rejected.", {"code": code})

    monkeypatch.setattr(notifications, "request", rejected)
    monkeypatch.setattr(provider.time, "sleep", delays.append)
    with pytest.raises(GatewayRequestError, match="Registration was rejected"):
        provider._register_provider()
    assert not delays
