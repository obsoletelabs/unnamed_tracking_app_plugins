"""Verify distributable packages against the reviewed publisher registry."""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import sys
import zipfile

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

try:
    from .publisher_registry import PublisherRegistryError, load_registry
    from .package_format import canonical_payload_digest, SIGNATURE_ENVELOPE, signature_envelope, signature_message
except ImportError:  # Direct script execution keeps tools independently usable.
    from publisher_registry import PublisherRegistryError, load_registry
    from package_format import canonical_payload_digest, SIGNATURE_ENVELOPE, signature_envelope, signature_message


def verify_package(path: Path, *, require_signature: bool = False) -> None:
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        files = {
            name.removeprefix("payload/"): archive.read(name)
            for name in archive.namelist()
            if name.startswith("payload/") and not name.endswith("/")
        }
    payload_digest = canonical_payload_digest(files.items())
    integrity = manifest["integrity"]
    if integrity.get("sha256") != payload_digest:
        raise PublisherRegistryError("package payload digest does not match its manifest")
    # Local demo artifacts are deliberately unsigned. The host presents an
    # explicit untrusted-install confirmation before accepting them. Release
    # verification still requires a registered publisher signature.
    if integrity.get("signature") is None:
        if require_signature or integrity.get("key_id") is not None:
            raise PublisherRegistryError("release package requires a publisher signature")
        return
    signature = integrity["signature"]
    version = 2 if signature.startswith("v2:") else 1
    if version == 2:
        if json.loads(files.get(SIGNATURE_ENVELOPE, b"null")) != signature_envelope(manifest, integrity.get("key_id")):
            raise PublisherRegistryError("signed manifest envelope does not match")
    record = load_registry().get(integrity.get("key_id"))
    archive_sha256 = hashlib.sha256(path.read_bytes()).hexdigest()
    if record is None or not record.allows_package(manifest["plugin_id"], archive_sha256):
        raise PublisherRegistryError("package publisher is not trusted for this plugin")
    if version == 1:
        claim = {key: value for key, value in manifest.items() if key != "integrity"}
        claim_hash = hashlib.sha256(json.dumps(claim, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        if claim_hash not in record.legacy_manifest_hashes.get(payload_digest, []):
            raise PublisherRegistryError("legacy signed manifest is not reviewed; use a v2 package")
    Ed25519PublicKey.from_public_bytes(record.public_key).verify(
        base64.b64decode(signature.removeprefix("v2:"), validate=True),
        signature_message(payload_digest, version),
    )


def main() -> None:
    paths = [Path(value) for value in sys.argv[1:]]
    if not paths:
        raise SystemExit("at least one package path is required")
    for package in paths:
        verify_package(package)


if __name__ == "__main__":
    main()
