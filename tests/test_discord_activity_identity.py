"""OAuth identity cannot be substituted by a client's claimed Discord user or room."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture
def adapter(monkeypatch):
    spec = importlib.util.spec_from_file_location("discord_activity_identity", ROOT / "official/discord-bot-notifications/plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "_bot_config", lambda: {"token": "bot-secret", "guild_id": "123456789012345678"})
    monkeypatch.setattr(module, "_load", lambda key, default=None: {"application_id": "1558455437035053158", "client_secret": "oauth-secret"})
    return module


def test_bootstrap_uses_oauth_user_and_verified_instance(adapter, monkeypatch):
    calls = []
    def gateway(method, capability, payload):
        calls.append(payload)
        assert payload["headers"]["User-Agent"] == adapter.DISCORD_USER_AGENT
        if payload["url"].endswith("/oauth2/token"):
            assert "client_secret=oauth-secret" in payload["text_body"]
            return {"status": 200, "data": {"access_token": "user-access-token"}}
        assert payload["headers"]["Authorization"] == "Bearer user-access-token"
        return {"status": 200, "data": {"id": "222222222222222222", "username": "participant"}}
    monkeypatch.setattr(adapter, "request", gateway)
    monkeypatch.setattr(adapter, "_discord", lambda *args: {
        "application_id": "1558455437035053158", "instance_id": "i-room",
        "users": ["222222222222222222"], "location": {"guild_id": "123456789012345678"}})
    result = adapter.authenticate_activity({"proof": {"code": "authorization", "instance_id": "i-room"}})
    assert result["subject"] == "222222222222222222" and result["verified"]
    assert "oauth-secret" not in str(result) and "bot-secret" not in str(result)


@pytest.mark.parametrize("change", [{"users": []}, {"application_id": "different"},
    {"instance_id": "other-room"}, {"location": {"guild_id": "other-server"}}])
def test_membership_rejects_other_subject_application_room_or_server(adapter, monkeypatch, change):
    instance = {"application_id": "1558455437035053158", "instance_id": "i-room",
        "users": ["222222222222222222"], "location": {"guild_id": "123456789012345678"}, **change}
    monkeypatch.setattr(adapter, "_discord", lambda *args: instance)
    with pytest.raises(adapter.PluginError, match="Join"):
        adapter.revalidate_activity({"subject": "222222222222222222", "room": "i-room"})


def test_client_cannot_supply_identity_in_place_of_oauth(adapter):
    with pytest.raises(adapter.PluginError, match="authorization code"):
        adapter.authenticate_activity({"proof": {"code": "code", "instance_id": "i-room", "subject": "spoofed"}})
