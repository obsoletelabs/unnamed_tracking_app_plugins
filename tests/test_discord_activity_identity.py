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


@pytest.mark.parametrize("avatar", [None, "abcdef"])
def test_bootstrap_uses_oauth_user_and_verified_instance(adapter, monkeypatch, avatar):
    calls = []
    def gateway(method, capability, payload):
        calls.append(payload)
        assert payload["headers"]["User-Agent"] == adapter.DISCORD_USER_AGENT
        if payload["url"].endswith("/oauth2/token"):
            assert "client_secret=oauth-secret" in payload["text_body"]
            return {"status": 200, "data": {"access_token": "user-access-token"}}
        assert payload["headers"]["Authorization"] == "Bearer user-access-token"
        return {"status": 200, "data": {"id": "222222222222222222", "username": "participant", "avatar": avatar}}
    monkeypatch.setattr(adapter, "request", gateway)
    monkeypatch.setattr(adapter, "_discord", lambda *args: {
        "application_id": "1558455437035053158", "instance_id": "i-room",
        "users": ["222222222222222222"], "location": {"kind": "gc", "channel_id": "333333333333333333", "guild_id": "123456789012345678"}})
    result = adapter.authenticate_activity({"proof": {"code": "authorization", "instance_id": "i-room"}})
    assert result["subject"] == "222222222222222222" and result["verified"]
    assert result["avatar_url"].startswith("https://cdn.discordapp.com/")
    assert ("/avatars/222222222222222222/abcdef.png" in result["avatar_url"]) is bool(avatar)
    assert "oauth-secret" not in str(result) and "bot-secret" not in str(result)


@pytest.mark.parametrize("change", [{"users": []}, {"application_id": "different"},
    {"instance_id": "other-room"}, {"location": {"kind": "gc", "channel_id": "333333333333333333", "guild_id": "other-server"}}])
def test_membership_rejects_other_subject_application_room_or_server(adapter, monkeypatch, change):
    instance = {"application_id": "1558455437035053158", "instance_id": "i-room",
        "users": ["222222222222222222"], "location": {"kind": "gc", "channel_id": "333333333333333333", "guild_id": "123456789012345678"}, **change}
    monkeypatch.setattr(adapter, "_discord", lambda *args: instance)
    with pytest.raises(adapter.PluginError, match="Join"):
        adapter.revalidate_activity({"subject": "222222222222222222", "room": "i-room"})


def test_client_cannot_supply_identity_in_place_of_oauth(adapter):
    with pytest.raises(adapter.PluginError, match="authorization code"):
        adapter.authenticate_activity({"proof": {"code": "code", "instance_id": "i-room", "subject": "spoofed"}})


def test_private_rooms_require_opt_in_and_still_verify_the_exact_member(adapter, monkeypatch):
    config = {"application_id": "1558455437035053158", "client_secret": "oauth-secret",
              "allow_private_channels": False}
    monkeypatch.setattr(adapter, "_load", lambda *args: config)
    instance = {"application_id": config["application_id"], "instance_id": "private-room",
                "users": ["222222222222222222"], "location": {
                    "kind": "pc", "channel_id": "333333333333333333", "guild_id": None}}
    monkeypatch.setattr(adapter, "_discord", lambda *args: instance)
    values = {"subject": "222222222222222222", "room": "private-room"}
    with pytest.raises(adapter.PluginError, match="not enabled"):
        adapter.revalidate_activity(values)
    config["allow_private_channels"] = True
    assert adapter.revalidate_activity(values)["verified"]
    with pytest.raises(adapter.PluginError, match="Join"):
        adapter.revalidate_activity({**values, "subject": "444444444444444444"})
    instance["location"]["kind"] = "unknown"
    with pytest.raises(adapter.PluginError, match="not supported"):
        adapter.revalidate_activity(values)
    instance["location"] = {"kind": "gc", "channel_id": "333333333333333333", "guild_id": "other"}
    with pytest.raises(adapter.PluginError, match="configured server"):
        adapter.revalidate_activity(values)


def test_private_room_policy_can_keep_existing_oauth_secret(adapter, monkeypatch):
    saved = []
    monkeypatch.setattr(adapter, "_load", lambda *args: {
        "application_id": "1558455437035053158", "client_secret": "oauth-secret-long-fixture"})
    monkeypatch.setattr(adapter, "_actor", lambda *args, **kwargs: "admin")
    monkeypatch.setattr(adapter, "_discord", lambda *args: {"id": "1558455437035053158"})
    monkeypatch.setattr(adapter, "_store", lambda key, value: saved.append((key, value)))
    result = adapter.save_activity_oauth({"application_id": "1558455437035053158",
                                         "allow_private_channels": True})
    assert result == {"configured": True, "application_id": "1558455437035053158"}
    assert saved[0][1]["client_secret"] == "oauth-secret-long-fixture"
    assert saved[0][1]["allow_private_channels"] is True
    with pytest.raises(adapter.PluginError, match="client secret"):
        adapter.save_activity_oauth({"application_id": "555555555555555555"})
