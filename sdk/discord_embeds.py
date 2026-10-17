"""Deterministic Discord embed rendering for host-approved notification deliveries.

The host has already applied the recipient's projection, the declared capability limits and its
own sanitiser. This module only lays that content out within Discord's hard limits:

* at most 10 embeds and 6,000 characters across all embeds of one message;
* 256 characters per title, 4,096 per description, 25 fields of 256/1,024 characters;
* at most 5 link buttons in one action row (bots only; webhooks cannot carry components).

Truncation is deterministic (the same delivery always yields the same payload, so an edit of
an unchanged story is a no-op for Discord) and a cut description always ends with a link to the
live story page when the host supplied one. Nothing here reads storage, credentials or the
network, and no mention is ever allowed to ping (`allowed_mentions` parses nothing).
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

MAX_EMBEDS = 10
MAX_EMBED_CHARACTERS = 6000
# Leaves room for the footer and for characters Discord counts differently from Python.
EMBED_CHARACTER_BUDGET = 5800
MAX_TITLE = 256
MAX_DESCRIPTION = 4096
MAX_FIELDS = 25
MAX_FIELD_NAME = 256
MAX_FIELD_VALUE = 1024
MAX_BUTTONS = 5
MAX_BUTTON_LABEL = 80
MAX_BUTTON_URL = 512
MAX_ITEM_DESCRIPTION = 350
MAX_DIGEST_ITEMS = 8
MAX_IMAGES = 4
COLOR_NORMAL = 3430612
COLOR_CRITICAL = 15158332
ELLIPSIS = "…"
STORY_LINK_LABEL = "Open full story"

_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]")
_MASS_MENTION = re.compile(r"@(everyone|here)", re.IGNORECASE)
_SNOWFLAKE = re.compile(r"^[0-9]{17,20}$")
_REFERENCE_PART = re.compile(r"^[0-9]{1,20}$")
_ZERO_WIDTH = "​"


class DiscordRenderError(ValueError):
    """The delivery cannot be presented (malformed reference or content)."""


def clean(value: Any) -> str:
    """Text without control characters or mass-mention triggers."""
    text = value if isinstance(value, str) else ""
    return _MASS_MENTION.sub(lambda match: "@" + _ZERO_WIDTH + match.group(1), _CONTROL.sub("", text))


def truncate(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    return value if len(value) <= limit else value[: limit - 1].rstrip() + ELLIPSIS


def safe_url(value: Any, *, limit: int = 2048) -> str | None:
    """An http(s) URL without credentials or whitespace, otherwise None."""
    if not isinstance(value, str) or not value or len(value) > limit or any(c.isspace() for c in value):
        return None
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        return None
    return value


def _timestamp(value: Any) -> str | None:
    if type(value) is not int or not 0 < value < 253402300800:
        return None
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


def _fields(facts: Any) -> list[dict[str, Any]]:
    fields = []
    for fact in facts if isinstance(facts, list) else []:
        if not isinstance(fact, dict):
            continue
        name, value = clean(fact.get("label")).strip(), clean(fact.get("text")).strip()
        if name and value and len(fields) < MAX_FIELDS:
            fields.append({"name": truncate(name, MAX_FIELD_NAME), "value": truncate(value, MAX_FIELD_VALUE),
                           "inline": len(value) <= 40 and len(name) <= 40})
    return fields


def _buttons(delivery: dict[str, Any], link: str | None) -> list[dict[str, Any]]:
    """Link buttons: the live story page first, then the host-checked action links."""
    wanted = [(STORY_LINK_LABEL, link)] if link else []
    for action in delivery.get("actions") or []:
        if isinstance(action, dict):
            wanted.append((clean(action.get("label")).strip(), safe_url(action.get("url"), limit=MAX_BUTTON_URL)))
    buttons: list[dict[str, Any]] = []
    seen: set[str] = set()
    for label, url in wanted:
        url = safe_url(url, limit=MAX_BUTTON_URL)
        if label and url and url not in seen and len(buttons) < MAX_BUTTONS:
            seen.add(url)
            buttons.append({"type": 2, "style": 5, "label": truncate(label, MAX_BUTTON_LABEL), "url": url})
    return buttons


def _link_lines(delivery: dict[str, Any], link: str | None) -> str:
    """Webhooks cannot carry buttons, so the same links become a short markdown list."""
    lines = []
    seen: set[str] = set()
    pairs = ([(STORY_LINK_LABEL, link)] if link else []) + [
        (clean(a.get("label")).strip(), safe_url(a.get("url"))) for a in delivery.get("actions") or [] if isinstance(a, dict)
    ]
    for label, url in pairs:
        if label and url and url not in seen and len(lines) < MAX_BUTTONS:
            seen.add(url)
            lines.append(f"[{truncate(label.replace(']', ')').replace('[', '('), 60)}](<{url}>)")
    return "\n".join(lines)


def _characters(embed: dict[str, Any]) -> int:
    total = len(embed.get("title", "")) + len(embed.get("description", ""))
    total += len(embed.get("footer", {}).get("text", ""))
    for field in embed.get("fields", []):
        total += len(field["name"]) + len(field["value"])
    return total


FIELD_BUDGET = 2000
_TAIL = re.compile(r"\n\n\[" + re.escape(STORY_LINK_LABEL) + r"\]\(<[^>]*>\)$")


def _shrink_description(description: str, keep: int) -> str:
    """Cut to `keep` characters, never the closing link to the full live story."""
    tail = _TAIL.search(description)
    if tail is None:
        return truncate(description, keep) if keep > 0 else ""
    link = tail.group(0)
    room = keep - len(link)
    if room < 16:
        return link.strip()[: max(keep, 0)] if keep >= len(link.strip()) else ""
    return truncate(description[: tail.start()], room) + link


def _fit(embeds: list[dict[str, Any]]) -> None:
    """Shrink until Discord's per-message budget holds: facts first, then text from the end."""
    for embed in embeds:
        fields = embed.get("fields", [])
        while fields and sum(len(f["name"]) + len(f["value"]) for f in fields) > FIELD_BUDGET:
            fields.pop()
    excess = sum(map(_characters, embeds)) - EMBED_CHARACTER_BUDGET
    for embed in reversed(embeds):
        if excess <= 0:
            return
        description = embed.get("description", "")
        if description:
            embed["description"] = _shrink_description(description, max(0, len(description) - excess))
            excess -= len(description) - len(embed["description"])
        while excess > 0 and embed.get("fields"):
            removed = embed["fields"].pop()
            excess -= len(removed["name"]) + len(removed["value"])
        if not embed.get("description"):
            embed.pop("description", None)
        if not embed.get("fields"):
            embed.pop("fields", None)


def _description(body: str, link: str | None, extra: str, limit: int) -> str:
    text = body
    suffix = ""
    if extra:
        suffix = "\n\n" + extra
    tail = f"\n\n[{STORY_LINK_LABEL}](<{link}>)" if link else ""
    if len(text) + len(suffix) <= limit:
        return text + suffix
    # Cut the body, never the links that lead to the full live story.
    room = limit - len(suffix) - len(tail)
    if room < 32:
        suffix, room = "", limit - len(tail)
    return truncate(text, room) + tail + suffix if tail else truncate(text, room) + suffix


def render_delivery(delivery: dict[str, Any], *, components: bool) -> dict[str, Any]:
    """The message body for one `send`, `edit` or `follow_up` delivery.

    `components` is true for bot-created messages (link buttons) and false for webhooks (links are
    listed in the embed). The result never contains a mention that can notify anyone.
    """
    if not isinstance(delivery, dict):
        raise DiscordRenderError("Notification content is invalid.")
    title = clean(delivery.get("title")).strip()
    if not title:
        raise DiscordRenderError("Notification content is invalid.")
    body = clean(delivery.get("body")).strip()
    link = safe_url(delivery.get("link"))
    colour = COLOR_CRITICAL if delivery.get("urgency") == "critical" else COLOR_NORMAL
    items = [item for item in delivery.get("items") or [] if isinstance(item, dict)]
    shown = items[:MAX_DIGEST_ITEMS]
    extra = _link_lines(delivery, link) if not components else ""
    main: dict[str, Any] = {"title": truncate(title, MAX_TITLE), "color": colour}
    if link:
        main["url"] = link
    if shown:
        hidden = len(items) - len(shown)
        main["description"] = (f"And {hidden} more." if hidden else "") + (f"\n\n{extra}" if extra else "")
    else:
        main["description"] = _description(body, link, extra, MAX_DESCRIPTION)
    main["description"] = main.get("description", "").strip()
    if not main["description"]:
        del main["description"]
    fields = _fields(delivery.get("facts"))
    if fields:
        main["fields"] = fields
    stamp = _timestamp(delivery.get("event_at"))
    if stamp:
        main["timestamp"] = stamp
    operation = delivery.get("operation", "send")
    main["footer"] = {"text": "Updated · Tracking app" if operation == "edit" else "Tracking app"}
    embeds = [main]
    for item in shown:
        embed: dict[str, Any] = {"title": truncate(clean(item.get("title")).strip() or "Notification", MAX_TITLE),
                                 "color": colour}
        url = safe_url(item.get("url"))
        if url:
            embed["url"] = url
        text = clean(item.get("body")).strip()
        if text:
            embed["description"] = truncate(text, MAX_ITEM_DESCRIPTION)
        item_stamp = _timestamp(item.get("event_at"))
        if item_stamp:
            embed["timestamp"] = item_stamp
        embeds.append(embed)
    images = [url for url in map(safe_url, (delivery.get("images") or [])[:MAX_IMAGES]) if url]
    if images:
        main["image"] = {"url": images[0]}
        for url in images[1:]:
            if len(embeds) < MAX_EMBEDS:
                embeds.append({"image": {"url": url}, "color": colour, **({"url": link} if link else {})})
    _fit(embeds)
    message: dict[str, Any] = {"embeds": embeds, "allowed_mentions": {"parse": []}}
    if components:
        buttons = _buttons(delivery, link)
        message["components"] = [{"type": 1, "components": buttons}] if buttons else []
    return message


def render_text(delivery: dict[str, Any]) -> str:
    """Plain fallback for a channel where the bot cannot embed links (at most 2,000 characters)."""
    title = clean(delivery.get("title")).strip() or "Notification"
    link = safe_url(delivery.get("link"))
    tail = f"\n\n[{STORY_LINK_LABEL}](<{link}>)" if link else ""
    heading = f"**{truncate(title, 200)}**\n\n"
    body = clean(delivery.get("body")).strip()
    return heading + truncate(body, 2000 - len(heading) - len(tail)) + tail


def encode_reference(channel_id: str, message_id: str) -> str:
    if not _SNOWFLAKE.fullmatch(str(channel_id)) or not _SNOWFLAKE.fullmatch(str(message_id)):
        raise DiscordRenderError("Discord returned an unusable message reference.")
    return f"{channel_id}:{message_id}"


def decode_reference(reference: Any) -> tuple[str, str]:
    """Split an opaque `channel:message` reference; anything else is not ours to edit."""
    if not isinstance(reference, str) or reference.count(":") != 1:
        raise DiscordRenderError("The earlier Discord message reference is invalid.")
    channel_id, message_id = reference.split(":")
    if not _SNOWFLAKE.fullmatch(channel_id) or not _SNOWFLAKE.fullmatch(message_id):
        raise DiscordRenderError("The earlier Discord message reference is invalid.")
    return channel_id, message_id


def webhook_message_id(reference: Any) -> str:
    if not isinstance(reference, str) or not _SNOWFLAKE.fullmatch(reference):
        raise DiscordRenderError("The earlier Discord message reference is invalid.")
    return reference


def nonce(idempotency_key: Any) -> str | None:
    """Discord deduplicates a repeated create with the same nonce (25 characters at most)."""
    if not isinstance(idempotency_key, str):
        return None
    value = re.sub(r"[^A-Za-z0-9]", "", idempotency_key)[:25]
    return value or None
