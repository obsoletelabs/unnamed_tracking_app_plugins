"""Expired signers preserve only reviewed archive bytes, never backdated releases."""

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import zipfile

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from tools.package_format import (
    canonical_payload_digest,
    signature_envelope,
    signature_message,
)
from tools.publisher_registry import (
    PublisherRecord,
    PublisherRegistryError,
    load_registry,
)
from tools.verify_packages import verify_package


CUTOFF = datetime(2026, 10, 7, 16, tzinfo=timezone.utc)


def record(**overrides):
    values = dict(
        key_id="rotation-test",
        publisher="Test",
        public_key=b"x" * 32,
        status="active",
        plugin_id_prefixes=("official.",),
        not_after=CUTOFF,
        plugin_ids=("example.self-service-session-manager",),
    )
    values.update(overrides)
    return PublisherRecord(**values)


def test_signing_stops_at_perth_midnight_without_expanding_the_official_scope():
    signer = record()
    before = CUTOFF - timedelta(microseconds=1)
    assert signer.allows_plugin("official.pwa", release=True, now=before)
    assert signer.allows_plugin(
        "example.self-service-session-manager", release=True, now=before
    )
    assert not signer.allows_plugin(
        "example.self-service-session-manager-extra", release=True, now=before
    )
    assert not signer.allows_plugin("example.other", release=True, now=before)
    assert not signer.allows_plugin("official.pwa", release=True, now=CUTOFF)
    assert not signer.allows_plugin(
        "official.pwa", release=True, now=CUTOFF + timedelta(days=1)
    )


def test_historical_pin_never_bypasses_revocation_scope_or_activation():
    digest = "a" * 64
    signer = record(historical_package_sha256=frozenset({digest}))
    assert signer.allows_package("official.pwa", digest, now=CUTOFF)
    assert not signer.allows_package("official.pwa", "b" * 64, now=CUTOFF)
    assert not signer.allows_package("other.pwa", digest, now=CUTOFF)
    assert not record(
        status="revoked", historical_package_sha256=frozenset({digest})
    ).allows_package("official.pwa", digest, now=CUTOFF)
    assert not record(
        not_before=CUTOFF + timedelta(days=1), not_after=None
    ).allows_package("official.pwa", digest, now=CUTOFF)


@pytest.mark.parametrize(
    "policy",
    [
        {"not_after": "2026-10-07T16:00:00"},
        {"not_after": 123},
        {"not_after": "invalid"},
        {"not_before": "2027-01-01T00:00:00Z", "not_after": "2026-01-01T00:00:00Z"},
        {"historical_package_sha256": ["bad"]},
        {"historical_package_sha256": ["a" * 64] * 2},
        {"historical_package_sha256": "a" * 64},
        {"plugin_ids": ["example.*"]},
        {"plugin_ids": ["example.one"] * 2},
        {"plugin_ids": [None]},
    ],
)
def test_registry_rejects_malformed_rotation_policy(tmp_path, policy):
    key = Ed25519PrivateKey.generate().public_key().public_bytes_raw()
    encoded = base64.b64encode(key).decode()
    (tmp_path / "key.b64").write_text(encoded)
    item = {
        "key_id": "rotation-test",
        "public_key_file": "key.b64",
        "public_key_b64": encoded,
        "public_key_sha256": hashlib.sha256(key).hexdigest(),
        "status": "active",
        "plugin_id_prefixes": ["official."],
        **policy,
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps({"schema_version": 1, "publishers": [item]}))
    with pytest.raises(PublisherRegistryError):
        load_registry(path)


def signed_archive(path, key, *, changed=False):
    manifest = {
        "plugin_id": "official.rotation-test",
        "name": "Rotation",
        "version": "1.0.0",
    }
    files = {
        "plugin.py": b"changed" if changed else b"original",
        "distribution.json": b'{"build":{"source_committed_at":"1970-01-01T00:00:00Z"}}',
        "package-signature-v2.json": json.dumps(
            signature_envelope(manifest, "rotation-test")
        ).encode(),
    }
    digest = canonical_payload_digest(files.items())
    manifest["integrity"] = {
        "key_id": "rotation-test",
        "sha256": digest,
        "signature": "v2:"
        + base64.b64encode(key.sign(signature_message(digest))).decode(),
    }
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name, content in files.items():
            archive.writestr("payload/" + name, content)


def test_verifier_accepts_exact_historical_archive_and_rejects_new_backdated_signature(
    tmp_path, monkeypatch
):
    key = Ed25519PrivateKey.generate()
    historical = tmp_path / "historical.utp"
    signed_archive(historical, key)
    pin = hashlib.sha256(historical.read_bytes()).hexdigest()
    signer = record(
        public_key=key.public_key().public_bytes_raw(),
        not_after=datetime(2000, 1, 1, tzinfo=timezone.utc),
        historical_package_sha256=frozenset({pin}),
    )
    monkeypatch.setattr(
        "tools.verify_packages.load_registry", lambda: {signer.key_id: signer}
    )
    verify_package(historical, require_signature=True)
    forged = tmp_path / "backdated.utp"
    signed_archive(forged, key, changed=True)
    with pytest.raises(PublisherRegistryError, match="trusted"):
        verify_package(forged, require_signature=True)
    with zipfile.ZipFile(historical, "a") as archive:
        archive.comment = b"changed container bytes"
    with pytest.raises(PublisherRegistryError, match="trusted"):
        verify_package(historical, require_signature=True)
