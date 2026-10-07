"""Session manager behavior using only the public, scoped Plugin API."""

from __future__ import annotations

import time
from typing import Any
from uuid import UUID

from sdk.plugin_protocol import request, route_query_value, route_response


def _identifier(values: dict[str, Any], name: str) -> str:
    value = values.get(name)
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a UUID")
    try:
        return str(UUID(value))
    except ValueError as exc:
        raise ValueError(f"{name} must be a UUID") from exc


def _context(values: dict[str, Any]) -> dict[str, Any]:
    context = values.get("_plugin_context")
    return context if isinstance(context, dict) else {}


def _list(values: dict[str, Any], admin: bool = False) -> dict[str, Any]:
    limit = values.get("limit", 200)
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit must be an integer")
    payload = {
        key: values[key]
        for key in ("q", "country", "state", "anomaly", "cursor")
        if key in values and values[key] is not None and values[key] != ""
    }
    payload["limit"] = max(1, min(limit, 200))
    if admin and values.get("user_id"):
        payload["user_id"] = _identifier(values, "user_id")
    context = _context(values)
    if context.get("session_id"):
        payload["current_session_id"] = context["session_id"]
    result = request(
        "sessions.admin.list" if admin else "sessions.list",
        "sessions.admin.read" if admin else "sessions.read",
        payload,
    )
    result["is_admin"] = context.get("is_admin") is True
    return result


def list_sessions(values: dict[str, Any]) -> dict[str, Any]:
    return _list(values)


def list_admin_sessions(values: dict[str, Any]) -> dict[str, Any]:
    return _list(values, admin=True)


def _revoke(
    values: dict[str, Any], method: str, name: str | None = None
) -> dict[str, Any]:
    if _context(values).get("confirmed") is not True:
        raise ValueError("explicit revocation confirmation is required")
    payload = {"confirmed": True}
    if _context(values).get("session_id"):
        payload["current_session_id"] = _context(values)["session_id"]
    if name:
        payload[name] = _identifier(values, name)
    capability = (
        "sessions.admin.revoke"
        if method.startswith("sessions.admin.")
        else "sessions.revoke"
    )
    return request(method, capability, payload)


def revoke_session(values: dict[str, Any]) -> dict[str, Any]:
    return _revoke(values, "sessions.revoke", "session_id")


def revoke_all_sessions(values: dict[str, Any]) -> dict[str, Any]:
    return _revoke(values, "sessions.revoke_all")


def revoke_admin_session(values: dict[str, Any]) -> dict[str, Any]:
    return _revoke(values, "sessions.admin.revoke", "session_id")


def revoke_all_admin_sessions(values: dict[str, Any]) -> dict[str, Any]:
    return _revoke(values, "sessions.admin.revoke_all")


def revoke_user_sessions(values: dict[str, Any]) -> dict[str, Any]:
    return _revoke(values, "sessions.admin.revoke_user", "user_id")


def geoip_status(values: dict[str, Any]) -> dict[str, Any]:
    del values
    return request("sessions.geoip.status", "sessions.geoip.read", {})


def _route(
    route_request: dict[str, Any], handler, *, listing: bool = False
) -> dict[str, Any]:
    values = dict(route_request.get("body") or {})
    values.update(route_request.get("path_parameters") or {})
    user = route_request.get("user") or {}
    values["_plugin_context"] = {
        "confirmed": values.get("confirmed") is True,
        "session_id": route_request.get("current_session_id"),
        "is_admin": user.get("is_admin") is True,
    }
    if listing:
        for key in ("limit", "q", "country", "state", "anomaly", "cursor", "user_id"):
            value = route_query_value(route_request, key)
            if value is None:
                continue
            if key == "limit":
                try:
                    value = int(value)
                except ValueError:
                    return route_response({"error": "limit must be an integer"}, 422)
            if key == "anomaly":
                if value not in ("true", "false"):
                    return route_response(
                        {"error": "anomaly must be true or false"}, 422
                    )
                value = value == "true"
            values[key] = value
    try:
        return route_response(handler(values))
    except ValueError as exc:
        return route_response({"error": str(exc)}, 422)


def list_sessions_route(route_request: dict[str, Any]) -> dict[str, Any]:
    return _route(route_request, list_sessions, listing=True)


def list_admin_sessions_route(route_request: dict[str, Any]) -> dict[str, Any]:
    return _route(route_request, list_admin_sessions, listing=True)


def revoke_session_route(route_request: dict[str, Any]) -> dict[str, Any]:
    return _route(route_request, revoke_session)


def revoke_all_sessions_route(route_request: dict[str, Any]) -> dict[str, Any]:
    return _route(route_request, revoke_all_sessions)


def revoke_admin_session_route(route_request: dict[str, Any]) -> dict[str, Any]:
    return _route(route_request, revoke_admin_session)


def revoke_all_admin_sessions_route(route_request: dict[str, Any]) -> dict[str, Any]:
    return _route(route_request, revoke_all_admin_sessions)


def revoke_user_sessions_route(route_request: dict[str, Any]) -> dict[str, Any]:
    return _route(route_request, revoke_user_sessions)


def main() -> None:
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
