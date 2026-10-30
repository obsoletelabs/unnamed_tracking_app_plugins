"""Official producers on the story contract, from a real package built with a throwaway key."""
import base64
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sdk import notification_stories as stories
from tools.distribution import ROOT
from tools.validate_packages import validate_package

PLUGIN = "official.jellyfin-media-sync"
SOURCE = ROOT / "official/jellyfin-media-sync"


@pytest.fixture(name="signed")
def signed_fixture(tmp_path):
    """The real Jellyfin plugin, built and signed by the publisher tooling with a throwaway key."""
    for name in ("tools", "sdk"):
        shutil.copytree(ROOT / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(SOURCE, tmp_path / "official/jellyfin-media-sync",
                    ignore=shutil.ignore_patterns("__pycache__"))
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes_raw()
    encoded = base64.b64encode(public).decode()
    (tmp_path / "publishers").mkdir()
    (tmp_path / "publishers/throwaway.public-key.b64").write_text(encoded)
    (tmp_path / "publishers/registry.json").write_text(json.dumps({"schema_version": 1, "publishers": [{
        "key_id": "throwaway", "publisher": "Unnamed Tracking Official", "channel": "official",
        "public_key_file": "throwaway.public-key.b64", "public_key_b64": encoded,
        "public_key_sha256": hashlib.sha256(public).hexdigest(), "status": "active",
        "plugin_id_prefixes": ["official."]}]}))
    (tmp_path / "catalogue.json").write_text(json.dumps({
        "base_url": "https://example.invalid", "name": "Throwaway", "unreleased_plugins": []}))
    (tmp_path / ".gitignore").write_text(".validation/\n__pycache__/\n")
    for command in (["init"], ["config", "user.name", "Test"],
                    ["config", "user.email", "test@example.invalid"], ["add", "."],
                    ["commit", "-m", "feat: prepare official producers"]):
        subprocess.run(["git", "-C", str(tmp_path), *command], check=True, capture_output=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PLUGIN_")}
    env["PLUGIN_OFFICIAL_SIGNING_KEY_ID"] = "throwaway"
    env["PLUGIN_OFFICIAL_SIGNING_KEY_B64"] = base64.b64encode(key.private_bytes_raw()).decode()
    result = subprocess.run([sys.executable, str(tmp_path / "tools/build_packages.py"), "--publish"],
                            env=env, capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    return tmp_path, next((tmp_path / "dist").glob(f"{PLUGIN}-*.utp"))


def entries_of(path):
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_signed_jellyfin_package_declares_the_story_capabilities_and_verifies(signed):
    root, package = signed
    entries = entries_of(package)
    manifest = json.loads(entries["manifest.json"])
    assert manifest["integrity"]["signature"].startswith("v2:")
    assert manifest["api_contract_version"] == "1.1.18"
    assert manifest["native_frontend"]["activation"] == "page"
    names = {item["name"] for item in manifest["capabilities"]}
    assert {"notification_sources.register", "notifications.canonical", "notifications.send"} <= names
    # Every capability is justified by a permission and no wider notification authority is asked.
    assert names == {item["capability"]["name"] for item in manifest["permissions"]}
    assert not names & {"notifications.sensitive", "notifications.urgency", "api.full"}
    assert "payload/attention.py" in entries
    validate_package(package)
    verified = subprocess.run([sys.executable, str(root / "tools/verify_packages.py"), str(package)],
                              capture_output=True, text=True)
    assert verified.returncode == 0, verified.stderr


def test_packaged_producer_publishes_a_valid_contract_story(signed, tmp_path_factory):
    _, package = signed
    target = tmp_path_factory.mktemp("payload")
    with zipfile.ZipFile(package) as archive:
        for name in archive.namelist():
            if name.startswith("payload/") and not name.endswith("/"):
                destination = target / name.removeprefix("payload/")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.read(name))
    sent = []
    code = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "import sdk.notification_stories as stories\n"
        "import attention\n"
        "calls = []\n"
        "def gateway(method, capability, payload):\n"
        "    calls.append([method, capability, payload]); return {}\n"
        "stories.request = gateway; attention.request = gateway\n"
        "account = {'id': 'a1', 'name': 'Living room'}\n"
        "attention.report_problem('00000000-0000-4000-8000-000000000001', account, 'Home', 'Check the token.')\n"
        "attention.report_recovered('00000000-0000-4000-8000-000000000001', account, 'Home')\n"
        "print(json.dumps(calls))\n"
    )
    result = subprocess.run([sys.executable, "-I", "-c", code, str(target)], capture_output=True,
                            text=True)
    assert result.returncode == 0, result.stderr
    sent = json.loads(result.stdout)
    assert [c[2]["method"] for c in sent] == [
        "notification_sources.register", "notifications.publish",
        "notification_sources.register", "notifications.publish"]
    assert {c[1] for c in sent} == {"tasks.background"}
    first, last = sent[1][2]["payload"], sent[3][2]["payload"]
    assert [first["story"]["phase"], last["story"]["phase"]] == ["attention", "resolved"]
    assert first["story"]["key"] == last["story"]["key"] == "sync:a1"
    assert first["event_id"] != last["event_id"] and "recipient" not in json.dumps(sent)
    registration = sent[0][2]["payload"]
    stories.check_registration(registration)
    stories.check_event(first, registration)
    stories.check_event(last, registration)


def test_user_scoped_helpers_use_only_reviewed_background_operations(monkeypatch):
    calls = []
    monkeypatch.setattr(stories, "request", lambda *args: calls.append(args) or {})
    spec = importlib.util.spec_from_file_location("attention", SOURCE / "attention.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    user = "00000000-0000-4000-8000-000000000001"
    stories.register_canonical_type_for_user(user, module.REGISTRATION)
    assert [(c[0], c[1], c[2]["method"], c[2]["capability"]) for c in calls] == [
        ("tasks.request", "tasks.background", "notification_sources.register",
         "notification_sources.register")]
    with pytest.raises(stories.ContractError):
        stories.publish_for_user(user, {"event_type": "x"})
    assert len(calls) == 1


def test_jellyfin_registration_is_scoped_to_the_plugin_and_has_a_closed_lifecycle():
    spec = importlib.util.spec_from_file_location("attention", SOURCE / "attention.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    stories.check_registration(module.REGISTRATION)
    assert module.EVENT_TYPE.startswith(PLUGIN + ".")
    phases = {p["id"]: p for p in module.REGISTRATION["lifecycle"]["phases"]}
    assert phases["resolved"]["terminal"] and not phases["attention"].get("terminal")
