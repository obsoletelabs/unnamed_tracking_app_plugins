"""Maintained admin invitation integration; the host owns tokens and account creation."""
import json
import time
from sdk.plugin_protocol import request

KEY = "invitations/configuration"
PRESENTATION = {
    "sender_name": ("", 80), "email_subject": ("You are invited", 160),
    "email_heading": ("Join our library", 160),
    "welcome_message": ("You have been invited to create an account.", 2000),
    "button_label": ("Accept invitation", 80),
    "footer_message": ("Sent by your tracking app.", 500),
    "greeting": ("personal", 16), "email_layout": ("card", 16),
    "accent_color": ("#3458d4", 7),
}

def definition(values):
    lifetime = values.get("token_lifetime_seconds", 86400)
    if isinstance(lifetime, bool) or not isinstance(lifetime, (int, float)) or int(lifetime) != lifetime or not 3600 <= lifetime <= 604800:
        raise ValueError("Link lifetime must be an integer between 3600 and 604800 seconds")
    flow = {"mode": "user_invite", "name": "User Invites", "token_lifetime_seconds": int(lifetime)}
    for key, (_, limit) in PRESENTATION.items():
        if key not in values:
            continue
        value = values[key]
        if not isinstance(value, str) or len(value) > limit:
            raise ValueError(f"Invalid {key.replace('_', ' ')}")
        if key in {"sender_name", "email_subject", "email_heading", "button_label"} and any(ord(c) < 32 or ord(c) == 127 for c in value):
            raise ValueError("Email labels must not contain control characters")
        if key in {"email_subject", "email_heading", "button_label"} and not value.strip():
            raise ValueError("Email labels must not be empty")
        flow[key] = value
    if flow.get("greeting", "personal") not in {"personal", "generic", "none"} or flow.get("email_layout", "card") not in {"card", "simple"}:
        raise ValueError("Choose a supported greeting and email layout")
    color = flow.get("accent_color", "#3458d4")
    if len(color) != 7 or color[0] != "#" or any(c not in "0123456789abcdefABCDEF" for c in color[1:]):
        raise ValueError("Choose a valid accent color")
    return flow

def configuration():
    raw = request("storage.get", "plugin.storage", {"key": KEY}).get("value")
    return json.loads(raw) if raw else {}

def save(values):
    stored = configuration()
    flow = definition({**stored, **values})
    live = request("auth_flows.user_invites.status", "auth.user_invites", {})
    if live.get("registered") is True:
        request("auth_flows.user_invites.register", "auth.user_invites", flow)
    request("storage.put", "plugin.storage", {"key": KEY, "value": json.dumps({"enabled": live.get("registered") is True, **flow})})
    return {"saved": True}

def enable(values):
    flow = definition({**configuration(), **values})
    result = request("auth_flows.user_invites.register", "auth.user_invites", flow)
    request("storage.put", "plugin.storage", {"key": KEY, "value": json.dumps({"enabled": True, **flow})})
    return result

def disable(values):
    del values
    result = request("auth_flows.user_invites.unregister", "auth.user_invites", {})
    stored = configuration()
    request("storage.put", "plugin.storage", {"key": KEY, "value": json.dumps({**stored, "enabled": False})})
    return result

def status(values):
    del values
    live = request("auth_flows.user_invites.status", "auth.user_invites", {})
    stored = configuration()
    flow = definition(stored)
    return {**{key: default for key, (default, _) in PRESENTATION.items()}, **flow, **live,
            "token_lifetime_seconds": live.get("token_lifetime_seconds", flow["token_lifetime_seconds"]) if live.get("registered") else flow["token_lifetime_seconds"]}

def issue(values):
    payload = {"email": values.get("email", "")}
    if "recipient_name" in values:
        payload["recipient_name"] = values["recipient_name"]
    return request("auth_flows.user_invites.issue", "auth.user_invites", payload)

def list_invites(values):
    del values
    return request("auth_flows.user_invites.list", "auth.user_invites", {})

def revoke(values):
    return request("auth_flows.user_invites.revoke", "auth.user_invites", {"id": values.get("id", "")})

def restore_configuration():
    raw = request("storage.get", "plugin.storage", {"key": KEY}).get("value")
    stored = json.loads(raw) if raw else {}
    if stored.get("enabled") is True:
        request("auth_flows.user_invites.restore", "auth.user_invites", definition(stored))

def main():
    request("lifecycle.ready", "lifecycle.ready", {})
    restore_configuration()
    while True:
        time.sleep(3600)

if __name__ == "__main__":
    main()
