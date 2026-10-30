from __future__ import annotations

from pathlib import Path
import json
import sys
import zipfile

import pytest

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from publisher_registry import PublisherRegistryError, load_registry, release_signer
from package_format import canonical_payload_digest
from verify_packages import verify_package


def test_registry_matches_reviewed_public_key_files() -> None:
    registry = load_registry()
    historical = {"official-example-2026", "official-example-2026-additional", "non-secret-testkey",
                  "unnamed-tracking-examples-2026-10-v1", "unnamed-tracking-official-2026-10-v1",
                  "unnamed-tracking-generic-2026-10-v1"}
    current = {"unnamed-tracking-examples-2026-10-07-v2", "unnamed-tracking-official-2026-10-07-v2",
               "unnamed-tracking-generic-2026-10-07-v2"}
    assert set(registry) == historical | current
    assert all(registry[key].not_after is not None for key in historical)
    official = registry["unnamed-tracking-official-2026-10-07-v2"]
    assert official.channel == "official" and official.allows_plugin("official.pwa", release=True)
    assert not official.allows_plugin("example.lifecycle")
    assert official.allows_plugin("example.self-service-session-manager", release=True)
    assert not official.allows_plugin("example.self-service-session-manager-extra")
    examples = registry["unnamed-tracking-examples-2026-10-07-v2"]
    assert examples.channel == "demo" and examples.allows_plugin("example.lifecycle", release=True)
    generic = registry["unnamed-tracking-generic-2026-10-07-v2"]
    assert generic.channel == "community" and generic.allows_plugin("example.lifecycle", release=True)
    assert generic.allows_plugin("plugin.lifecycle", release=True)
    assert not examples.allows_plugin("official.pwa")
    assert not generic.allows_plugin("official.pwa")
    assert {registry[key].publisher for key in current} == {"Unnamed Tracking Official"}


def test_release_signer_requires_an_active_scoped_registered_key() -> None:
    record = load_registry()["unnamed-tracking-examples-2026-10-07-v2"]
    assert release_signer(record.key_id, ("example.lifecycle",), record.public_key) == record
    with pytest.raises(PublisherRegistryError, match="scope"):
        release_signer(record.key_id, ("untrusted.plugin",), record.public_key)


def test_checked_in_packages_verify_with_the_publisher_registry() -> None:
    for package in (ROOT / "dist").glob("*.utp"):
        verify_package(package)


def test_canonical_payload_digest_is_order_independent_and_content_bound() -> None:
    entries = [("sdk/protocol.py", b"protocol"), ("plugin.py", b"plugin")]
    digest = canonical_payload_digest(entries)
    assert digest == canonical_payload_digest(reversed(entries))
    assert digest != canonical_payload_digest([("sdk/protocol.py", b"changed"), entries[1]])


EXPOSED_KEY = "non-secret-testkey"


def _signed_by(key_id: str) -> set[str]:
    signed = set()
    for package in (ROOT / "dist").glob("*.utp"):
        with zipfile.ZipFile(package) as archive:
            integrity = json.loads(archive.read("manifest.json"))["integrity"]
        if integrity.get("key_id") == key_id:
            signed.add(package.name)
    return signed


def test_exposed_test_key_is_never_active() -> None:
    record = load_registry()[EXPOSED_KEY]
    assert record.status in {"retiring", "revoked"}
    assert not record.allows_plugin("example.lifecycle", release=True)
    with pytest.raises(PublisherRegistryError, match="inactive"):
        release_signer(EXPOSED_KEY, ("example.lifecycle",), record.public_key)


def test_exposed_test_key_signs_no_new_packages() -> None:
    # The seed is public, so only the frozen historical set may carry its key id.
    assert len(_signed_by(EXPOSED_KEY)) == 33
    assert not any(name.startswith("official.") for name in _signed_by(EXPOSED_KEY))


def _copy_with_key(tmp_path: Path, key_id: str) -> Path:
    source = next(
        package for package in sorted((ROOT / "dist").glob("example.*-*.utp"))
        if package.name in _signed_by(EXPOSED_KEY)
    )
    target = tmp_path / source.name
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w") as dst:
        for item in src.infolist():
            data = src.read(item.filename)
            if item.filename == "manifest.json":
                manifest = json.loads(data)
                manifest["integrity"]["key_id"] = key_id
                data = json.dumps(manifest).encode()
            dst.writestr(item, data)
    return target


def test_revoked_registry_entry_rejects_its_signatures(tmp_path: Path, monkeypatch) -> None:
    registry = json.loads((ROOT / "publishers" / "registry.json").read_text(encoding="utf-8"))
    for entry in registry["publishers"]:
        if entry["key_id"] == EXPOSED_KEY:
            entry["status"] = "revoked"
    (tmp_path / "registry.json").write_text(json.dumps(registry), encoding="utf-8")
    for key_file in (ROOT / "publishers").glob("*.public-key.b64"):
        (tmp_path / key_file.name).write_text(key_file.read_text())
    import verify_packages

    original = verify_packages.load_registry
    monkeypatch.setattr(verify_packages, "load_registry", lambda: original(tmp_path / "registry.json"))
    package = next(
        package for package in sorted((ROOT / "dist").glob("*.utp")) if package.name in _signed_by(EXPOSED_KEY)
    )
    with pytest.raises(PublisherRegistryError, match="not trusted"):
        verify_package(package)


def test_forged_signature_claiming_the_exposed_key_is_rejected(tmp_path: Path) -> None:
    forged = _copy_with_key(tmp_path, "unnamed-tracking-examples-2026-10-v1")
    with pytest.raises(Exception):
        verify_package(forged)
