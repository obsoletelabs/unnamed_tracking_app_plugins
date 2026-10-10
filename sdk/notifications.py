"""Public typed notification source/provider helpers."""

from typing import Any, Literal

from .plugin_protocol import request


def register_type(definition: dict[str, Any]) -> dict[str, Any]:
    return request("notification_sources.register", "notification_sources.register", definition)


def unregister_type(event_type: str) -> dict[str, Any]:
    return request("notification_sources.unregister", "notification_sources.register", {"event_type": event_type})


def emit(
    event_type: str,
    dedupe_key: str,
    occurred_at: int,
    data: dict[str, str | int | bool],
    *,
    group_key: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "event_type": event_type,
        "dedupe_key": dedupe_key,
        "occurred_at": occurred_at,
        "data": data,
    }
    if group_key is not None:
        payload["group_key"] = group_key
    return request("notifications.emit", "notifications.emit", payload)


def register_provider(
    provider_id: str,
    name: str,
    action_id: str,
    *,
    destination_kind: str,
    privacy: Literal["PUBLIC", "PRIVATE"] = "PUBLIC",
    channel_context: Literal["external", "internal"] = "external",
) -> dict[str, Any]:
    """Register a plugin-owned destination contract.

    The plugin owns its settings and performs the actual delivery action. The
    host stores only an opaque routing record and the declared trust boundary.
    """
    transport = "plugin_private" if privacy == "PRIVATE" else "plugin_public"
    return request(
        "notification_providers.register",
        "notification_providers.register",
        {
            "provider_id": provider_id,
            "name": name,
            "action_id": action_id,
            "destination_kind": destination_kind,
            "privacy": privacy,
            "channel_context": channel_context,
            "transport": transport,
        },
    )
