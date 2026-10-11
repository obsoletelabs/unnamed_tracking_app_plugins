"""Maintained Discord webhook transport using the public generic provider contract."""

import json
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from sdk.notifications import provider_context, register_provider
from sdk.plugin_protocol import GatewayRequestError, request

PROVIDER_ID = "official.discord-notifications.webhook"
DEFINITION = {
    "destinations": [{
        "kind": "discord_webhook",
        "label": "Discord webhook",
        "privacy": "PUBLIC",
        "fields": [{
            "id": "url", "label": "Discord webhook URL", "type": "password",
            "secret": True, "required": True,
            "description": "HTTPS URL for an ordinary Discord text channel. The plugin stores its token.",
            "validation": {"max_length": 512},
        }],
    }],
    "configure_action": "configure", "retire_action": "retire", "test_action": "deliver",
    "features": {"multiple_destinations": True, "critical_supported": False},
}


class PluginError(ValueError):
    """Safe user-facing configuration errors, without URLs or remote bodies."""


def _context(values: dict[str, Any], operation: str) -> dict[str, Any]:
    try:
        context = provider_context(values, operation=operation, provider_id=PROVIDER_ID)
        if context["scope"] != "destination" or context["destination"]["kind"] != "discord_webhook":
            raise ValueError("Wrong destination kind")
        return context
    except (KeyError, TypeError, ValueError) as exc:
        raise PluginError("A core-authorized Discord destination is required.") from exc


def _validate_url(value: str) -> str:
    try:
        if not isinstance(value, str) or len(value) > 512 or any(char.isspace() for char in value):
            raise ValueError("Invalid URL")
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or parsed.username or parsed.password
                or parsed.netloc.lower() not in {"discord.com", "discordapp.com"}
                or parsed.query or parsed.fragment
                or not re.fullmatch(r"/api/webhooks/[0-9]{1,32}/[A-Za-z0-9._-]{1,256}", parsed.path)):
            raise ValueError("Invalid URL")
        return parsed.geturl()
    except (TypeError, ValueError) as exc:
        raise PluginError("Enter a valid HTTPS Discord webhook URL without query, port or fragment.") from exc


def _key(context: dict[str, Any]) -> str:
    return f"webhooks/{context['installation_id']}/{context['destination']['id']}"


def _load(context: dict[str, Any]) -> dict[str, Any] | None:
    raw = request("storage.get", "plugin.storage", {"key": _key(context)}).get("value")
    if raw is None:
        return None
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or type(value.get("revision")) is not int:
            raise ValueError("Invalid record")
        return value
    except (TypeError, ValueError) as exc:
        raise PluginError("Saved Discord configuration is invalid; configure it again.") from exc


def _store(context: dict[str, Any], record: dict[str, Any]) -> None:
    request("storage.put", "plugin.storage", {"key": _key(context), "value": json.dumps(record)})


def configure(values: dict[str, Any]) -> dict[str, Any]:
    context = _context(values, "configure")
    configuration = values.get("configuration")
    if not isinstance(configuration, dict) or set(configuration) - {"url"}:
        raise PluginError("Discord configuration requires a webhook URL.")
    current = _load(context)
    revision = context["destination"]["revision"]
    if current and (current["revision"] > revision or current.get("retired")):
        raise PluginError("This configuration is stale or retired.")
    url = _validate_url(configuration.get("url", current.get("url") if current else None))
    _store(context, {"revision": revision, "url": url})
    return {"configured": True}


def retire(values: dict[str, Any]) -> dict[str, Any]:
    context = _context(values, "retire")
    current = _load(context)
    revision = context["destination"]["revision"]
    if current and current["revision"] > revision:
        raise PluginError("This retirement is stale.")
    # Retain only an opaque revision tombstone, so an old callback cannot restore the secret.
    _store(context, {"revision": revision, "retired": True})
    return {"retired": True}


def deliver(values: dict[str, Any]) -> dict[str, Any]:
    """Core owns attempts/retries; this provider returns only safe transport results."""
    try:
        context = _context(values, "deliver")
        record = _load(context)
        if not record or record.get("retired") or record["revision"] != context["destination"]["revision"]:
            raise PluginError("The configured destination revision is unavailable.")
        delivery = values.get("delivery")
        if not isinstance(delivery, dict) or not isinstance(delivery.get("title"), str) or not isinstance(delivery.get("body"), str):
            raise PluginError("Notification content is invalid.")
        embed = {"title": delivery["title"][:256], "description": delivery["body"][:4000]}
        link = delivery.get("link")
        if isinstance(link, str) and urlsplit(link).scheme in {"http", "https"}:
            embed["url"] = link
        occurred_at = delivery.get("event_at")
        if type(occurred_at) is int:
            embed["timestamp"] = datetime.fromtimestamp(occurred_at, timezone.utc).isoformat()
        response = request("network.request", "network.outbound", {
            "url": _validate_url(record.get("url")), "method": "POST",
            "headers": {"Content-Type": "application/json"},
            "body": {"embeds": [embed], "allowed_mentions": {"parse": []}},
            "response_format": "text",
        })
        status = response.get("status")
        if type(status) is not int:
            return {"success": False, "retryable": True, "error": "discord_response_invalid"}
        if 200 <= status < 300:
            return {"success": True, "retryable": False}
        return {"success": False, "retryable": status == 0 or status == 429 or status >= 500, "error": "discord_delivery_failed"}
    except GatewayRequestError as exc:
        return {"success": False, "retryable": exc.code in {"unavailable", "rate_limited"}, "error": "discord_gateway_failed"}
    except (PluginError, TypeError, ValueError, OverflowError):
        return {"success": False, "retryable": False, "error": "discord_configuration_invalid"}


def _register_provider() -> None:
    delay = 1
    while True:
        try:
            register_provider(PROVIDER_ID, "Discord Webhook", "deliver", transport="plugin", definition=DEFINITION)
            return
        except GatewayRequestError as exc:
            if exc.code != "unavailable":
                raise
            print("Waiting for the host gateway before registering Discord Webhook.", file=sys.stderr, flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main() -> None:
    _register_provider()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
