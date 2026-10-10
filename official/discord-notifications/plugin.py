"""Maintained Discord layouts; concrete endpoints and transport stay in core."""

from __future__ import annotations

import sys
import time

from sdk.notifications import register_provider
from sdk.plugin_protocol import GatewayRequestError

PLUGIN_ID = "official.discord-notifications"
PROVIDER_ID = PLUGIN_ID + ".webhook"


def render(_values: dict) -> dict:
    """Reference the approved projection without returning arbitrary content."""
    return {"style": "embed", "fields": ["title", "body", "event_at", "link"]}


def _register_provider() -> None:
    delay = 1
    while True:
        try:
            register_provider(PROVIDER_ID, "Discord", "render", transport="discord_webhook")
            return
        except GatewayRequestError as exc:
            if exc.code != "unavailable":
                raise
            print("Waiting for the host gateway before registering Discord.", file=sys.stderr, flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 30)


def main() -> None:
    _register_provider()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
