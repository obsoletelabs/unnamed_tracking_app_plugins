from __future__ import annotations

import json
import sys
import time

from sdk.plugin_protocol import request

CAPABILITY = "notifications.send"


def announce_page(values: dict) -> bool:
    context = values.get("_plugin_context", {})
    if isinstance(context, str):
        try:
            context = json.loads(context)
        except json.JSONDecodeError:
            context = {}
    if not isinstance(context, dict):
        context = {}
    page = context.get("page_title") or context.get("page_id") or "Unknown page"
    path = context.get("path") or "/"
    # Ask the host runtime to deliver the message. The runtime reads the
    # private webhook from plugin storage; the plugin never echoes the secret.
    print(json.dumps({
        "discord": True,
        "content": f"Unnamed Tracking: a user is viewing **{page}** ({path}).",
    }), flush=True)
    return True


def main() -> None:
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "announce":
        raise SystemExit(0 if announce_page(json.load(sys.stdin)) else 1)
    main()
