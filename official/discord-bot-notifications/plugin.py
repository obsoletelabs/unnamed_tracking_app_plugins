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
    payload: dict[str, Any] = {"url": DISCORD_API + path, "method": method, "headers": {"Authorization": f"Bot {token}", "Content-Type": "application/json"}, "timeout_ms": 10000}
    if body is not None:
        payload["json"] = body
    return request("network.request", "network.outbound", payload).get("json")


def _member_by_username(token: str, guild_id: str, username: str) -> dict[str, Any] | None:
    username = username.casefold()
    after = "0"
    matches: list[dict[str, Any]] = []
    while True:
        response = _discord(token, "GET", f"/guilds/{quote(guild_id)}/members?limit=1000&after={after}")
        if not isinstance(response, list):
            raise PluginError("Discord did not return the server member list.")
        for member in response:
            user = member.get("user", {}) if isinstance(member, dict) else {}
            if str(user.get("username", "")).casefold() == username:
                matches.append(user)
                if len(matches) > 1:
                    raise PluginError("That Discord username matched more than one server member; use the unique Discord username.")
        if len(response) < 1000:
            return matches[0] if matches else None
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


def _avatar_url(user: dict[str, Any] | None, *, size: int = 256) -> str | None:
    if not isinstance(user, dict) or not user.get("id") or not user.get("avatar"):
        return None
    return f"https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png?size={size}"


def _permission_names(permission_value: int) -> list[str]:
    permissions = {
        1: "CREATE_INSTANT_INVITE", 2: "KICK_MEMBERS", 4: "BAN_MEMBERS", 8: "ADMINISTRATOR", 16: "MANAGE_CHANNELS", 32: "MANAGE_GUILD",
        1024: "VIEW_CHANNEL", 2048: "SEND_MESSAGES", 4096: "SEND_TTS_MESSAGES", 8192: "MANAGE_MESSAGES", 16384: "EMBED_LINKS", 32768: "ATTACH_FILES",
        65536: "READ_MESSAGE_HISTORY", 131072: "MENTION_EVERYONE", 262144: "USE_EXTERNAL_EMOJIS", 524288: "VIEW_GUILD_INSIGHTS", 1048576: "CONNECT",
        2097152: "SPEAK", 4194304: "MUTE_MEMBERS", 8388608: "DEAFEN_MEMBERS", 16777216: "MOVE_MEMBERS", 33554432: "USE_VAD",
        67108864: "PRIORITY_SPEAKER", 134217728: "STREAM", 268435456: "USE_APPLICATION_COMMANDS", 536870912: "MANAGE_THREADS", 1073741824: "USE_PUBLIC_THREADS",
        2147483648: "USE_PRIVATE_THREADS", 4294967296: "USE_EXTERNAL_STICKERS", 8589934592: "SEND_MESSAGES_IN_THREADS", 17179869184: "USE_EMBEDDED_ACTIVITIES",
        34359738368: "MODERATE_MEMBERS", 137438953472: "VIEW_AUDIT_LOG", 274877906944: "VIEW_GUILD_ANALYTICS", 1099511627776: "MANAGE_EVENTS",
        4398046511104: "VIEW_CREATOR_MONETIZATION_ANALYTICS", 8796093022208: "USE_SOUNDBOARD", 17592186044416: "CREATE_GUILD_EXPRESSIONS",
        35184372088832: "CREATE_EVENTS", 70368744177664: "USE_EXTERNAL_SOUNDS", 140737488355328: "SEND_VOICE_MESSAGES",
    }
    return [name for bit, name in permissions.items() if permission_value & bit]


def _bot_snapshot(token: str, guild_id: str) -> dict[str, Any]:
    started = time.monotonic()
    bot = _discord(token, "GET", "/users/@me")
    guild = _discord(token, "GET", f"/guilds/{quote(guild_id)}?with_counts=true")
    if not isinstance(bot, dict) or not bot.get("id"):
        raise PluginError("Discord did not return the configured bot identity.")
    bot_id = str(bot["id"])
    member = _discord(token, "GET", f"/guilds/{quote(guild_id)}/members/{quote(bot_id)}")
    roles = _discord(token, "GET", f"/guilds/{quote(guild_id)}/roles")
    elapsed_ms = round((time.monotonic() - started) * 1000)
    if not isinstance(guild, dict) or not guild.get("id"):
        raise PluginError("Discord could not read the configured server.")
    if not isinstance(member, dict):
        member = {}
    if not isinstance(roles, list):
        roles = []
    member_role_ids = [str(rid) for rid in member.get("roles", [])]
    if str(guild.get("id")) not in member_role_ids:
        member_role_ids.insert(0, str(guild.get("id")))
    role_by_id = {str(role.get("id")): role for role in roles if isinstance(role, dict)}
    role_names = [str(role_by_id[rid].get("name")) for rid in member_role_ids if rid in role_by_id]
    permission_value = 0
    for role_id in member_role_ids:
        role = role_by_id.get(role_id)
        if not isinstance(role, dict):
            continue
        try:
            permission_value |= int(role.get("permissions", "0"))
        except (TypeError, ValueError):
            continue
    return {
        "bot": {
            "id": bot_id, "username": str(bot.get("username", "")), "global_name": bot.get("global_name"), "discriminator": str(bot.get("discriminator", "0")),
            "avatar_url": _avatar_url(bot), "verified": bot.get("verified"), "bot": bot.get("bot") is True, "public_flags": bot.get("public_flags"),
            "invite_url": f"https://discord.com/oauth2/authorize?client_id={quote(bot_id)}&scope=bot%20applications.commands", "recommended_intents": ["GUILDS", "GUILD_MEMBERS"],
        },
        "guild": {
            "id": str(guild.get("id")), "name": str(guild.get("name", "")), "icon_url": f"https://cdn.discordapp.com/icons/{guild['id']}/{guild['icon']}.png?size=256" if guild.get("icon") else None,
            "description": guild.get("description"), "owner_id": guild.get("owner_id"), "member_count": guild.get("approximate_member_count"), "online_count": guild.get("approximate_presence_count"),
            "verification_level": guild.get("verification_level"), "premium_tier": guild.get("premium_tier"), "premium_subscription_count": guild.get("premium_subscription_count"),
            "premium_progress_bar_enabled": guild.get("premium_progress_bar_enabled"), "preferred_locale": guild.get("preferred_locale"), "features": guild.get("features", []), "nsfw_level": guild.get("nsfw_level"),
            "vanity_url_code": guild.get("vanity_url_code"), "afk_channel_id": guild.get("afk_channel_id"), "afk_timeout": guild.get("afk_timeout"), "system_channel_id": guild.get("system_channel_id"),
            "rules_channel_id": guild.get("rules_channel_id"), "public_updates_channel_id": guild.get("public_updates_channel_id"), "explicit_content_filter": guild.get("explicit_content_filter"),
            "default_message_notifications": guild.get("default_message_notifications"), "mfa_level": guild.get("mfa_level"), "widget_enabled": guild.get("widget_enabled"),
        },
        "bot_member": {"nickname": member.get("nick"), "joined_at": member.get("joined_at"), "pending": member.get("pending"), "role_names": role_names, "role_count": len(role_names), "permissions": permission_value, "permission_names": _permission_names(permission_value)},
        "health": {"api_ok": True, "request_ms": elapsed_ms},
    }


def get_config(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values)
    config = _load("secrets/bot-config", {})
    link = _load("links/" + user_id, {})
    result: dict[str, Any] = {"configured": isinstance(config, dict) and bool(config.get("token") and config.get("guild_id")), "bot_configured": isinstance(config, dict) and bool(config.get("token") and config.get("guild_id")), "guild_id": str(config.get("guild_id", "")) if isinstance(config, dict) else "", "linked": isinstance(link, dict) and bool(link.get("discord_id"))}
    if result["configured"]:
        try:
            result.update(_bot_snapshot(str(config["token"]), str(config["guild_id"])))
        except GatewayRequestError:
            result["health"] = {"api_ok": False}; result["bot_error"] = "Discord could not be reached right now."
        except PluginError as exc:
            result["health"] = {"api_ok": False}; result["bot_error"] = str(exc)
    if result["linked"] and result["configured"]:
        linked_id = str(link["discord_id"])
        try:
            linked_user = _discord(str(config["token"]), "GET", f"/users/{quote(linked_id)}")
            linked_member = _discord(str(config["token"]), "GET", f"/guilds/{quote(str(config['guild_id']))}/members/{quote(linked_id)}")
            if isinstance(linked_user, dict):
                result["username"] = linked_user.get("username", ""); result["global_name"] = linked_user.get("global_name"); result["discord_id"] = linked_id; result["avatar_url"] = _avatar_url(linked_user)
            if isinstance(linked_member, dict):
                result["server_nickname"] = linked_member.get("nick"); result["server_joined_at"] = linked_member.get("joined_at"); result["server_roles"] = linked_member.get("roles", [])
            result["linked_at"] = link.get("linked_at"); result["last_test_at"] = link.get("last_test_at"); result["last_delivery_at"] = link.get("last_delivery_at")
        except GatewayRequestError:
            result["link_warning"] = "The linked Discord account could not be refreshed."
    return result


def save_bot_config(values: dict[str, Any]) -> dict[str, Any]:
    _actor(values, admin=True)
    token = str(values.get("token", "")).strip(); guild_id = str(values.get("guild_id", "")).strip()
    if not token or not _SNOWFLAKE.fullmatch(guild_id):
        raise PluginError("Enter a valid Discord bot token and server ID.")
    snapshot = _bot_snapshot(token, guild_id)
    _store("secrets/bot-config", {"token": token, "guild_id": guild_id})
    return {"ok": True, "message": f"Connected as {snapshot['bot']['username']} to {snapshot['guild']['name']}."}


def clear_bot_token(values: dict[str, Any]) -> dict[str, Any]:
    _actor(values, admin=True); _delete("secrets/bot-config")
    return {"ok": True, "message": "Bot token and server configuration removed. User links were retained."}


def start_link(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values); config = _bot_config(); username = str(values.get("username", "")).strip()
    if not _USERNAME.fullmatch(username):
        raise PluginError("Enter your Discord username exactly as shown by Discord.")
    member = _member_by_username(config["token"], config["guild_id"], username)
    if member is None or not _SNOWFLAKE.fullmatch(str(member.get("id", ""))):
        raise PluginError("That Discord username was not found in the configured server.")
    code = f"{secrets.randbelow(100_000_000):08d}"
    _store("pending-links/" + user_id, {"discord_id": str(member["id"]), "code_hash": hashlib.sha256(code.encode()).hexdigest(), "expires_at": int(time.time()) + _LINK_TTL, "attempts": 0})
    _send_dm(config["token"], str(member["id"]), f"Your verification code is **{code}**.")
    return {"ok": True, "message": "Verification code sent to your Discord DMs.", "expires_in_seconds": _LINK_TTL}


def confirm_link(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values); pending = _load("pending-links/" + user_id)
    if not isinstance(pending, dict) or int(pending.get("expires_at", 0)) < int(time.time()):
        raise PluginError("Your verification code has expired. Start the link again.")
    attempts = int(pending.get("attempts", 0))
    if attempts >= 5:
        raise PluginError("Too many verification attempts. Start the link again.")
    code = str(values.get("code", "")); pending["attempts"] = attempts + 1; _store("pending-links/" + user_id, pending)
    if not hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(), str(pending.get("code_hash", ""))):
        raise PluginError("That verification code is incorrect.")
    _store("links/" + user_id, {"discord_id": str(pending["discord_id"]), "linked_at": int(time.time())}); _delete("pending-links/" + user_id)
    return {"ok": True, "message": "Discord account linked."}


def unlink(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values); _delete("links/" + user_id); _delete("pending-links/" + user_id)
    return {"ok": True, "message": "Discord account unlinked."}


def test_dm(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _actor(values); config = _bot_config(); link = _load("links/" + user_id)
    if not isinstance(link, dict) or not link.get("discord_id"):
        raise PluginError("Link and verify your Discord account first.")
    _send_dm(config["token"], link["discord_id"], "Discord notification test from your tracking app.")
    link["last_test_at"] = int(time.time()); _store("links/" + user_id, link)
    return {"ok": True, "message": "Test DM sent."}


def deliver(values: dict[str, Any]) -> dict[str, Any]:
    """Send only to the verified recipient mapped to the host-supplied user context."""
    try:
        user_id = _actor(values); delivery = values.get("delivery")
        if not isinstance(delivery, dict):
            return {"success": False, "retryable": False, "error": "delivery_invalid"}
        context = values.get("_notification_context")
        destination = context.get("destination") if isinstance(context, dict) else None
        if (
            not isinstance(context, dict)
            or context.get("operation") != "deliver"
            or not isinstance(destination, dict)
            or destination.get("kind") != "discord_bot_dm"
        ):
            return {"success": False, "retryable": False, "error": "notification_context_invalid"}
        title = str(delivery.get("title", "Notification"))[:250]; body = str(delivery.get("body", ""))[:1500]; content = f"**{title}**\n{body}".strip()[:1900]
        config = _bot_config(); link = _load("links/" + user_id)
        if not isinstance(link, dict) or not link.get("discord_id"):
            return {"success": False, "retryable": False, "error": "recipient_not_linked"}
        _send_dm(config["token"], str(link["discord_id"]), content or "Notification")
        link["last_delivery_at"] = int(time.time()); _store("links/" + user_id, link)
    except GatewayRequestError as exc:
        retryable = exc.code in {"unavailable", "rate_limited"}
        return {"success": False, "retryable": retryable, "error": "discord_gateway_unavailable" if retryable else "discord_permission_denied"}
    except PluginError:
        return {"success": False, "retryable": False, "error": "discord_delivery_failed"}
    return {"success": True, "retryable": False}


def _register_provider() -> None:
    delay = 1
    while True:
        try:
            register_provider(
                PROVIDER_ID,
                "Discord Bot DM",
                "deliver",
                transport="plugin",
                definition={
                    "destinations": [
                        {
                            "kind": "discord_bot_dm",
                            "label": "Discord Bot DM",
                            "privacy": "PRIVATE",
                            "fields": [],
                        }
                    ],
                    "configure_action": "save-bot-config",
                    "retire_action": "clear-bot-token",
                    "test_action": "test-dm",
                    "features": {"critical_supported": False, "multiple_destinations": False},
                },
            )
            return
        except GatewayRequestError as exc:
            if exc.code != "unavailable":
                raise
            print("Waiting for the host gateway before registering Discord Bot DM.", file=sys.stderr, flush=True); time.sleep(delay); delay = min(delay * 2, 30)


def main() -> None:
    _register_provider()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
