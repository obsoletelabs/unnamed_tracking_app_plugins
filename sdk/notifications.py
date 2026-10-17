"""Public typed notification source helpers; recipient/routing stay host-owned."""

import re
from typing import Any, Literal
from uuid import UUID

from .plugin_protocol import request


def register_type(definition: dict[str, Any]) -> dict[str, Any]:
    return request("notification_sources.register", "notification_sources.register", definition)


def unregister_type(event_type: str) -> dict[str, Any]:
    return request("notification_sources.unregister", "notification_sources.register", {"event_type": event_type})


def emit(event_type: str, dedupe_key: str, occurred_at: int, data: dict[str, str | int | bool], *, group_key: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"event_type": event_type, "dedupe_key": dedupe_key, "occurred_at": occurred_at, "data": data}
    if group_key is not None:
        payload["group_key"] = group_key
    return request("notifications.emit", "notifications.emit", payload)


def register_provider(
    provider_id: str,
    name: str,
    action_id: str,
    *,
    transport: Literal["legacy", "discord_webhook", "plugin"] = "legacy",
    definition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register a provider using the versioned host-owned transport contract.

    Existing host-owned transports remain supported. Plugin-owned destinations
    use the generic plugin transport plus a bounded declarative definition;
    credentials and endpoint values remain inside plugin storage. On host 1.1.14
    or later the definition may add ``capabilities`` (see
    ``sdk.notification_stories.provider_capabilities``) and an ``edit_action`` for
    providers that can change a message they already sent.
    """
    if (transport == "plugin") != (definition is not None):
        raise ValueError("Generic plugin providers require a definition; legacy transports forbid it")
    payload: dict[str, Any] = {
        "provider_id": provider_id,
        "name": name,
        "action_id": action_id,
        "transport": transport,
    }
    if definition is not None:
        payload["definition"] = definition
    return request(
        "notification_providers.register",
        "notification_providers.register",
        payload,
    )

def provider_context(values: dict[str, Any], *, operation: str, provider_id: str | None = None) -> dict[str, Any]:
    """Validate the private host-issued context; never derive routing identity from UI values.

    Core rejects this reserved field from public actions. Store its revisions
    beside plugin-owned secrets and compare them before transport. This helper
    validates a contract, not a signature or independent SECURE destination proof.
    """
    context = values.get("_notification_context")
    if not isinstance(context, dict) or context.get("operation") != operation:
        raise ValueError("Core notification authority is required")
    scope = context.get("scope")
    expected = {"operation", "scope", "installation_id"}
    if operation == "deliver":
        if scope != "destination":
            raise ValueError("Delivery requires destination scope")
        expected |= {"attempt_id", "server_revision", "destination"}
        UUID(context["attempt_id"])
        revision = context["server_revision"]
    elif operation in {"configure", "retire"}:
        expected.add("provider_id")
        if provider_id is not None and context.get("provider_id") != provider_id:
            raise ValueError("Configuration belongs to another provider")
        if scope == "destination":
            expected.add("destination")
            revision = 1
        elif scope == "server" and operation == "configure":
            expected.add("revision")
            revision = context["revision"]
        else:
            raise ValueError("Configuration scope is invalid")
    else:
        raise ValueError("Notification operation is invalid")
    if set(context) != expected or type(revision) is not int or revision < 1:
        raise ValueError("Notification context is invalid")
    UUID(context["installation_id"])
    if scope == "destination":
        destination = context.get("destination")
        if (not isinstance(destination, dict) or set(destination) != {"id", "revision", "kind"}
                or type(destination["revision"]) is not int or destination["revision"] < 1
                or not isinstance(destination["kind"], str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,31}", destination["kind"])):
            raise ValueError("Notification destination context is invalid")
        UUID(destination["id"])
    return context


def poll_lifecycle(
    cursor: str | None = None, *, limit: int = 100, include_revisions: bool = False
) -> dict[str, Any]:
    """Replay own installation metadata on host 1.1.4 with an explicit read grant.

    ``include_revisions`` (host 1.1.14 or later) also replays ``revised``: an unread story
    item was updated in place. Omit it on older hosts; the request then keeps its 1.1.4 shape.

    Save the returned cursor only after processing its events. If
    resync_required is true, discard stale local assumptions and restart using
    the returned cursor; this feed cannot reconstruct expired state.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("Lifecycle limit must be an integer from 1 to 200")
    if cursor is not None and (not isinstance(cursor, str) or not 1 <= len(cursor) <= 1024):
        raise ValueError("Lifecycle cursor must be a nonempty bounded string")
    payload: dict[str, Any] = {"cursor": cursor, "limit": limit}
    if include_revisions is True:
        payload["include_revisions"] = True
    elif include_revisions is not False:
        raise ValueError("include_revisions must be true or false")
    return request("notifications.lifecycle.poll", "notifications.lifecycle.read", payload)

def destination_status(*, provider_id: str | None = None, after: str | None = None, limit: int = 50) -> dict[str, Any]:
    """Read current actor/current installation status with an independent 1.1.11 grant.

    No destination addresses, configuration, content or credentials are returned.
    This snapshot is informational: core rechecks routing at actual delivery.
    Verification and recovery changes remain owner actions in host Notifications.
    """
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Destination status limit must be an integer from 1 to 100")
    if provider_id is not None and (not isinstance(provider_id, str) or not 1 <= len(provider_id) <= 128):
        raise ValueError("Provider ID must be a bounded string")
    if after is not None:
        UUID(after)
    return request("notification_destinations.status", "notification_destinations.read", {
        "provider_id": provider_id, "after": after, "limit": limit,
    })
