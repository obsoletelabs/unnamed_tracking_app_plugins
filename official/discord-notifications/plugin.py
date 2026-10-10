"""Official Discord webhook provider; configuration and delivery stay in the plugin."""

from __future__ import annotations

import json
import sys
import time
from typing import Any
from urllib.parse import urlparse

from sdk.notifications import register_provider
from sdk.plugin_protocol import GatewayRequestError, request

PLUGIN_ID = "official.discord-notifications"
PROVIDER_ID = PLUGIN_ID + ".webhook"
_ALLOWED_HOSTS = {"discord.com", "discordapp.com"}


class PluginError(ValueError):
    """Safe user-facing configuration/delivery error."""


def _user_id(values: dict[str, Any]) -> str:
    context = values.get("_plugin_context", {})
    if not isinstance(context, dict) or not context.get("user_id"):
        raise PluginError("Sign in to configure Discord notifications.")
    return str(context["user_id"])


def _validate_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise PluginError("Discord webhook URLs must use HTTPS without embedded credentials.")
    if (parsed.hostname or "").lower() not in _ALLOWED_HOSTS:
        raise PluginError("Enter a Discord webhook URL.")
    if not parsed.path.startswith("/api/webhooks/"):
        raise PluginError("Enter a valid Discord webhook URL.")
    return parsed.geturl()


def _secret_key(user_id: str) -> str:
    return "webhooks/" + user_id


def _load_url(user_id: str) -> str:
    raw = request("storage.get", "plugin.storage", {"key": _secret_key(user_id)}).get("value")
    if not raw:
        raise PluginError("Configure a Discord webhook first.")
    try:
        data = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise PluginError("Saved Discord webhook configuration is invalid.") from exc
    return _validate_url(str(data.get("url", "")))


def _send(url: str, payload: dict[str, Any]) -> None:
    request(
        "network.request",
        "network.outbound",
        {
            "url": url,
            "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "json": payload,
            "timeout_ms": 10000,
        },
    )


def test(values: dict[str, Any]) -> dict[str, Any]:
    user_id = _user_id(values)
    _send(_load_url(user_id), {"content": "Discord webhook test from your tracking app.", "allowed_mentions": {"parse": []}})
    return {"ok": True, "message": "Test notification sent."}


def deliver(values: dict[str, Any]) -> dict[str, Any]:
    """Deliver only the public projection supplied by the notification coordinator."""
    try:
        user_id = _user_id(values)
        delivery = values.get("delivery")
        if not isinstance(delivery, dict):
            return {"success": False, "retryable": False, "error": "delivery_invalid"}
        title = str(delivery.get("title", "Notification"))[:256]
        body = str(delivery.get("body", ""))[:4000]
        event_at = delivery.get("event_at")
        embed: dict[str, Any] = {"title": title, "description": body}
        if isinstance(event_at, int):
            embed["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(event_at))
        _send(_load_url(user_id), {"embeds": [embed], "allowed_mentions": {"parse": []}})
    except GatewayRequestError as exc:
        retryable = exc.code in {"unavailable", "rate_limited"}
        return {
            "success": False,
            "retryable": retryable,
            "error": "discord_gateway_unavailable" if retryable else "discord_delivery_failed",
        }
    except PluginError as exc:
        return {"success": False, "retryable": False, "error": str(exc)[:512]}
    return {"success": True, "retryable": False}


def _register_provider() -> None:
    delay = 1
    while True:
        try:
            register_provider(
                PROVIDER_ID,
                "Discord Webhook",
                "deliver",
                destination_kind="discord_webhook",
                privacy="PUBLIC",
            )
            return
        except GatewayRequestError as exc:
            if exc.code != "unavailable":
                raise
            print(
                "Waiting for the host gateway before registering Discord Webhook.",
                file=sys.stderr,
                flush=True,
            )
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main() -> None:
    _register_provider()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
