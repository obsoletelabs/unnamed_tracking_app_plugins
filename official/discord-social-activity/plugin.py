"""Public Plugin API consumer for persistent shared game-night sessions."""

import hashlib
import json
import time
from typing import Any

from sdk.plugin_protocol import request
from sdk.public_apps import participant_context

from engine import SessionError, transition


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
    while True:
        # Bounded data retention even if the Discord instance never reconnects.
        keys = request("storage.keys", "plugin.storage", {"prefix": "rooms/"}).get("keys", [])
        for key in keys:
            previous = request("storage.get", "plugin.storage", {"key": key}).get("value")
            if previous and json.loads(previous).get("expires_at", 0) <= int(time.time()):
                request("storage.compare_and_swap", "plugin.storage",
                        {"key": key, "expected": previous, "value": None})
        time.sleep(60)
