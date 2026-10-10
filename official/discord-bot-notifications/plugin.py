"""Official Discord bot DM provider with verified per-user account links."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sys
import time
from typing import Any
from urllib.parse import quote
from uuid import UUID

from sdk.notifications import register_provider
from sdk.plugin_protocol import GatewayRequestError, request

PLUGIN_ID = "official.discord-bot-notifications"
PROVIDER_ID = PLUGIN_ID + ".dm"
DISCORD_API = "https://discord.com/api/v10"
_USERNAME = re.compile(r"^[a-z0-9._]{2,32}$")
_SNOWFLAKE = re.compile(r"^[0-9]{17,20}$")
_LINK_TTL = 600


class PluginError(ValueError):
    """Safe user-facing plugin action failure."""


def _actor(values: dict[str, Any], *, admin: bool = False) -> str:
    context = values.get("_plugin_context", {})
    if not isinstance(context, dict) or not context.get("user_id") or (admin and context.get("is_admin") is not True):
        raise PluginError("Administrator access is required." if admin else "Sign in to manage your Discord link.")
    try:
        return str(UUID(str(context["user_id"])))
    except (TypeError, ValueError, AttributeError):
        raise PluginError("Sign in to manage your Discord link.") from None


def _load(key: str, default: Any = None) -> Any:
    raw = request("storage.get", "plugin.storage", {"key": key}).get("value")
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        raise PluginError("Saved Discord configuration is damaged.") from None


def _store(key: str, value: Any) -> None:
    request("storage.put", "plugin.storage", {"key": key, "value": json.dumps(value)})


def _delete(key: str) -> None:
    request("storage.delete", "plugin.storage", {"key": key})


def _bot_config() -> dict[str, str]:
    config = _load("secrets/bot-config", {})
    token = config.get("token") if isinstance(config, dict) else None
    guild_id = config.get("guild_id") if isinstance(config, dict) else None
    if not isinstance(token, str) or not token or not isinstance(guild_id, str):
        raise PluginError("An administrator must configure the Discord bot token and server ID.")
    return {"token": token, "guild_id": guild_id}


def _discord(token: str, method: str, path: str, body: dict | None = None) -> Any:
    payload: dict[str, Any] = {
        "url": DISCORD_API + path,
        "method": method,
        "headers": {"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        "timeout_ms": 10000,
    }
    if body is not None:
        payload["json"] = body
    return request("network.request", "network.outbound", payload).get("json")


def _member_by_username(token: str, guild_id: str, username: str) -> dict[str, Any] | None:
    username = username.casefold()
    after = "0"
    while True:
        response = _discord(token, "GET", f"/guilds/{quote(guild_id)}/members?limit=1000&after={after}")
        if not isinstance(response, list):
            raise PluginError("Discord did not return the server member list.")
        for member in response:
            user = member.get("user", {}) if isinstance(member, dict) else {}
            if str(user.get("username", "")).casefold() == username:
                return user
        if len(response) < 1000:
            return None
        last = response[-1].get("user", {}).get("id")
        if not isinstance(last, str) or not _SNOWFLAKE.fullmatch(last):
            return None
        after = last


def _send_dm(token: str, discord_id: str, content: str) -> None:
    channel = _discord(token, "POST", "/users/@me/channels", {"recipient_id": discord_id})
    channel_id = channel.get("id") if isinstance(channel, dict) else None
    if not isinstance(channel_id, str):
        raise PluginError("Discord could not open a direct message channel.")
    _discord(token, "POST", f"/channels/{channel_id}/messages", {"content": content[:1900], "allowed_mentions": {"parse": []}})


def get_config(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values)
    config = _load("secrets/bot-config", {})
    link = _load("links/" + user_id, {})
    return {
        "configured": isinstance(config, dict) and bool(config.get("token") and config.get("guild_id")),
        "guild_id": str(config.get("guild_id", "")) if isinstance(config, dict) else "",
        "linked": isinstance(link, dict) and bool(link.get("discord_id")),
    }


def save_bot_config(values: dict[str, Any]) -> dict[str, Any]:
    _actor(values, admin=True)
    token = str(values.get("token", "")).strip()
    guild_id = str(values.get("guild_id", "")).strip()
    if not token or not _SNOWFLAKE.fullmatch(guild_id):
        raise PluginError("Enter a valid Discord bot token and server ID.")
    _store("secrets/bot-config", {"token": token, "guild_id": guild_id})
    return {"ok": True, "message": "Discord bot configuration saved."}


def clear_bot_token(values: dict[str, Any]) -> dict[str, Any]:
    _actor(values, admin=True)
    _delete("secrets/bot-config")
    return {"ok": True, "message": "Bot token and server configuration removed. User links were retained."}


def start_link(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values)
    config = _bot_config()
    username = str(values.get("username", "")).strip()
    if not _USERNAME.fullmatch(username):
        raise PluginError("Enter your Discord username exactly as shown by Discord.")
    member = _member_by_username(config["token"], config["guild_id"], username)
    if member is None or not _SNOWFLAKE.fullmatch(str(member.get("id", ""))):
        raise PluginError("That Discord username was not found in the configured server.")
    code = f"{secrets.randbelow(100_000_000):08d}"
    _store("pending-links/" + user_id, {"discord_id": str(member["id"]), "code_hash": hashlib.sha256(code.encode()).hexdigest(), "expires_at": int(time.time()) + _LINK_TTL, "attempts": 0})
    _send_dm(config["token"], str(member["id"]), f"Your verification code is **{code}**.")
    return {"ok": True, "message": "Verification code sent to your Discord DMs."}


def confirm_link(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values)
    pending = _load("pending-links/" + user_id)
    if not isinstance(pending, dict) or int(pending.get("expires_at", 0)) < int(time.time()):
        raise PluginError("Your verification code has expired. Start the link again.")
    attempts = int(pending.get("attempts", 0))
    if attempts >= 5:
        raise PluginError("Too many verification attempts. Start the link again.")
    code = str(values.get("code", ""))
    pending["attempts"] = attempts + 1
    _store("pending-links/" + user_id, pending)
    if not hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(), str(pending.get("code_hash", ""))):
        raise PluginError("That verification code is incorrect.")
    _store("links/" + user_id, {"discord_id": str(pending["discord_id"])})
    _delete("pending-links/" + user_id)
    return {"ok": True, "message": "Discord account linked."}


def unlink(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values)
    _delete("links/" + user_id)
    _delete("pending-links/" + user_id)
    return {"ok": True, "message": "Discord account unlinked."}


def test_dm(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values)
    config = _bot_config()
    link = _load("links/" + user_id)
    if not isinstance(link, dict) or not link.get("discord_id"):
        raise PluginError("Link and verify your Discord account first.")
    _send_dm(config["token"], link["discord_id"], "Discord notification test from your tracking app.")
    return {"ok": True, "message": "Test DM sent."}


def deliver(values: dict[str, Any]) -> dict[str, Any]:
    """Send only to the verified recipient mapped to the host-supplied user context."""
    try:
        user_id = _actor(values)
        delivery = values.get("delivery")
        if not isinstance(delivery, dict):
            return {"success": False, "retryable": False, "error": "delivery_invalid"}
        title = str(delivery.get("title", "Notification"))[:250]
        body = str(delivery.get("body", ""))[:1500]
        content = f"**{title}**\n{body}".strip()[:1900]
        config = _bot_config()
        link = _load("links/" + user_id)
        if not isinstance(link, dict) or not link.get("discord_id"):
            return {"success": False, "retryable": False, "error": "recipient_not_linked"}
        _send_dm(config["token"], str(link["discord_id"]), content or "Notification")
    except GatewayRequestError as exc:
        retryable = exc.code in {"unavailable", "rate_limited"}
        return {"success": False, "retryable": retryable, "error": "discord_gateway_unavailable" if retryable else "discord_permission_denied"}
    except PluginError as exc:
        return {"success": False, "retryable": False, "error": "discord_delivery_failed" if str(exc) else "discord_delivery_failed"}
    return {"success": True, "retryable": False}


def _register_provider() -> None:
    delay = 1
    while True:
        try:
            register_provider(PROVIDER_ID, "Discord Bot DM", "deliver", destination_kind="discord_bot_dm", privacy="PRIVATE")
            return
        except GatewayRequestError as exc:
            if exc.code != "unavailable":
                raise
            print("Waiting for the host gateway before registering Discord Bot DM.", file=sys.stderr, flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main() -> None:
    _register_provider()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
