"""Direct-message consent policy for the Discord bot provider (host issue #418).

A DM is opened only for a Discord account that the signed-in recipient enrolled
(or verified) for their own host account, and never after that consent is
withdrawn. These tests document the existing policy; they do not change it.
"""

from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import re
from uuid import uuid4

import pytest

ROOT = Path(__file__).parents[1]
PLUGIN_PATH = ROOT / "official/discord-bot-notifications/plugin.py"
GUILD = "123456789012345678"
ALICE, BOB = str(uuid4()), str(uuid4())
MEMBERS = {"alice": "223456789012345678", "bob": "323456789012345678", "victim": "423456789012345678"}
CREATE_DM = "/users/@me/channels"


def load():
    spec = importlib.util.spec_from_file_location("discord_dm_consent", PLUGIN_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def bot(monkeypatch):
    plugin = load()
    storage = {"secrets/bot-config": {"token": "legacy-token", "guild_id": GUILD}}
    dm_channels: list[str] = []

    def discord(token, method, path, body=None):
        if path == CREATE_DM:
            dm_channels.append(body["recipient_id"])
            return {"id": "523456789012345678"}
        return {"id": "623456789012345678"}

    monkeypatch.setattr(plugin, "_load", lambda key, default=None: copy.deepcopy(storage.get(key, default)))
    monkeypatch.setattr(plugin, "_store", lambda key, value: storage.__setitem__(key, copy.deepcopy(value)))
    monkeypatch.setattr(plugin, "_delete", lambda key: storage.pop(key, None))
    monkeypatch.setattr(plugin, "_discord", discord)
    monkeypatch.setattr(plugin, "_send_channel", lambda *args: None)
    monkeypatch.setattr(
        plugin, "_member_by_username",
        lambda token, guild, username: {"id": MEMBERS[username]} if username in MEMBERS else None,
    )
    return plugin, storage, dm_channels


def ctx(user, *, admin=False):
    return {"user_id": user, "is_admin": admin}


def notification(destination_id=None):
    return {"operation": "deliver", "destination": {"kind": "discord_bot_dm", "id": destination_id or str(uuid4()), "revision": 1}}


def deliver(plugin, user, *, admin=False):
    return plugin.deliver({
        "_plugin_context": ctx(user, admin=admin),
        "_notification_context": notification(),
        "delivery": {"title": "Private", "body": "Only for the enrolled recipient."},
    })


def test_only_two_helpers_can_open_a_dm_channel():
    source = PLUGIN_PATH.read_text(encoding="utf-8")
    assert len(re.findall(re.escape(CREATE_DM), source)) == 2  # _send_dm and _dm_channel_id


def test_enrolling_never_messages_the_target_and_unknown_members_store_nothing(bot):
    plugin, storage, dms = bot
    plugin.link_private({"_plugin_context": ctx(ALICE), "username": "alice"})
    with pytest.raises(plugin.PluginError, match="not found"):
        plugin.link_private({"_plugin_context": ctx(ALICE), "username": "stranger"})
    assert dms == []
    assert [a["discord_id"] for a in storage["links/" + ALICE]["accounts"]] == [MEMBERS["alice"]]


def test_unknown_username_sends_no_verification_dm(bot):
    plugin, storage, dms = bot
    with pytest.raises(plugin.PluginError, match="not found"):
        plugin.start_link({"_plugin_context": ctx(ALICE), "username": "stranger"})
    assert dms == [] and "pending-links/" + ALICE not in storage


def test_verification_code_is_bound_to_the_requesting_account_and_attempts_are_capped(bot):
    plugin, storage, dms = bot
    plugin.start_link({"_plugin_context": ctx(ALICE), "username": "victim"})
    assert dms == [MEMBERS["victim"]]  # the opt-in challenge goes only to the named member
    with pytest.raises(plugin.PluginError):  # another host user holds no challenge
        plugin.confirm_link({"_plugin_context": ctx(BOB), "code": "00000000"})
    for _ in range(5):
        with pytest.raises(plugin.PluginError, match="incorrect"):
            plugin.confirm_link({"_plugin_context": ctx(ALICE), "code": "00000000"})
    with pytest.raises(plugin.PluginError, match="Too many"):
        plugin.confirm_link({"_plugin_context": ctx(ALICE), "code": "00000000"})
    assert "links/" + ALICE not in storage


def test_delivery_uses_only_the_signed_in_users_own_enrolment(bot):
    plugin, storage, dms = bot
    plugin.link_private({"_plugin_context": ctx(ALICE), "username": "alice"})
    plugin.link_private({"_plugin_context": ctx(BOB), "username": "bob"})
    assert deliver(plugin, ALICE)["success"]
    assert dms == [MEMBERS["alice"]]
    # An administrator context does not widen the recipient set either.
    assert deliver(plugin, ALICE, admin=True)["success"]
    assert MEMBERS["bob"] not in dms


def test_test_dm_cannot_target_an_account_the_user_has_not_enrolled(bot):
    plugin, storage, dms = bot
    plugin.link_private({"_plugin_context": ctx(ALICE), "username": "alice"})
    plugin.link_private({"_plugin_context": ctx(BOB), "username": "bob"})
    for target in (MEMBERS["bob"], MEMBERS["victim"]):
        with pytest.raises(plugin.PluginError, match="linked Discord account"):
            plugin.test_dm({"_plugin_context": ctx(ALICE), "discord_id": target})
    assert dms == []
    plugin.test_dm({"_plugin_context": ctx(ALICE), "discord_id": MEMBERS["alice"]})
    assert dms == [MEMBERS["alice"]]


def test_unlinking_withdraws_consent_for_delivery_and_tests(bot):
    plugin, storage, dms = bot
    plugin.link_private({"_plugin_context": ctx(ALICE), "username": "alice"})
    plugin.link_private({"_plugin_context": ctx(ALICE), "username": "bob"})
    plugin.unlink({"_plugin_context": ctx(ALICE), "discord_id": MEMBERS["bob"]})
    assert deliver(plugin, ALICE)["success"]
    assert dms == [MEMBERS["alice"]]
    plugin.unlink({"_plugin_context": ctx(ALICE)})
    dms.clear()
    assert deliver(plugin, ALICE) == {"success": False, "retryable": False, "error": "recipient_not_linked"}
    with pytest.raises(plugin.PluginError, match="Select a linked"):
        plugin.test_dm({"_plugin_context": ctx(ALICE)})
    assert dms == []


def test_retiring_the_destination_withdraws_consent_and_pending_challenges(bot):
    plugin, storage, dms = bot
    plugin.link_private({"_plugin_context": ctx(ALICE), "username": "alice"})
    plugin.start_link({"_plugin_context": ctx(ALICE), "username": "bob"})
    dms.clear()
    plugin.retire_destination({"_plugin_context": ctx(ALICE)})
    assert "pending-links/" + ALICE not in storage
    assert not deliver(plugin, ALICE)["success"]
    assert dms == []


def test_delivery_requires_core_destination_context_and_a_signed_in_user(bot):
    plugin, storage, dms = bot
    plugin.link_private({"_plugin_context": ctx(ALICE), "username": "alice"})
    forged = plugin.deliver({"_plugin_context": ctx(ALICE), "delivery": {"title": "t", "body": "b"}})
    assert forged["error"] == "notification_context_invalid"
    assert deliver(plugin, "") == {"success": False, "retryable": False, "error": "discord_delivery_failed"}
    assert dms == []


def test_account_dm_enrolment_is_per_owner_and_unknown_members_are_not_stored(bot, monkeypatch):
    plugin, storage, dms = bot
    installation = str(uuid4())
    monkeypatch.setattr(plugin, "_bot_snapshot", lambda token, guild: {})

    def authority(operation, scope="destination", destination=None, revision=1):
        base = {"operation": operation, "scope": scope, "installation_id": installation}
        if operation == "deliver":
            base.update(server_revision=1, attempt_id=str(uuid4()))
        else:
            base["provider_id"] = plugin.ACCOUNT_PROVIDER_ID
        if scope == "server":
            base["revision"] = revision
        else:
            base["destination"] = {"id": destination or str(uuid4()), "revision": revision, "kind": "discord_account_dm"}
        return base

    plugin.configure_account_destination({
        "_notification_context": authority("configure", scope="server"), "_plugin_context": ctx(ALICE, admin=True),
        "configuration": {"token": "tok", "guild_id": GUILD},
    })
    mine = authority("configure")
    with pytest.raises(plugin.PluginError, match="not found"):
        plugin.configure_account_destination({"_notification_context": mine, "_plugin_context": ctx(ALICE),
                                              "configuration": {"username": "stranger"}})
    assert plugin._account_key(mine) not in storage
    plugin.configure_account_destination({"_notification_context": mine, "_plugin_context": ctx(ALICE),
                                          "configuration": {"username": "alice"}})
    assert dms == []

    payload = {"_notification_context": authority("deliver", destination=mine["destination"]["id"]),
               "delivery": {"title": "t", "body": "b", "link": None}}
    assert plugin.deliver_account({**payload, "_plugin_context": ctx(BOB)})["success"] is False
    assert dms == []
    assert plugin.deliver_account({**payload, "_plugin_context": ctx(ALICE)})["success"] is True
    assert dms == [MEMBERS["alice"]]

    retire = authority("retire", destination=mine["destination"]["id"], revision=2)
    plugin.retire_account_destination({"_notification_context": retire, "_plugin_context": ctx(ALICE)})
    assert plugin.deliver_account({**payload, "_plugin_context": ctx(ALICE)})["success"] is False
    assert dms == [MEMBERS["alice"]]


def test_channel_and_social_activity_plugins_never_open_dm_channels():
    for name in ("official/discord-social-activity", "official/discord-notifications"):
        for source in (ROOT / name).rglob("*.py"):
            assert CREATE_DM not in source.read_text(encoding="utf-8"), source
