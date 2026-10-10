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
    transport: Literal["legacy", "discord_webhook", "plugin"] = "legacy",
    definition: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Register a provider using the versioned host-owned transport contract.

    Existing host-owned transports remain supported. Plugin-owned destinations
    use the generic plugin transport plus a bounded declarative definition;
    credentials and endpoint values remain inside plugin storage.
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
