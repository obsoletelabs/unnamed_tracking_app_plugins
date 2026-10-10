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

from sdk.notifications import register_provider
from sdk.plugin_protocol import GatewayRequestError, request

PLUGIN_ID = "official.discord-bot-notifications"
PROVIDER_ID = PLUGIN_ID + ".dm"
DISCORD_API = "https://discord.com/api/v10"
_USERNAME = re.compile(r"^[a-z0-9._]{2,32}$")
_SNOWFLAKE = re.compile(r"^[0-9]{17,20}$")
_LINK_TTL = 600
_MAX_LINK_STARTS_PER_HOUR = 5


class PluginError(ValueError):
    """Safe user-facing plugin action failure."""


def _actor(values: dict[str, Any], *, admin: bool = False) -> str:
    context = values.get("_plugin_context", {})
    if (
        not isinstance(context, dict)
        or not context.get("user_id")
        or (admin and context.get("is_admin") is not True)
    ):
        raise PluginError(
            "Administrator access is required."
            if admin
            else "Sign in to manage your Discord link."
        )
    return str(context["user_id"])


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
        "headers": {"Authorization": "Bot " + token},
    }
    if body is not None:
        payload["body"] = body
    response = request("network.request", "network.outbound", payload)
    status = response.get("status", 0)
    if not isinstance(status, int):
        raise PluginError("Discord returned an invalid response.")
    if status < 200 or status >= 300:
        if status == 429 or status >= 500 or status == 0:
            raise PluginError("Discord is temporarily unavailable. Try again later.")
        if status in {401, 403}:
            raise PluginError("Discord rejected the bot token or the bot lacks server access.")
        if status == 404:
            raise PluginError("Discord could not find that server or destination.")
        raise PluginError("Discord rejected the request. Check the bot setup and try again.")
    return response.get("data")


def _send_dm(token: str, discord_user_id: str, content: str) -> None:
    channel = _discord(token, "POST", "/users/@me/channels", {"recipient_id": discord_user_id})
    channel_id = channel.get("id") if isinstance(channel, dict) else None
    if not isinstance(channel_id, str) or not _SNOWFLAKE.fullmatch(channel_id):
        raise PluginError("Discord did not create a direct-message channel.")
    _discord(
        token,
        "POST",
        f"/channels/{channel_id}/messages",
        {"content": content[:1900], "allowed_mentions": {"parse": []}},
    )


def _start_link(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values)
    username = values.get("username")
    if not isinstance(username, str) or not _USERNAME.fullmatch(username.lower()):
        raise PluginError("Enter your Discord username (2–32 letters, numbers, dots or underscores).")
    attempts_key = "link-attempts/" + user_id
    now = int(time.time())
    attempts = _load(attempts_key, {"window": now, "count": 0})
    if not isinstance(attempts, dict):
        attempts = {"window": now, "count": 0}
    if now - int(attempts.get("window", 0)) >= 3600:
        attempts = {"window": now, "count": 0}
    if int(attempts.get("count", 0)) >= _MAX_LINK_STARTS_PER_HOUR:
        raise PluginError("Too many link attempts. Wait an hour and try again.")
    attempts["count"] = int(attempts.get("count", 0)) + 1
    _store(attempts_key, attempts)

    config = _bot_config()
    encoded = quote(username, safe="")
    members = _discord(
        config["token"],
        "GET",
        f"/guilds/{config['guild_id']}/members/search?query={encoded}&limit=10",
    )
    if not isinstance(members, list):
        raise PluginError("Discord returned an invalid server member list.")
    matches = [
        member
        for member in members
        if isinstance(member, dict)
        and isinstance(member.get("user"), dict)
        and str(member["user"].get("username", "")).casefold() == username.casefold()
        and isinstance(member["user"].get("id"), str)
        and _SNOWFLAKE.fullmatch(member["user"]["id"])
    ]
    if len(matches) != 1:
        raise PluginError(
            "That username must match exactly one member of the configured Discord server. "
            "Check the spelling and ask an administrator to confirm the bot's server access."
        )
    discord_user = matches[0]["user"]
    code = f"{secrets.randbelow(100_000_000):08d}"
    expires_at = now + _LINK_TTL
    digest = hashlib.sha256(f"{user_id}:{code}:{expires_at}".encode()).hexdigest()
    _store(
        "pending-links/" + user_id,
        {
            "discord_id": discord_user["id"],
            "username": discord_user["username"],
            "code_digest": digest,
            "expires_at": expires_at,
        },
    )
    _send_dm(
        config["token"],
        discord_user["id"],
        f"Your account-link code is **{code}**. Enter it in the app within 10 minutes. "
        "If you did not request this, ignore this message.",
    )
    return {
        "ok": True,
        "message": "Verification code sent by DM. Enter it here within 10 minutes.",
    }


def _confirm_link(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values)
    code = values.get("code")
    if not isinstance(code, str) or not re.fullmatch(r"[0-9]{8}", code):
        raise PluginError("Enter the eight-digit code sent by Discord.")
    pending = _load("pending-links/" + user_id)
    now = int(time.time())
    if not isinstance(pending, dict) or int(pending.get("expires_at", 0)) <= now:
        _delete("pending-links/" + user_id)
        raise PluginError("The verification code expired. Start linking again.")
    digest = hashlib.sha256(
        f"{user_id}:{code}:{pending['expires_at']}".encode()
    ).hexdigest()
    if not hmac.compare_digest(digest, str(pending.get("code_digest", ""))):
        raise PluginError("The verification code is incorrect.")
    _store(
        "links/" + user_id,
        {
            "discord_id": pending["discord_id"],
            "username": pending["username"],
            "verified_at": now,
        },
    )
    _delete("pending-links/" + user_id)
    return {"ok": True, "message": "Discord account linked and verified."}


def get_config(values: dict[str, Any]) -> dict[str, Any]:
    context = values.get("_plugin_context", {})
    user_id = _actor(values)
    link = _load("links/" + user_id)
    result: dict[str, Any] = {
        "linked": isinstance(link, dict),
        "username": link.get("username", "") if isinstance(link, dict) else "",
    }
    if isinstance(context, dict) and context.get("is_admin") is True:
        config = _load("secrets/bot-config", {})
        result.update(
            {
                "is_admin": True,
                "bot_configured": bool(isinstance(config, dict) and config.get("token")),
                "guild_id": config.get("guild_id", "") if isinstance(config, dict) else "",
                "bot_name": config.get("bot_name", "") if isinstance(config, dict) else "",
            }
        )
    else:
        result["is_admin"] = False
    return result


def save_bot_config(values: dict[str, Any]) -> dict[str, Any]:
    _actor(values, admin=True)
    token = values.get("token")
    guild_id = values.get("guild_id")
    if not isinstance(token, str) or not 20 <= len(token.strip()) <= 512:
        raise PluginError("Enter a valid Discord bot token.")
    token = token.strip()
    if not isinstance(guild_id, str) or not _SNOWFLAKE.fullmatch(guild_id):
        raise PluginError("Enter the numeric Discord server ID.")
    me = _discord(token, "GET", "/users/@me")
    if not isinstance(me, dict) or not isinstance(me.get("id"), str):
        raise PluginError("Discord did not return a valid bot identity.")
    guild = _discord(token, "GET", f"/guilds/{guild_id}")
    if not isinstance(guild, dict) or guild.get("id") != guild_id:
        raise PluginError("The bot cannot access that Discord server.")
    _store(
        "secrets/bot-config",
        {"token": token, "guild_id": guild_id, "bot_name": str(me.get("username", "Discord bot"))[:100]},
    )
    return {"ok": True, "message": "Discord bot configuration saved. The token will not be shown again."}


def clear_bot_token(values: dict[str, Any]) -> dict[str, Any]:
    _actor(values, admin=True)
    _delete("secrets/bot-config")
    return {"ok": True, "message": "Bot token and server configuration removed. User links were retained."}


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
    context = values.get("_plugin_context", {})
    user_id = _actor(values)
    if not isinstance(context, dict):
        return {"success": False, "retryable": False, "error": "recipient_context_missing"}
    config = _load("secrets/bot-config", {})
    link = _load("links/" + user_id)
    if not isinstance(config, dict) or not config.get("token"):
        return {"success": False, "retryable": False, "error": "bot_not_configured"}
    if not isinstance(link, dict) or not link.get("discord_id"):
        return {"success": False, "retryable": False, "error": "recipient_not_linked"}
    delivery = values.get("delivery")
    if not isinstance(delivery, dict):
        return {"success": False, "retryable": False, "error": "delivery_invalid"}
    title = str(delivery.get("title", "Notification"))[:250]
    body = str(delivery.get("body", ""))[:1500]
    content = f"**{title}**\n{body}".strip()[:1900]
    try:
        _send_dm(str(config["token"]), str(link["discord_id"]), content or "Notification")
    except PluginError as exc:
        retryable = "temporarily unavailable" in str(exc).lower()
        return {
            "success": False,
            "retryable": retryable,
            "error": "discord_temporarily_unavailable" if retryable else "discord_delivery_failed",
        }
    return {"success": True, "retryable": False}


def _register_provider() -> None:
    delay = 1
    while True:
        try:
            register_provider(PROVIDER_ID, "Discord Bot DM", "deliver", transport="discord_bot_dm")
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
