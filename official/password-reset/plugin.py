"""Maintained auth contribution; credentials and account mutations stay in the host."""

import json
import time

from sdk.plugin_protocol import request

KEY = "recovery/configuration"


def configuration():
    raw = request("storage.get", "plugin.storage", {"key": KEY}).get("value")
    return json.loads(raw) if raw else {}


def save(values):
    flow = definition({**configuration(), **values})
    live = request("auth_flows.password_reset.status", "auth.password_reset", {})
    if live.get("registered") is True:
        request("auth_flows.password_reset.register", "auth.password_reset", flow)
    request("storage.put", "plugin.storage", {"key": KEY, "value": json.dumps({"enabled": live.get("registered") is True, **flow})})
    return {"saved": True}


def definition(values):
    lifetime = values.get("token_lifetime_seconds", 1200)
    if isinstance(lifetime, bool) or not isinstance(lifetime, (int, float)) or int(lifetime) != lifetime or not 600 <= lifetime <= 3600:
        raise ValueError("Link lifetime must be an integer between 600 and 3600 seconds")
    return {"mode": "password_reset", "name": "Password Reset", "token_lifetime_seconds": int(lifetime)}


def status(values):
    del values
    live = request("auth_flows.password_reset.status", "auth.password_reset", {})
    stored = definition(configuration())
    return {**live, "token_lifetime_seconds": live.get("token_lifetime_seconds", stored["token_lifetime_seconds"]) if live.get("registered") else stored["token_lifetime_seconds"]}


def enable(values):
    flow = definition({**configuration(), **values})
    result = request("auth_flows.password_reset.register", "auth.password_reset", flow)
    request("storage.put", "plugin.storage", {"key": KEY, "value": json.dumps({"enabled": True, **flow})})
    return {"enabled": True, "token_lifetime_seconds": flow["token_lifetime_seconds"], "registered": result.get("registered") is True}


def disable(values):
    del values
    result = request("auth_flows.password_reset.unregister", "auth.password_reset", {})
    stored = configuration()
    request("storage.put", "plugin.storage", {"key": KEY, "value": json.dumps({**stored, "enabled": False})})
    return {"enabled": False, "registered": result.get("registered") is True}


def restore_configuration():
    raw = request("storage.get", "plugin.storage", {"key": KEY}).get("value")
    stored = json.loads(raw) if raw is not None else {}
    if stored.get("enabled") is True:
        request("auth_flows.password_reset.restore", "auth.password_reset", definition(stored))


def main():
    request("lifecycle.ready", "lifecycle.ready", {})
    restore_configuration()
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
