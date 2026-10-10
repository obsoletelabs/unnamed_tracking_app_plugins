"""Public typed notification source helpers; recipient/routing stay host-owned."""

from typing import Any

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


def register_provider(provider_id: str, name: str, action_id: str, *, transport: str = "legacy") -> dict[str, Any]:
    """Register a namespaced provider; host owns endpoints, trust and delivery state."""
    return request("notification_providers.register", "notification_providers.register", {
        "provider_id": provider_id, "name": name, "action_id": action_id, "transport": transport,
    })


def poll_lifecycle(cursor: str | None = None, *, limit: int = 100) -> dict[str, Any]:
    """Replay own installation metadata on host 1.1.4 with an explicit read grant.

    Save the returned cursor only after processing its events. If
    resync_required is true, discard stale local assumptions and restart using
    the returned cursor; this feed cannot reconstruct expired state.
    """
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
        raise ValueError("Lifecycle limit must be an integer from 1 to 200")
    if cursor is not None and (not isinstance(cursor, str) or not 1 <= len(cursor) <= 1024):
        raise ValueError("Lifecycle cursor must be a nonempty bounded string")
    return request("notifications.lifecycle.poll", "notifications.lifecycle.read", {
        "cursor": cursor, "limit": limit,
    })