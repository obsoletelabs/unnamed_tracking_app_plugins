"""Deliberately unreliable approved-field renderer; never a production provider."""

from __future__ import annotations

import json
import sys
import time
from uuid import UUID

from sdk.notifications import register_provider
from sdk.plugin_protocol import GatewayRequestError, request

PROVIDER_ID = "example.notification-chaos-provider.webhook"
LEDGER_KEY = "simulation/failed-notifications"
LEDGER_LIMIT = 100
MODES = {"embed", "plain", "fail_first", "always_fail", "invalid_layout"}


def _fail_first(values: dict) -> None:
    """Persist only bounded opaque IDs; this ledger is not delivery state."""
    try:
        identity = str(UUID(values["delivery"]["notification_id"]))
    except (KeyError, TypeError, ValueError, AttributeError):
        raise ValueError("Core notification identity is required") from None
    raw = request("storage.get", "plugin.storage", {"key": LEDGER_KEY}).get("value")
    try:
        ledger = json.loads(raw) if raw is not None else []
        if not isinstance(ledger, list) or len(ledger) > LEDGER_LIMIT:
            raise ValueError
        ledger = [str(UUID(item)) for item in ledger]
    except (TypeError, ValueError, AttributeError):
        raise ValueError("Demo simulation ledger is invalid") from None
    if identity in ledger:
        return
    request("storage.put", "plugin.storage", {
        "key": LEDGER_KEY, "value": json.dumps([*ledger, identity][-LEDGER_LIMIT:]),
    })
    raise RuntimeError("Demo provider deliberately fails the first render")


def render(values: dict) -> dict:
    mode = request("settings.get", "plugin.settings", {"key": "mode"}).get("value")
    mode = "embed" if mode is None else mode
    if not isinstance(mode, str) or mode not in MODES:
        raise ValueError("Choose a valid demo failure mode")
    if mode == "always_fail":
        raise RuntimeError("Demo provider deliberately fails every render")
    if mode == "invalid_layout":
        # Deliberately violates the public schema to prove core rejection.
        return {"style": "confetti", "fields": ["title"]}
    if mode == "fail_first":
        _fail_first(values)
    # Backwards field order is intentionally absurd, but still approved content.
    return {"style": "plain" if mode == "plain" else "embed",
            "fields": ["link", "event_at", "body", "title"]}


def _register_provider() -> None:
    delay = 1
    while True:
        try:
            register_provider(
                PROVIDER_ID,
                "Notification Chaos Demo",
                "render",
                transport="plugin",
                definition={
                    "destinations": [
                        {"kind": "notification_chaos", "label": "Notification Chaos Demo", "privacy": "PUBLIC"}
                    ],
                    "configure_action": "configure",
                    "retire_action": "retire",
                    "test_action": "test",
                },
            )
            return
        except GatewayRequestError as exc:
            if exc.code != "unavailable":
                raise
            print("Waiting for the host before registering the demo.", file=sys.stderr, flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main() -> None:
    _register_provider()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
