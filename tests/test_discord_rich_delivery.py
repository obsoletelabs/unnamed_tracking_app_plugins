"""Rich Discord embeds, digests, edits and follow-ups through a fake Discord HTTP API (#112)."""
import copy
import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import jsonschema
import pytest

from fake_discord import FakeDiscord, embed_characters, violations
from sdk import discord_embeds
from test_discord_bot_channels import CHANNEL, authority
from test_discord_bot_destinations import ACCOUNTS, GUILD, INSTALLATION, OWNER, context, load, values

ROOT = Path(__file__).parents[1]
STORY = "https://app.example.test/notifications/stories/9d0f"
WEBHOOK = "https://discord.com/api/webhooks/123456789012345678/secret-token"


def canonical(**changes):
    document = {
        "notification_id": str(uuid4()), "event_type": "example.update", "title": "Update available",
        "body": "Version 2.0 is ready to install.", "event_at": 1760000000, "urgency": "normal",
        "link": STORY, "contract_version": "1.0.0", "operation": "send", "revision": 1,
        "remote_ref": None, "idempotency_key": uuid4().hex, "html": None,
        "actions": [{"label": "Release notes", "url": "https://example.com/notes"}],
        "images": ["https://example.com/cover.png"], "facts": [{"label": "Version", "text": "2.0"}, {"label": "Size", "text": "12 MB"}],
        "items": [],
    }
    document.update(changes)
    return document


# --- server channel (PUBLIC) and account DM (PRIVATE) bot providers -------------------------


@pytest.fixture
def bot(monkeypatch):
    plugin = load()
    storage, fake = {}, FakeDiscord()
    monkeypatch.setattr(plugin, "_load", lambda key, default=None: copy.deepcopy(storage.get(key, default)))
    monkeypatch.setattr(plugin, "_store", lambda key, record: storage.__setitem__(key, copy.deepcopy(record)))
    monkeypatch.setattr(plugin, "_bot_snapshot", lambda *args: {})
    monkeypatch.setattr(plugin, "_member_by_username", lambda token, guild, name: {"id": ACCOUNTS[name]} if name in ACCOUNTS else None)
    monkeypatch.setattr(plugin, "request", fake)
    plugin.allow_channels({"_plugin_context": {"user_id": OWNER, "is_admin": True}, "channel_ids": []}) if False else None
    storage["channel-policy/" + GUILD] = [{"id": CHANNEL, "name": "announcements"}]
    server = authority(plugin, scope="server")
    plugin.configure_channel_destination(values(server, {"token": "bot-one", "guild_id": GUILD}, admin=True))
    plugin.configure_account_destination(values(context(plugin, "configure", scope="server"), {"token": "bot-one", "guild_id": GUILD}, admin=True))
    return plugin, storage, fake


def channel_route(plugin, channel=CHANNEL):
    route = authority(plugin)
    plugin.configure_channel_destination(values(route, {"channel_id": channel}))
    return route


def account_route(plugin, name="casey"):
    route = context(plugin, "configure")
    plugin.configure_account_destination(values(route, {"username": name}))
    return route


def run(function, route, delivery, *, actor=OWNER):
    route = {**route, "operation": "deliver", "server_revision": 1, "attempt_id": str(uuid4())}
    route.pop("provider_id", None)
    payload = values(route, actor=actor)
    payload["delivery"] = delivery
    return function(payload)


def stored(fake, ref):
    channel, message = ref.split(":")
    return fake.messages[(channel, message)]["body"]


def test_a_story_is_rendered_as_an_embed_with_facts_image_and_link_buttons(bot):
    plugin, _, fake = bot
    result = run(plugin.deliver_channel, channel_route(plugin), canonical())
    assert result["success"] and result["remote_ref"].startswith(CHANNEL + ":")
    message = stored(fake, result["remote_ref"])
    embed = message["embeds"][0]
    assert embed["title"] == "Update available" and embed["url"] == STORY
    assert [(f["name"], f["value"]) for f in embed["fields"]] == [("Version", "2.0"), ("Size", "12 MB")]
    assert embed["image"] == {"url": "https://example.com/cover.png"}
    buttons = message["components"][0]["components"]
    assert [(b["label"], b["url"]) for b in buttons] == [("Open full story", STORY), ("Release notes", "https://example.com/notes")]
    assert message["allowed_mentions"] == {"parse": []} and violations(message, webhook=False) == []


def test_an_edit_changes_the_same_message_and_a_deleted_one_becomes_a_follow_up(bot):
    plugin, _, fake = bot
    route = channel_route(plugin)
    first = run(plugin.deliver_channel, route, canonical())
    reference = first["remote_ref"]
    edited = run(plugin.edit_channel, route, canonical(operation="edit", remote_ref=reference, revision=2, title="Update installed",
                                                       facts=[{"label": "Version", "text": "2.0"}, {"label": "Status", "text": "Installed"}]))
    assert edited == {"success": True, "retryable": False, "remote_ref": reference}
    body = stored(fake, reference)
    assert body["embeds"][0]["title"] == "Update installed" and body["embeds"][0]["footer"]["text"].startswith("Updated")
    assert len(fake.messages) == 1 and [c["method"] for c in fake.sent("PATCH")] == ["PATCH"]
    assert fake.sent("PATCH")[0]["body"]["content"] is None
    # The user deleted it in Discord: the edit is refused (gone) and the host sends a follow-up.
    fake.delete(CHANNEL, reference.split(":")[1])
    gone = run(plugin.edit_channel, route, canonical(operation="edit", remote_ref=reference, revision=3))
    assert gone == {"success": False, "retryable": False, "gone": True}
    follow = run(plugin.deliver_channel, route, canonical(operation="follow_up", remote_ref=reference, revision=3, title="Update: Update failed"))
    assert follow["success"] and follow["remote_ref"] != reference
    assert fake.sent("POST")[-1]["body"]["message_reference"] == {
        "message_id": reference.split(":")[1], "channel_id": CHANNEL, "fail_if_not_exists": False}


def test_references_are_bound_to_their_destination_and_bot(bot, monkeypatch):
    plugin, storage, fake = bot
    route = channel_route(plugin)
    reference = run(plugin.deliver_channel, route, canonical())["remote_ref"]
    # A reference of another channel is never edited, and no request is made for it.
    before = len(fake.calls)
    foreign = "523456789012345678:" + reference.split(":")[1]
    assert run(plugin.edit_channel, route, canonical(operation="edit", remote_ref=foreign)) ["gone"] is True
    assert run(plugin.edit_channel, route, canonical(operation="edit", remote_ref="not-a-reference"))["gone"] is True
    assert [c["method"] for c in fake.calls[before:]].count("PATCH") == 0
    # A second bot (token rotated or another installation) cannot change the first bot's message.
    storage[plugin._channel_server_key(route)]["token"] = "bot-two"
    assert run(plugin.edit_channel, route, canonical(operation="edit", remote_ref=reference)) == {"success": False, "retryable": False, "gone": True}
    assert fake.messages[(CHANNEL, reference.split(":")[1])]["body"]["embeds"][0]["title"] == "Update available"


def test_account_dm_edits_follow_the_linked_account_only(bot):
    plugin, storage, fake = bot
    route = account_route(plugin)
    first = run(plugin.deliver_account, route, canonical())
    channel = fake.dm_channels[("Bot bot-one", ACCOUNTS["casey"])]
    assert first["remote_ref"].startswith(channel + ":")
    assert run(plugin.edit_account, route, canonical(operation="edit", remote_ref=first["remote_ref"]))["success"]
    # Re-enrolling the destination for a different Discord account makes the old message foreign.
    storage[plugin._account_key(route)]["discord_id"] = ACCOUNTS["other"]
    assert run(plugin.edit_account, route, canonical(operation="edit", remote_ref=first["remote_ref"]))["gone"] is True


@pytest.mark.parametrize("change", ["retired", "revision", "owner", "installation"])
def test_revoked_or_unlinked_destinations_receive_no_later_update(bot, change):
    plugin, storage, fake = bot
    route = channel_route(plugin)
    reference = run(plugin.deliver_channel, route, canonical())["remote_ref"]
    calls = len(fake.calls)
    actor = OWNER
    if change == "retired":
        plugin.retire_channel_destination(values({**route, "operation": "retire"}))
    elif change == "revision":
        route["destination"]["revision"] += 1
    elif change == "owner":
        actor = str(uuid4())
    else:
        route["installation_id"] = str(uuid4())
    for function, document in ((plugin.edit_channel, canonical(operation="edit", remote_ref=reference)), (plugin.deliver_channel, canonical())):
        assert not run(function, route, document, actor=actor)["success"]
    assert len(fake.calls) == calls


def test_rate_limits_and_server_errors_are_retryable_without_losing_or_duplicating(bot):
    plugin, _, fake = bot
    route = channel_route(plugin)
    document = canonical()
    fake.fail_next(429, retry_after=2)
    limited = run(plugin.deliver_channel, route, document)
    assert limited["success"] is False and limited["retryable"] is True and not fake.messages
    ok = run(plugin.deliver_channel, route, document)
    assert ok["success"] and len(fake.messages) == 1
    # A repeat of the same obligation (crash after Discord accepted it) is deduplicated by nonce.
    again = run(plugin.deliver_channel, route, document)
    assert again["remote_ref"] == ok["remote_ref"] and len(fake.messages) == 1
    fake.fail_next(429, method="PATCH")
    edit = canonical(operation="edit", remote_ref=ok["remote_ref"], title="Changed")
    assert run(plugin.edit_channel, route, edit)["retryable"] is True
    assert stored(fake, ok["remote_ref"])["embeds"][0]["title"] == "Update available"
    fake.fail_next(503)
    assert run(plugin.deliver_channel, route, canonical())["retryable"] is True
    fake.fail_next(400, method="PATCH")
    assert run(plugin.edit_channel, route, edit) == {"success": False, "retryable": False, "error": "discord_channel_unavailable"}


def test_a_channel_without_embed_permission_gets_one_plain_message_with_suppressed_previews(bot):
    plugin, _, fake = bot
    fake.denied_embeds = True
    result = run(plugin.deliver_channel, channel_route(plugin), canonical())
    assert result["success"]
    message = stored(fake, result["remote_ref"])
    assert message["flags"] == 4 and "embeds" not in message and STORY in message["content"]


def test_a_digest_keeps_every_item_within_discord_limits(bot):
    plugin, _, fake = bot
    items = [{"title": f"Game {n} " + "x" * 300, "body": f"Release {n} " + "y" * 900, "event_at": 1760000000 + n,
              "url": f"https://app.example.test/notifications/stories/{n}"} for n in range(8)]
    result = run(plugin.deliver_channel, channel_route(plugin), canonical(items=items, title="8 new releases", facts=[], images=[], body="summary"))
    message = stored(fake, result["remote_ref"])
    assert len(message["embeds"]) == 9
    assert [e["title"].split(" x")[0] for e in message["embeds"][1:]] == [f"Game {n}" for n in range(8)]
    assert all(e["url"].endswith(f"/{n}") for n, e in enumerate(message["embeds"][1:]))
    assert sum(map(embed_characters, message["embeds"])) <= 6000
    # More members than one message can hold say so and keep the link to the full list.
    many = canonical(items=items + items[:3], title="11 new releases", facts=[], images=[], body="summary")
    shown = discord_embeds.render_delivery(many, components=True)
    assert shown["embeds"][0]["description"] == "And 3 more." and shown["embeds"][0]["url"] == STORY
    assert shown["components"][0]["components"][0]["url"] == STORY


def test_truncation_is_deterministic_and_keeps_the_story_link(bot):
    document = canonical(body="word " * 3000, facts=[{"label": "L" * 400, "text": "V" * 3000}] * 40,
                         images=[f"https://example.com/{n}.png" for n in range(9)])
    first = discord_embeds.render_delivery(document, components=True)
    assert first == discord_embeds.render_delivery(copy.deepcopy(document), components=True)
    embed = first["embeds"][0]
    assert len(embed["description"]) <= 4096 and embed["description"].endswith(f"[Open full story](<{STORY}>)")
    assert len(embed["fields"]) <= 25 and all(len(f["name"]) <= 256 and len(f["value"]) <= 1024 for f in embed["fields"])
    assert len(first["embeds"]) <= 10 and sum(map(embed_characters, first["embeds"])) <= 6000
    assert violations(first, webhook=False) == []


def test_text_is_neutralised_and_only_safe_links_survive():
    document = canonical(title="@everyone urgent\x00", body="ping @here <@&123> now",
                         link="javascript:alert(1)", actions=[{"label": "Bad", "url": "ftp://x"}, {"label": "Good", "url": "https://example.com/ok"}],
                         images=["javascript:x", "https://example.com/i.png"], html="<script>alert(1)</script>", user_id="never", email="a@b.c")
    message = discord_embeds.render_delivery(document, components=True)
    text = json.dumps(message)
    assert "@everyone" not in text and "@here" not in text and "\x00" not in text
    for forbidden in ("javascript:", "ftp://", "<script", "never", "a@b.c"):
        assert forbidden not in text
    assert message["allowed_mentions"] == {"parse": []}
    assert [b["label"] for b in message["components"][0]["components"]] == ["Good"]
    assert "url" not in message["embeds"][0]


def test_the_bot_providers_declare_validated_capabilities():
    plugin = load()
    schema = json.loads((ROOT / "tools/schemas/notification-provider-v1.schema.json").read_bytes())
    for provider_id, name, action, definition in (
        (plugin.ACCOUNT_PROVIDER_ID, "Discord account DM", "deliver-account", plugin.ACCOUNT_DEFINITION),
        (plugin.CHANNEL_PROVIDER_ID, "Discord server channel", "deliver-channel", plugin.CHANNEL_DEFINITION),
    ):
        jsonschema.validate({"provider_id": provider_id, "name": name, "action_id": action, "transport": "plugin", "definition": definition}, schema)
        capabilities = definition["capabilities"]
        assert capabilities["message_updates"] == "edit" and definition["edit_action"] in {"edit-account", "edit-channel"}
        assert capabilities["action_buttons"] <= discord_embeds.MAX_BUTTONS
        assert capabilities["max_batch_items"] <= discord_embeds.MAX_DIGEST_ITEMS and capabilities["max_title_chars"] == 256
        assert capabilities["threaded_follow_ups"] is True and capabilities["rich_embeds"] is True


# --- webhooks (PUBLIC) -----------------------------------------------------------------------


def load_webhook():
    spec = importlib.util.spec_from_file_location("discord_webhook_rich", ROOT / "official/discord-notifications/plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hook(monkeypatch):
    plugin, fake, storage = load_webhook(), FakeDiscord(), {}

    def request(method, capability, payload):
        if method == "storage.get":
            return {"value": storage.get(payload["key"])}
        if method == "storage.put":
            storage[payload["key"]] = payload["value"]
            return {}
        return fake(method, capability, payload)

    monkeypatch.setattr(plugin, "request", request)
    return plugin, fake, storage


def webhook_values(plugin, destination, delivery, operation="deliver", url=WEBHOOK, revision=1):
    authority = {"operation": operation, "scope": "destination", "provider_id": plugin.PROVIDER_ID, "installation_id": INSTALLATION,
                 "destination": {"id": destination, "revision": revision, "kind": "discord_webhook"}}
    if operation == "deliver":
        authority = {key: value for key, value in authority.items() if key != "provider_id"}
        authority.update(attempt_id=str(uuid4()), server_revision=1)
    return {"_notification_context": authority, "configuration": {"url": url}, "delivery": delivery}


def enrolled(plugin, url=WEBHOOK):
    destination = str(uuid4())
    assert plugin.configure(webhook_values(plugin, destination, None, "configure", url)) == {"configured": True}
    return destination


def test_webhook_messages_are_embeds_without_components_and_can_be_edited(hook):
    plugin, fake, _ = hook
    destination = enrolled(plugin)
    first = plugin.deliver(webhook_values(plugin, destination, canonical()))
    assert first["success"] and first["remote_ref"].isdigit()
    sent = fake.sent("POST")[0]
    assert sent["url"].endswith("?wait=true") and "components" not in sent["body"]
    assert "[Open full story](<" + STORY + ">)" in sent["body"]["embeds"][0]["description"]
    edited = plugin.edit(webhook_values(plugin, destination, canonical(operation="edit", remote_ref=first["remote_ref"], title="Installed")))
    assert edited == {"success": True, "retryable": False, "remote_ref": first["remote_ref"]}
    assert len(fake.messages) == 1 and fake.sent("PATCH")[0]["url"].endswith("/messages/" + first["remote_ref"])
    fake.delete("webhook:123456789012345678:secret-token", first["remote_ref"])
    assert plugin.edit(webhook_values(plugin, destination, canonical(operation="edit", remote_ref=first["remote_ref"]))) == {
        "success": False, "retryable": False, "gone": True}
    follow = plugin.deliver(webhook_values(plugin, destination, canonical(operation="follow_up", remote_ref=None)))
    assert follow["success"] and "message_reference" not in fake.sent("POST")[-1]["body"]


def test_webhooks_are_isolated_and_a_retired_one_receives_nothing(hook):
    plugin, fake, _ = hook
    first, second = enrolled(plugin), enrolled(plugin, "https://discord.com/api/webhooks/223456789012345678/other-token")
    reference = plugin.deliver(webhook_values(plugin, first, canonical()))["remote_ref"]
    # The second webhook cannot edit the first one's message: Discord reports it unknown.
    other = plugin.edit(webhook_values(plugin, second, canonical(operation="edit", remote_ref=reference)))
    assert other["gone"] is True and fake.messages[("webhook:123456789012345678:secret-token", reference)]["body"]["embeds"][0]["title"] == "Update available"
    assert plugin.edit(webhook_values(plugin, first, canonical(operation="edit", remote_ref="x/../y")))["gone"] is True
    plugin.retire(webhook_values(plugin, first, None, "retire"))
    calls = len(fake.calls)
    assert not plugin.edit(webhook_values(plugin, first, canonical(operation="edit", remote_ref=reference)))["success"]
    assert not plugin.deliver(webhook_values(plugin, first, canonical()))["success"]
    assert len(fake.calls) == calls


def test_webhook_rate_limits_and_failures_are_retryable_or_surfaced(hook):
    plugin, fake, _ = hook
    destination = enrolled(plugin)
    fake.fail_next(429, retry_after=3)
    assert plugin.deliver(webhook_values(plugin, destination, canonical())) == {"success": False, "retryable": True}
    fake.fail_next(502)
    assert plugin.deliver(webhook_values(plugin, destination, canonical()))["retryable"] is True
    fake.fail_next(400)
    assert plugin.deliver(webhook_values(plugin, destination, canonical())) == {"success": False, "retryable": False}
    reference = plugin.deliver(webhook_values(plugin, destination, canonical()))["remote_ref"]
    fake.fail_next(429, method="PATCH")
    assert plugin.edit(webhook_values(plugin, destination, canonical(operation="edit", remote_ref=reference)))["retryable"] is True


def test_the_webhook_test_message_and_unrelated_payloads_keep_the_minimal_form(hook):
    plugin, fake, _ = hook
    destination = enrolled(plugin)
    result = plugin.deliver(webhook_values(plugin, destination, {"notification_id": str(uuid4()), "event_type": "t", "title": "Test", "body": "Hello", "event_at": 1}))
    assert result == {"success": True, "retryable": False}
    sent = fake.sent("POST")[0]
    assert not sent["url"].endswith("wait=true") and sent["body"]["embeds"][0]["description"] == "Hello"


def test_the_webhook_declares_validated_capabilities():
    plugin = load_webhook()
    schema = json.loads((ROOT / "tools/schemas/notification-provider-v1.schema.json").read_bytes())
    jsonschema.validate({"provider_id": plugin.PROVIDER_ID, "name": "Discord Webhook", "action_id": "deliver", "transport": "plugin", "definition": plugin.DEFINITION}, schema)
    assert plugin.DEFINITION["destinations"][0]["privacy"] == "PUBLIC"
    assert plugin.DEFINITION["capabilities"]["threaded_follow_ups"] is False
    assert plugin.DEFINITION["edit_action"] == "edit"


@pytest.mark.parametrize("plugin_id", ["official.discord-notifications", "official.discord-bot-notifications"])
def test_packages_bundle_exactly_the_helpers_they_import(current_packages, plugin_id):
    import zipfile

    with zipfile.ZipFile(current_packages[plugin_id]) as archive:
        names = set(archive.namelist())
        assert {"payload/sdk/discord_embeds.py", "payload/sdk/notification_stories.py"} <= names
        assert archive.read("payload/sdk/discord_embeds.py") == (ROOT / "sdk/discord_embeds.py").read_bytes()
        manifest = json.loads(archive.read("manifest.json"))
    contract = "1.1.17" if plugin_id == "official.discord-bot-notifications" else "1.1.14"
    assert manifest["api_contract_version"] == contract
    assert manifest["sdk_version_range"] == "^" + contract
