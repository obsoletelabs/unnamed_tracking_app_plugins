from __future__ import annotations

from pathlib import Path
import sys

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
