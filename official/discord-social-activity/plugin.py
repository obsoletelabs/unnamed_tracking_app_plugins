"""Public Plugin API consumer for persistent shared game-night sessions."""

import hashlib
import json
import sys
import time
from typing import Any

from sdk.plugin_protocol import GatewayRequestError, request
from sdk.public_apps import participant_context

from engine import SessionError, transition
from privacy import scrub_room


def admin_list(values: dict[str, Any]) -> dict[str, Any]:
    return request("public_apps.admin.list", "integrations.public_app.admin",
                   {"cursor": values["cursor"]} if values.get("cursor") else {})


def admin_manage(values: dict[str, Any]) -> dict[str, Any]:
    if values.get("confirmed") is not True or values.get("operation") not in {"unlink", "purge"}:
        raise ValueError("Review and confirm the selected management action.")
    operation = values["operation"]
    payload = {key: values[key] for key in ("actor_id", "all", "source_id", "confirmed") if key in values}
    # Invalidate external sessions before editing cached rooms, so stale callers
    # cannot write their removed data back through the host storage gateway.
    result = request("public_apps.admin." + operation, "integrations.public_app.admin", payload)
    rooms = request("storage.keys", "plugin.storage", {"prefix": "rooms/"}).get("keys", [])
    for key in rooms:
        for _attempt in range(12):
            previous = request("storage.get", "plugin.storage", {"key": key}).get("value")
            if previous is None:
                break
            saved = json.loads(previous)
            scrubbed = None if values.get("all") else scrub_room(saved,
                values["actor_id"], purge=operation == "purge", source_id=values.get("source_id"))
            updated = json.dumps(scrubbed, separators=(",", ":"), allow_nan=False) if scrubbed is not None else None
            if request("storage.compare_and_swap", "plugin.storage", {
                "key": key, "expected": previous, "value": updated}).get("swapped"):
                break
        else:
            raise RuntimeError("Connections were removed, but room cleanup needs retrying. Retry this action.")
    return result


def session_action(values: dict[str, Any]) -> dict[str, Any]:
    context = participant_context(values)
    room_key = "rooms/" + hashlib.sha256(context["room"].encode()).hexdigest()
    # Concurrent voting and joins cannot overwrite another participant's input.
    for _attempt in range(12):
        previous = request("storage.get", "plugin.storage", {"key": room_key}).get("value")
        saved = json.loads(previous) if previous is not None else None
        try:
            state, result = transition(saved, values, context)
        except SessionError as exc:
            return {"error": str(exc)}
        updated = json.dumps(state, separators=(",", ":"), allow_nan=False)
        committed = request("storage.compare_and_swap", "plugin.storage",
                            {"key": room_key, "expected": previous, "value": updated})
        if committed.get("swapped"):
            return result
    return {"error": "The room changed while saving. Retry this action."}


def main() -> None:
    delay = 1
    while True:
        # Bounded data retention even if the Discord instance never reconnects.
        try:
            keys = request("storage.keys", "plugin.storage", {"prefix": "rooms/"}).get("keys", [])
            for key in keys:
                previous = request("storage.get", "plugin.storage", {"key": key}).get("value")
                if previous and json.loads(previous).get("expires_at", 0) <= int(time.time()):
                    request("storage.compare_and_swap", "plugin.storage",
                            {"key": key, "expected": previous, "value": None})
        except GatewayRequestError as exc:
            if exc.code != "unavailable":
                raise
            # The host may still be starting or briefly unavailable during a reload.
            print("Waiting for the host gateway before cleaning up Game Night rooms.",
                  file=sys.stderr, flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)
            continue
        delay = 1
        time.sleep(60)
