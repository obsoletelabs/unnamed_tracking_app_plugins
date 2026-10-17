"""Maintained Discord webhook transport using the public generic provider contract."""

import json
import re
import sys
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from sdk.discord_embeds import DiscordRenderError, render_delivery, webhook_message_id
from sdk.notification_stories import ContractError, delivery_operation, delivery_result, provider_capabilities
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
    # Webhook messages can be edited by their own id, but cannot be replied to or carry buttons.
    "capabilities": provider_capabilities(
        max_batch_items=8, message_updates="edit", threaded_follow_ups=False, rich_embeds=True,
        images={"max_images": 4, "external_urls": True}, action_buttons=5, links=True,
        live_page_links=True, max_title_chars=256, max_text_chars=4096, max_payload_bytes=30000,
    ),
    "edit_action": "edit",
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


def _post(record: dict[str, Any], method: str, suffix: str, body: dict[str, Any]) -> dict[str, Any]:
    url = _validate_url(record.get("url"))
    return request("network.request", "network.outbound", {
        "url": url + suffix, "method": method, "headers": {"Content-Type": "application/json"},
        "body": body, "response_format": "json",
    })


def _retryable(status: int) -> bool:
    return status == 0 or status == 429 or status >= 500


def _rich(record: dict[str, Any], delivery: dict[str, Any]) -> dict[str, Any]:
    """Send or edit one canonical delivery; a gone message asks the host for a follow-up."""
    operation, reference = delivery_operation(delivery)
    message = render_delivery(delivery, components=False)
    if operation == "edit":
        try:
            message_id = webhook_message_id(reference)
        except DiscordRenderError:
            # Not a reference this provider produced, so nothing can be edited.
            return delivery_result(success=False, gone=True)
        response = _post(record, "PATCH", f"/messages/{message_id}", message)
        status = response.get("status")
        if type(status) is int and 200 <= status < 300:
            return delivery_result(success=True, remote_ref=message_id)
        if status in {403, 404}:
            return delivery_result(success=False, gone=True)
        return delivery_result(success=False, retryable=type(status) is not int or _retryable(status))
    response = _post(record, "POST", "?wait=true", message)
    status = response.get("status")
    if type(status) is not int:
        return delivery_result(success=False, retryable=True)
    if 200 <= status < 300:
        data = response.get("data")
        created = data.get("id") if isinstance(data, dict) else None
        try:
            return delivery_result(success=True, remote_ref=webhook_message_id(created))
        except DiscordRenderError:
            # Accepted without a usable id: later revisions become follow-ups, never blind edits.
            return delivery_result(success=True)
    return delivery_result(success=False, retryable=_retryable(status))


def _legacy(record: dict[str, Any], delivery: dict[str, Any]) -> dict[str, Any]:
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
    return {"success": False, "retryable": _retryable(status), "error": "discord_delivery_failed"}


def deliver(values: dict[str, Any]) -> dict[str, Any]:
    """Core owns attempts/retries; this provider returns only safe transport results.

    Canonical deliveries (they carry ``contract_version``) are rendered as embeds and may be
    edits of an earlier message; the host-owned test message keeps the minimal legacy payload.
    """
    try:
        context = _context(values, "deliver")
        record = _load(context)
        if not record or record.get("retired") or record["revision"] != context["destination"]["revision"]:
            raise PluginError("The configured destination revision is unavailable.")
        delivery = values.get("delivery")
        if not isinstance(delivery, dict) or not isinstance(delivery.get("title"), str) or not isinstance(delivery.get("body"), str):
            raise PluginError("Notification content is invalid.")
        if "contract_version" in delivery:
            return _rich(record, delivery)
        return _legacy(record, delivery)
    except GatewayRequestError as exc:
        return {"success": False, "retryable": exc.code in {"unavailable", "rate_limited"}, "error": "discord_gateway_failed"}
    except (PluginError, ContractError, DiscordRenderError, TypeError, ValueError, OverflowError):
        return {"success": False, "retryable": False, "error": "discord_configuration_invalid"}


def edit(values: dict[str, Any]) -> dict[str, Any]:
    """Apply a story revision to the webhook message sent earlier."""
    return deliver(values)


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
