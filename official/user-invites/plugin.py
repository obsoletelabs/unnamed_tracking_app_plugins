"""Maintained admin invitation integration; the host owns tokens and account creation."""
import json
import time
from sdk.plugin_protocol import request

KEY = "invitations/configuration"

def definition(values):
    lifetime = values.get("token_lifetime_seconds", 86400)
    if isinstance(lifetime, bool) or not isinstance(lifetime, (int, float)) or int(lifetime) != lifetime or not 3600 <= lifetime <= 604800:
        raise ValueError("Link lifetime must be an integer between 3600 and 604800 seconds")
    return {"mode": "user_invite", "name": "User Invites", "token_lifetime_seconds": int(lifetime)}

def enable(values):
    flow = definition(values)
    result = request("auth_flows.user_invites.register", "auth.user_invites", flow)
    request("storage.put", "plugin.storage", {"key": KEY, "value": json.dumps({"enabled": True, **flow})})
    return result

def disable(values):
    del values
    result = request("auth_flows.user_invites.unregister", "auth.user_invites", {})
    request("storage.put", "plugin.storage", {"key": KEY, "value": json.dumps({"enabled": False})})
    return result

def status(values):
    del values
    return request("auth_flows.user_invites.status", "auth.user_invites", {})

def issue(values):
    return request("auth_flows.user_invites.issue", "auth.user_invites", {"email": values.get("email", "")})

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
