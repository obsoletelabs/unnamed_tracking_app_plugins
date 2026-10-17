"""Versioned notification contract: SDK helpers, shared conformance and a real signed package."""
import base64
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import zipfile
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import jsonschema
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from sdk import notification_stories as stories
from sdk import notifications
from sdk.notification_stories import ContractError
from tools.distribution import ROOT
from tools.validate_packages import validate_package

FIXTURES = ROOT / "tests/fixtures/notification_contract"
SCHEMAS = ROOT / "tools/schemas"
PLUGIN_CASES = json.loads((FIXTURES / "plugin_conformance.json").read_text(encoding="utf-8"))
CANONICAL_CASES = json.loads((FIXTURES / "canonical_conformance.json").read_text(encoding="utf-8"))
EXAMPLE = ROOT / "examples/story-notification-demo"


def load_example():
    spec = importlib.util.spec_from_file_location("story_demo", EXAMPLE / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DEMO = load_example()


def registration(**changes):
    return {**deepcopy(DEMO.REGISTRATION), **changes}


def event(phase="available", version="2.0.0"):
    return DEMO.event(version, phase)


# --- shared conformance -------------------------------------------------------------------------


# Rules only the host can decide: it knows the capability catalogue; the SDK mirrors the rest.
HOST_ONLY = {"type: action requires unknown capability"}


def schema_for(name):
    return json.loads((SCHEMAS / f"{name}.schema.json").read_text(encoding="utf-8"))


def validator(name):
    schema = schema_for(name)
    return jsonschema.Draft202012Validator(schema)


def semantic(document_type, document):
    """The SDK's own semantic checks, where it implements them."""
    if document_type == "notification-canonical-type-v1":
        stories.check_registration(document)
    elif document_type == "notification-canonical-event-v1":
        stories.check_event(document)
    elif document_type == "notification-delivery-operation":
        stories.delivery_operation(document)
    else:
        raise LookupError(document_type)


@pytest.mark.parametrize(
    "item", PLUGIN_CASES["cases"] + CANONICAL_CASES["cases"],
    ids=lambda item: item["name"] if isinstance(item, dict) else str(item),
)
def test_shared_cases_agree_with_pinned_schemas_and_sdk(item):
    """Valid documents pass the schema and the SDK; invalid ones fail at least one of them."""
    document_type = item["document_type"]
    structural = not list(validator(document_type).iter_errors(item["document"]))
    try:
        semantic(document_type, item["document"])
    except ContractError:
        accepted = False
    except LookupError:
        accepted = True  # no SDK-side check for this document; the schema is the contract
    else:
        accepted = True
    if item["valid"]:
        assert structural and accepted, item["name"]
    elif item["name"] not in HOST_ONLY:
        if document_type in {"notification-canonical-type-v1", "notification-canonical-event-v1"}:
            # Both layers are checked in one place: nothing invalid may pass both.
            assert not (structural and accepted), item["name"]


def test_every_published_document_has_a_pinned_schema():
    for name in (
        "notification-canonical-type-v1", "notification-canonical-delivery-v1",
        "notification-contract-negotiation-request-v1",
        "notification-contract-negotiation-result-v1", "notification-canonical-event-v1",
        "notification-canonical-content-v1", "notification-story-lifecycle-v1",
        "notification-provider-capabilities-v1", "notification-renderer-contribution-v1",
    ):
        schema = schema_for(name)
        assert schema["additionalProperties"] is False
        assert schema["x-notification-contract-version"] == stories.CONTRACT_VERSION
    assert schema_for("notification-canonical-type-v1")["x-api-contract-version"] == (
        stories.NOTIFICATION_API_VERSION
    )
    # Additive fields of the older documents are pinned, with their 1.1.14 identity.
    assert "include_revisions" in schema_for("notification-lifecycle-query-v1")["properties"]
    assert "revised" in json.dumps(schema_for("notification-lifecycle-page-v1"))
    assert "edit_action" in json.dumps(schema_for("notification-provider-v1"))


def test_manifest_and_ui_schemas_know_the_new_capabilities():
    for name in ("manifest-v1", "ui-v1"):
        enum = schema_for(name)["$defs"]["Capability"]["enum"]
        for capability in ("notifications.canonical", "notifications.actions",
                           "notifications.urgency", "notifications.templates.html"):
            assert capability in enum, (name, capability)


# --- registration and event validation ---------------------------------------------------------


def test_the_demo_registration_and_events_are_valid():
    stories.check_registration(DEMO.REGISTRATION)
    for phase in ("available", "installed", "failed"):
        stories.check_event(event(phase), DEMO.REGISTRATION)


@pytest.mark.parametrize("changes", [
    {"recipient": "someone"}, {"user_id": str(uuid4())}, {"destination_id": str(uuid4())},
    {"default_category": "system"}, {"purpose": "security"}, {"purpose": "recovery"},
    {"contract_version": "2.0.0"}, {"contract_version": "1.9.0"}, {"contract_version": "latest"},
    {"label": ""}, {"description": "x" * 501}, {"max_urgency": "emergency"},
    {"facts": [{"key": "a", "label": "A", "kind": "text"}] * 2},
    {"facts": [{"key": "a", "label": "A", "kind": "float"}]},
    {"facts": [{"key": f"k{i}", "label": "A", "kind": "text"} for i in range(25)]},
    {"actions": [{"action_id": "Bad Id", "label": "A"}]},
    {"actions": [{"action_id": "a.b", "label": "A", "requires": ["api.full"]}]},
    {"actions": [{"action_id": "a.b", "label": "A", "requires": ["notifications.sensitive"]}]},
    {"actions": [{"action_id": "a.b", "label": "A", "input": {"x": {"type": "object"}}}]},
    {"actions": [{"action_id": "a.b", "label": "A", "script": "alert(1)"}]},
    {"grouping": {"strategy": "everything"}},
])
def test_registration_rejects_unsafe_or_unsupported_declarations(changes):
    with pytest.raises(ContractError):
        stories.check_registration(registration(**changes))


def test_lifecycle_and_contribution_rules():
    document = registration()
    document["lifecycle"] = {**document["lifecycle"], "event_type": "example.other.x"}
    with pytest.raises(ContractError, match="another event type"):
        stories.check_registration(document)
    document = registration()
    document["lifecycle"]["transitions"].append({"from_phase": "installed", "to_phase": "failed"})
    with pytest.raises(ContractError, match="Terminal"):
        stories.check_registration(document)
    document = registration()
    document["lifecycle"]["phases"].append({"id": "orphan", "label": "Orphan"})
    with pytest.raises(ContractError, match="reachable"):
        stories.check_registration(document)
    document = registration()
    document["renderers"][0] = {**document["renderers"][0], "template": "{fact_undeclared}"}
    with pytest.raises(ContractError, match="declared facts"):
        stories.check_registration(document)
    for template in ("<script>x</script>", "<img src=x onerror=alert(1)>", "{title!r}",
                     "{title:>9999}", "{title.__class__}"):
        document = registration()
        document["renderers"][0] = {**document["renderers"][0], "surface": "email",
                                    "kind": "html_template", "template": template}
        with pytest.raises(ContractError):
            stories.check_registration(document)


@pytest.mark.parametrize("mutation,message", [
    (lambda d: d.update(recipient="x"), "unsupported fields"),
    (lambda d: d.update(contract_version="2.0.0"), "major"),
    (lambda d: d.update(urgency="emergency"), "urgency"),
    (lambda d: d["content"].update(title="x" * 501), "title"),
    (lambda d: d["content"].update(summary="x" * 10_001), "summary"),
    (lambda d: d["content"]["facts"].append({"key": "version", "label": "Dup",
                                             "value": {"kind": "text", "value": "x"}}), "unique"),
    (lambda d: d["content"].update(actions=[{"id": "go", "label": "Go",
        "target": {"kind": "link", "url": "http://insecure.example.com"}}]), "HTTPS"),
    (lambda d: d["content"].update(actions=[{"id": "go", "label": "Go",
        "target": {"kind": "link", "url": "javascript:alert(1)"}}]), "HTTPS"),
    (lambda d: d["content"].update(actions=[{"id": "go", "label": "Go",
        "target": {"kind": "host_route", "path": "/api/users"}}]), "API route"),
    (lambda d: d["content"].update(images=[{"source": {"kind": "external",
        "url": "https://user:pass@example.com/a.png"}}]), "credentials"),
    (lambda d: d["content"].update(expires_at=1), "expiry"),
])
def test_events_reject_oversized_or_unsafe_documents(mutation, message):
    document = event()
    mutation(document)
    with pytest.raises(ContractError, match=message):
        stories.check_event(document)


@pytest.mark.parametrize("mutation,message", [
    (lambda d: d.update(event_type="example.other.thing"), "another event type"),
    (lambda d: d.update(story=None), "belong to a story"),
    (lambda d: d["story"].update(key="other:1"), "prefix"),
    (lambda d: d["story"].update(phase="unknown"), "phase"),
    (lambda d: d.update(urgency="critical"), "urgency"),
    (lambda d: d.update(grouping_key=None), "grouping key"),
    (lambda d: d["content"].update(facts=[]), "required fact"),
    (lambda d: d["content"]["facts"][0]["value"].update(kind="integer", value=3), "kind"),
    (lambda d: d["content"]["actions"][0]["target"].update(action_id="wipe.all"), "not declared"),
    (lambda d: d["content"]["actions"][0]["target"].update(input={}), "required"),
    (lambda d: d["content"]["actions"][0]["target"].update(input={"version": 5}), "type string"),
    (lambda d: d["content"]["actions"][0]["target"].update(input={"version": "x" * 33}), "length"),
    (lambda d: d["content"]["actions"][0]["target"].update(input={"version": "1", "x": "y"}), "not declared"),
])
def test_events_must_follow_their_registration(mutation, message):
    document = event()
    mutation(document)
    with pytest.raises(ContractError, match=message):
        stories.check_event(document, DEMO.REGISTRATION)


# --- gateway shapes ------------------------------------------------------------------------------


@pytest.fixture(name="sent")
def sent_fixture(monkeypatch):
    calls = []

    def gateway(method, capability, payload):
        calls.append((method, capability, payload))
        if method == "notifications.contract":
            return {"negotiated": stories.CONTRACT_VERSION if payload["contract_version"] == "1.0.0" else None,
                    "reason": "unsupported major version"}
        return {"created": True, "notification_id": str(uuid4()), "registered": True}

    monkeypatch.setattr(stories, "request", gateway)
    return calls


def test_gateway_calls_use_the_explicit_capabilities(sent):
    stories.register_canonical_type(DEMO.REGISTRATION)
    stories.publish(event(), registration=DEMO.REGISTRATION)
    assert stories.negotiate_contract() == "1.0.0"
    assert [(m, c) for m, c, _ in sent] == [
        ("notification_sources.register", "notification_sources.register"),
        ("notifications.publish", "notifications.canonical"),
        ("notifications.contract", "notifications.canonical"),
    ]
    assert "recipient" not in json.dumps(sent) and "destination" not in json.dumps(sent)


def test_unsupported_contract_versions_raise_the_hosts_reason(sent):
    with pytest.raises(ContractError, match="unsupported major"):
        stories.negotiate_contract("2.0.0")


def test_invalid_documents_never_reach_the_gateway(sent):
    bad = event()
    bad["content"]["title"] = "x" * 501
    with pytest.raises(ContractError):
        stories.publish(bad)
    with pytest.raises(ContractError):
        stories.register_canonical_type(registration(recipient="x"))
    assert sent == []


def test_revision_replay_is_opt_in(monkeypatch):
    calls = []
    monkeypatch.setattr(notifications, "request", lambda m, c, p: calls.append(p) or {})
    notifications.poll_lifecycle("cursor", limit=5)
    notifications.poll_lifecycle(include_revisions=True)
    assert calls == [{"cursor": "cursor", "limit": 5},
                     {"cursor": None, "limit": 100, "include_revisions": True}]
    with pytest.raises(ValueError):
        notifications.poll_lifecycle(include_revisions="yes")


def test_provider_helpers_describe_edits_without_authority():
    declared = stories.provider_capabilities(message_updates="edit", links=True)
    assert declared["contract_version"] == "1.0.0"
    for bad in ({"trust": "SECURE"}, {"verification_supported": True}, {"message_updates": "rewrite"},
                {"action_buttons": 2}):
        with pytest.raises(ContractError):
            stories.provider_capabilities(**bad)
    assert stories.delivery_operation({"operation": "edit", "remote_ref": "m1"}) == ("edit", "m1")
    assert stories.delivery_operation({}) == ("send", None)
    for bad in ({"operation": "edit"}, {"operation": "delete"},
                {"operation": "send", "remote_ref": "x" * 513}):
        with pytest.raises(ContractError):
            stories.delivery_operation(bad)
    assert stories.delivery_result(success=False, gone=True) == {
        "success": False, "retryable": False, "gone": True}
    assert stories.delivery_result(success=True, remote_ref="m2")["remote_ref"] == "m2"
    with pytest.raises(ContractError):
        stories.delivery_result(success=True, remote_ref="")


def test_story_action_context_is_validated():
    context = {"operation": "story_action", "story_id": str(uuid4()), "revision": 2,
               "installation_id": str(uuid4())}
    assert stories.story_action_context({"_notification_context": context}) == context
    for bad in ({}, {"_notification_context": {**context, "operation": "deliver"}},
                {"_notification_context": {**context, "revision": 0}},
                {"_notification_context": {**context, "extra": 1}},
                {"_notification_context": {"operation": "story_action"}}):
        with pytest.raises(ContractError):
            stories.story_action_context(bad)


# --- the example plugin --------------------------------------------------------------------------


@pytest.fixture(name="demo")
def demo_fixture(monkeypatch, sent):
    store = {}

    def gateway(method, capability, payload):
        if method == "storage.put":
            store[payload["key"]] = payload["value"]
            return {}
        return {"created": True, "notification_id": str(uuid4()), "registered": True}

    monkeypatch.setattr(DEMO, "request", gateway)
    return store


def context(user):
    return {"_plugin_context": {"user_id": str(user)}}


def test_demo_publishes_a_story_for_the_authenticated_user_only(demo, sent):
    owner = uuid4()
    result = DEMO.announce({**context(owner), "version": "3.1.0"})
    assert result["accepted"] is True
    published = [payload for method, _, payload in sent if method == "notifications.publish"]
    assert published[0]["story"] == {"key": "update:3.1.0", "phase": "available"}
    assert published[0]["event_id"] == "3.1.0:available"
    assert str(owner) not in json.dumps(published)
    DEMO.finish({**context(owner), "version": "3.1.0"})
    assert [p["story"]["phase"] for m, _, p in sent if m == "notifications.publish"] == [
        "available", "installed"]
    with pytest.raises(ValueError, match="authenticated"):
        DEMO.announce({"version": "1.0.0"})


def test_acknowledge_needs_the_host_context(demo):
    owner, story = uuid4(), uuid4()
    with pytest.raises(ContractError):
        DEMO.acknowledge({**context(owner), "version": "2.0.0"})
    result = DEMO.acknowledge({
        **context(owner), "version": "2.0.0",
        "_notification_context": {"operation": "story_action", "story_id": str(story),
                                  "revision": 4, "installation_id": str(uuid4())},
    })
    assert result == {"message": "Version 2.0.0 acknowledged"}
    assert json.loads(demo[f"users/{owner}/acknowledged/{story}"]) == {
        "version": "2.0.0", "revision": 4}


# --- manifest and real signed package ------------------------------------------------------------


def test_manifest_declares_exactly_the_capabilities_it_uses():
    manifest = json.loads((EXAMPLE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["api_contract_version"] == "1.1.14"
    names = {item["name"] for item in manifest["capabilities"]}
    assert names == {"notification_sources.register", "notifications.canonical",
                     "notifications.actions", "plugin.storage"}
    assert names == {item["capability"]["name"] for item in manifest["permissions"]}
    assert "notifications.urgency" not in names and "notifications.templates.html" not in names


@pytest.mark.parametrize("version", ["1.1.13", "1.1.2"])
def test_older_contracts_cannot_use_the_versioned_capabilities(tmp_path, version):
    from tools.check_source_layout import check

    shutil.copytree(EXAMPLE, tmp_path / "examples/story-notification-demo")
    shutil.copytree(ROOT / "sdk", tmp_path / "sdk", ignore=shutil.ignore_patterns("__pycache__"))
    root = tmp_path / "examples/story-notification-demo"
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["api_contract_version"] = version
    document = json.loads((root / "ui.json").read_text())
    document["api_contract_version"] = version
    (root / "manifest.json").write_text(json.dumps(manifest))
    (root / "ui.json").write_text(json.dumps(document))
    with pytest.raises(ValueError, match="1.1.14"):
        check(tmp_path)


def test_notification_capabilities_need_their_explicit_permissions_and_a_canonical_grant(tmp_path):
    from tools.check_source_layout import check

    shutil.copytree(EXAMPLE, tmp_path / "examples/story-notification-demo")
    shutil.copytree(ROOT / "sdk", tmp_path / "sdk", ignore=shutil.ignore_patterns("__pycache__"))
    root = tmp_path / "examples/story-notification-demo"
    manifest = json.loads((root / "manifest.json").read_text())
    manifest["permissions"] = [
        item for item in manifest["permissions"]
        if item["capability"]["name"] != "notifications.actions"
    ]
    (root / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        check(tmp_path)


@pytest.fixture(name="signed")
def signed_fixture(tmp_path):
    """A signed package built by the real publisher with a throwaway demo key."""
    for name in ("tools", "sdk"):
        shutil.copytree(ROOT / name, tmp_path / name, ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(EXAMPLE, tmp_path / "examples/story-notification-demo")
    key = Ed25519PrivateKey.generate()
    public = key.public_key().public_bytes_raw()
    encoded = base64.b64encode(public).decode()
    (tmp_path / "publishers").mkdir()
    (tmp_path / "publishers/throwaway.public-key.b64").write_text(encoded)
    (tmp_path / "publishers/registry.json").write_text(json.dumps({"schema_version": 1, "publishers": [{
        "key_id": "throwaway", "publisher": "Unnamed Tracking Official", "channel": "demo",
        "public_key_file": "throwaway.public-key.b64", "public_key_b64": encoded,
        "public_key_sha256": hashlib.sha256(public).hexdigest(), "status": "active",
        "plugin_id_prefixes": ["example."]}]}))
    (tmp_path / "catalogue.json").write_text(json.dumps({
        "base_url": "https://example.invalid", "name": "Throwaway", "unreleased_plugins": []}))
    (tmp_path / ".gitignore").write_text(".validation/\n__pycache__/\n")
    for command in (["init"], ["config", "user.name", "Test"],
                    ["config", "user.email", "test@example.invalid"], ["add", "."],
                    ["commit", "-m", "feat: prepare story demo"]):
        subprocess.run(["git", "-C", str(tmp_path), *command], check=True, capture_output=True)
    env = {k: v for k, v in os.environ.items() if not k.startswith("PLUGIN_")}
    env["PLUGIN_EXAMPLES_SIGNING_KEY_ID"] = "throwaway"
    env["PLUGIN_EXAMPLES_SIGNING_KEY_B64"] = base64.b64encode(key.private_bytes_raw()).decode()
    result = subprocess.run([sys.executable, str(tmp_path / "tools/build_packages.py"), "--publish"],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return tmp_path, next((tmp_path / "dist").glob("example.story-notification-demo-*.utp"))


def read_package(path):
    with zipfile.ZipFile(path) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_real_signed_package_is_valid_and_verifies(signed):
    root, package = signed
    entries = read_package(package)
    manifest = json.loads(entries["manifest.json"])
    assert manifest["integrity"]["signature"].startswith("v2:")
    assert manifest["integrity"]["key_id"] == "throwaway"
    assert manifest["api_contract_version"] == "1.1.14"
    assert {item["name"] for item in manifest["capabilities"]} >= {
        "notifications.canonical", "notifications.actions"}
    assert b"notification_stories" in entries["payload/plugin.py"]
    assert "payload/sdk/notification_stories.py" in entries
    assert entries["payload/sdk/notification_stories.py"] == (ROOT / "sdk/notification_stories.py").read_bytes()
    validate_package(package)
    verified = subprocess.run([sys.executable, str(root / "tools/verify_packages.py"), str(package)],
                              capture_output=True, text=True)
    assert verified.returncode == 0, verified.stderr


@pytest.mark.parametrize("tamper", ["capability", "payload", "signature"])
def test_tampered_signed_packages_fail_verification(signed, tamper):
    root, package = signed
    entries = read_package(package)
    manifest = json.loads(entries["manifest.json"])
    if tamper == "capability":
        manifest["capabilities"].append({"name": "notifications.templates.html", "version": 1})
        manifest["permissions"].append({"capability": {"name": "notifications.templates.html",
                                                       "version": 1}, "rationale": "Escalate"})
    elif tamper == "payload":
        entries["payload/plugin.py"] += b"\n# changed\n"
    else:
        manifest["integrity"]["signature"] = "v2:" + base64.b64encode(bytes(64)).decode()
    entries["manifest.json"] = json.dumps(manifest).encode()
    tampered = root / f"tampered-{tamper}.utp"
    with zipfile.ZipFile(tampered, "w") as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    result = subprocess.run([sys.executable, str(root / "tools/verify_packages.py"), str(tampered)],
                            capture_output=True, text=True)
    assert result.returncode != 0
