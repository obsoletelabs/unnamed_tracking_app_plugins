"""Independent public-contract demos and their packaged SDK behavior."""

import hashlib
import importlib.util
import json
import subprocess
import sys
import zipfile
from io import StringIO
from pathlib import Path
from uuid import uuid4

import pytest

from sdk import notifications

ROOT = Path(__file__).parents[1]
NAMES = ("password-reset-notification-demo", "user-invite-notification-demo")


def load(name, root=ROOT):
    spec = importlib.util.spec_from_file_location(
        "notification_demo_" + name.replace("-", "_"), root / "examples" / name / "plugin.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(params=NAMES)
def demo(request, monkeypatch):
    module = load(request.param)
    store, calls = {}, []

    def gateway(method, capability, payload):
        calls.append((method, capability, payload))
        if method == "storage.put":
            store[payload["key"]] = payload["value"]
            return {}
        if method == "storage.get":
            return {"value": store.get(payload["key"])}
        if method == "notification_sources.register":
            return {"registered": True}
        if method == "notifications.emit":
            return {"created": True, "notification_id": str(uuid4())}
        raise AssertionError(f"Unexpected gateway method {method}")

    monkeypatch.setattr(module, "request", gateway)
    monkeypatch.setattr(notifications, "request", gateway)
    return module, store, calls


def context(user=None):
    return {"_plugin_context": {"user_id": str(user or uuid4())}}


def test_demos_emit_bound_typed_facts_without_returning_token_or_credentials(demo):
    module, store, calls = demo
    result = module.issue(context())
    assert result["accepted"] and result["demo_only"]
    declaration = next(payload for method, _, payload in calls if method == "notification_sources.register")
    emission = next(payload for method, _, payload in calls if method == "notifications.emit")
    assert declaration["event_type"] == emission["event_type"] == module.EVENT_TYPE
    assert set(emission) == {"event_type", "dedupe_key", "occurred_at", "data", "group_key"}
    token = emission["data"]["token"]
    assert len(token) >= 32 and token not in json.dumps(result)
    assert token not in json.dumps(store)
    record = json.loads(next(iter(store.values())))
    assert record["digest"] == hashlib.sha256(token.encode()).hexdigest()
    assert record["expires_at"] == emission["occurred_at"] + 600
    assert not record["consumed"]
    assert all("user_id" not in payload and "destination_id" not in payload
               for method, _, payload in calls if method.startswith("notification"))


def test_demo_confirmation_is_explicit_owned_and_rejects_sequential_replay(demo):
    module, store, calls = demo
    owner = context()
    module.issue(owner)
    token = calls[-1][2]["data"]["token"]
    with pytest.raises(ValueError, match="invalid"):
        module.confirm({**context(), "token": token})
    with pytest.raises(ValueError, match="invalid"):
        module.confirm({**owner, "token": "changed"})
    assert not json.loads(next(iter(store.values())))["consumed"]
    result = module.confirm({**owner, "token": token})
    assert result == {"confirmed": True, "demo_only": True, "authentication_changed": False}
    with pytest.raises(ValueError, match="already used"):
        module.confirm({**owner, "token": token})
    assert "digest" not in json.loads(next(iter(store.values())))


def test_expiry_replacement_and_missing_context(demo, monkeypatch):
    module, _, calls = demo
    for missing in ({}, {"_plugin_context": {"user_id": "invalid"}}):
        with pytest.raises(ValueError, match="authenticated"):
            module.issue(missing)
    owner = context()
    module.issue(owner)
    old = calls[-1][2]["data"]["token"]
    module.issue(owner)
    new = calls[-1][2]["data"]["token"]
    assert old != new
    with pytest.raises(ValueError, match="invalid"):
        module.confirm({**owner, "token": old})
    now = int(module.time.time())
    monkeypatch.setattr(module.time, "time", lambda: now + 601)
    with pytest.raises(ValueError, match="expired"):
        module.confirm({**owner, "token": new})


def test_demo_permission_and_sensitivity_contracts():
    for name in NAMES:
        source = ROOT / "examples" / name
        manifest = json.loads((source / "manifest.json").read_text())
        module = load(name)
        caps = {item["name"] for item in manifest["capabilities"]}
        base = {"notifications.emit", "notification_sources.register", "plugin.storage"}
        recovery = name.startswith("password-reset")
        assert caps == base | ({"notifications.sensitive"} if recovery else set())
        assert {item["capability"]["name"] for item in manifest["permissions"]} == caps
        assert module.DEFINITION["required_trust"] == ("SECURE" if recovery else "PRIVATE")
        assert module.DEFINITION["purpose"] == ("recovery" if recovery else "standard")
        assert module.EVENT_TYPE.startswith(manifest["plugin_id"] + ".")
        assert manifest["api_contract_version"] == "1.1.2"
        assert not any(cap.startswith(("network", "users", "api.full")) for cap in caps)


def test_sdk_serializes_only_public_facts_and_handles_host_errors(monkeypatch, capsys):
    monkeypatch.setattr(sys, "stdin", StringIO('{"payload":{"created":true}}\n'))
    assert notifications.emit("example.test.changed", "key", 123, {"count": 2})["created"]
    wire = json.loads(capsys.readouterr().out)
    assert wire == {"api_version": "v1", "method": "notifications.emit", "capability": "notifications.emit",
                    "payload": {"event_type": "example.test.changed", "dedupe_key": "key", "occurred_at": 123,
                                "data": {"count": 2}}}
    monkeypatch.setattr(sys, "stdin", StringIO('{"error":"Explicit high-risk grant required"}\n'))
    with pytest.raises(RuntimeError, match="high-risk"):
        notifications.register_type({"event_type": "example.test.recovery"})


@pytest.mark.parametrize("name", NAMES)
def test_actual_package_contains_standalone_executable_demo(current_packages, tmp_path, name):
    plugin_id = "example." + name
    with zipfile.ZipFile(current_packages[plugin_id]) as archive:
        assert "payload/sdk/notifications.py" in archive.namelist()
        for path in archive.namelist():
            if path.startswith("payload/") and not path.endswith("/"):
                target = tmp_path / path.removeprefix("payload/")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(path))
    # The package imports only its included SDK and Python's standard library.
    result = subprocess.run([sys.executable, "-c", "import plugin; assert callable(plugin.issue); assert callable(plugin.confirm)"],
                            cwd=tmp_path, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
