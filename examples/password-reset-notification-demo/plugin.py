"""Synthetic notification flow only; never modifies host authentication or users."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import time
from uuid import UUID, uuid4

from sdk.notifications import emit, register_type
from sdk.plugin_protocol import request

EVENT_TYPE = 'example.password-reset-notification-demo.requested'
DEFINITION = {'event_type': 'example.password-reset-notification-demo.requested', 'label': 'Password Reset Routing Demo', 'description': 'Synthetic notification routing demonstration; no real authentication changes.', 'required_trust': 'SECURE', 'purpose': 'recovery', 'severity': 'info', 'title_template': 'Password Reset Routing Demo', 'body_template': "This is a synthetic password-reset demonstration. No account password will change. Demo token: {token}. It expires in ten minutes. Confirm it through this plugin's confirm action.", 'parameters': {'token': 'string'}}


def actor(values: dict) -> str:
    # This context is supplied by the authenticated host action boundary.
    raw = (values.get("_plugin_context") or {}).get("user_id")
    try:
        return str(UUID(raw))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("An authenticated plugin action context is required") from None


def issue(values: dict) -> dict:
    user_id = actor(values)
    register_type(DEFINITION)
    token = secrets.token_urlsafe(32)
    identity = uuid4().hex
    now = int(time.time())
    # Store a digest, never a reusable token. One active demonstration per owner.
    request("storage.put", "plugin.storage", {
        "key": f"users/{user_id}/challenge",
        "value": json.dumps({"digest": hashlib.sha256(token.encode()).hexdigest(),
                             "identity": identity, "expires_at": now + 600, "consumed": False}),
    })
    result = emit(EVENT_TYPE, identity, now, {"token": token}, group_key="demonstrations")
    # Acknowledgement means accepted by the core, never final email delivery.
    return {"accepted": result.get("created") is True, "notification_id": result.get("notification_id"),
            "expires_at": now + 600, "demo_only": True}


def confirm(values: dict) -> dict:
    user_id = actor(values)
    token = values.get("token")
    if not isinstance(token, str) or not 1 <= len(token) <= 128:
        raise ValueError("Enter the token from the demonstration notification")
    raw = request("storage.get", "plugin.storage", {"key": f"users/{user_id}/challenge"}).get("value")
    try:
        record = json.loads(raw) if raw is not None else {}
    except (TypeError, ValueError):
        raise ValueError("No valid demonstration challenge") from None
    digest = hashlib.sha256(token.encode()).hexdigest()
    if (record.get("consumed") or record.get("expires_at", 0) <= int(time.time())
            or not hmac.compare_digest(str(record.get("digest", "")), digest)):
        raise ValueError("The demonstration token is invalid, expired or already used")
    record["consumed"] = True
    record.pop("digest", None)
    request("storage.put", "plugin.storage", {
        "key": f"users/{user_id}/challenge", "value": json.dumps(record),
    })
    return {"confirmed": True, "demo_only": True, "authentication_changed": False}


def main() -> None:
    request("lifecycle.ready", "lifecycle.ready", {})
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
