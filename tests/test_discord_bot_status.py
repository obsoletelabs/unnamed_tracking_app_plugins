"""Own host destination proof and safe bot server discovery."""
import json
import shutil
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

from sdk import notifications
from test_discord_bot_destinations import load, OWNER, INSTALLATION


def test_status_sdk_uses_separate_grant_and_bounded_actorless_payload(monkeypatch):
    calls = []
    monkeypatch.setattr(notifications, "request", lambda *args: calls.append(args) or {"destinations": []})
    notifications.destination_status(provider_id="official.test.dm", limit=1)
    assert calls == [("notification_destinations.status", "notification_destinations.read", {
        "provider_id": "official.test.dm", "after": None, "limit": 1,
    })]
    for limit in [True, 0, 101]:
        with pytest.raises(ValueError):
            notifications.destination_status(limit=limit)
    with pytest.raises(ValueError):
        notifications.destination_status(after="not-a-cursor")


def test_destination_status_uses_host_proof_and_only_revision_matching_local_identity(monkeypatch):
    plugin = load()
    identity = str(uuid4())
    host = {"installation_id": INSTALLATION, "next_after": None, "destinations": [{
        "id": identity, "provider_id": plugin.ACCOUNT_PROVIDER_ID, "kind": "discord_account_dm",
        "revision": 3, "trust": "SECURE", "recovery_status": "eligible", "recovery_allowed": True,
    }]}
    record = {"user_id": OWNER, "revision": 3, "username": "casey", "discord_id": "123456789012345678", "token": "never-return"}
    monkeypatch.setattr(plugin, "destination_status", lambda **query: host)
    monkeypatch.setattr(plugin, "_load", lambda key, default=None: record if key == f"account-dm/destinations/{INSTALLATION}/{identity}" else default)
    result = plugin.get_destinations({"_plugin_context": {"user_id": OWNER}})
    assert result["destinations"][0]["trust"] == "SECURE"
    assert result["destinations"][0]["username"] == "casey"
    assert "never-return" not in json.dumps(result)
    for mutation in [{"user_id": str(uuid4())}, {"revision": 2}, {"retired": True}]:
        original = dict(record)
        record.update(mutation)
        result = plugin.get_destinations({"_plugin_context": {"user_id": OWNER}})
        assert "username" not in result["destinations"][0]
        record.clear(); record.update(original)
    with pytest.raises(plugin.PluginError):
        plugin.get_destinations({"user_id": OWNER})


def test_server_discovery_is_admin_only_bounded_and_does_not_return_token(monkeypatch):
    plugin = load()
    calls = []
    monkeypatch.setattr(plugin, "_bot_config", lambda: {"token": "stored-secret"})
    def discord(token, method, path):
        calls.append((token, method, path))
        return [{"id": "123456789012345678", "name": "Tracking", "token": "never-return"}, {"id": "invalid"}]
    monkeypatch.setattr(plugin, "_discord", discord)
    actor = {"_plugin_context": {"user_id": OWNER, "is_admin": True}}
    assert plugin.list_servers(actor) == {"servers": [{"id": "123456789012345678", "name": "Tracking"}], "next_after": None}
    assert calls == [("stored-secret", "GET", "/users/@me/guilds?limit=100&after=0")]
    plugin.list_servers({**actor, "token": "new-secret", "after": "123456789012345678"})
    assert calls[-1][0] == "new-secret"
    with pytest.raises(plugin.PluginError):
        plugin.list_servers({"_plugin_context": {"user_id": OWNER, "is_admin": False}})
    with pytest.raises(plugin.PluginError):
        plugin.list_servers({**actor, "after": "../other"})
    assert len(calls) == 2


def test_bot_native_status_and_selector_behaviour():
    node = shutil.which("node")
    assert node, "Node 22+ is required"
    result = subprocess.run([node, "--test", str(Path(__file__).with_name("discord_bot_status.test.mjs"))], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
