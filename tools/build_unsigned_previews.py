"""Build installable, explicitly unsigned HEAD previews without publishing releases."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from tools.build_packages import write_package
from tools.distribution import (ROOT, canonical_json, collect_payload, discover_plugins,
    git, load_histories, next_release, source_digest)
from tools.package_format import SIGNATURE_ENVELOPE, canonical_payload_digest, signature_envelope
from tools.validate_packages import validate_package
from tools.verify_packages import verify_package


def build(root: Path, output: Path) -> list[dict]:
    if output.resolve() == (root / "dist").resolve():
        raise ValueError("unsigned previews must not overwrite published dist")
    output.mkdir(parents=True, exist_ok=True)
    histories = load_histories(root)
    commit = git(root, "rev-parse", "HEAD")
    records = []
    for source, original in discover_plugins(root):
        manifest = json.loads(json.dumps(original))
        files, metadata = collect_payload(root, source, manifest)
        fingerprint = source_digest(manifest, files)
        version, _, bump = next_release(root, source, manifest,
            histories.get(manifest["plugin_id"], []), fingerprint)
        manifest["version"] = version
        files["distribution.json"] = canonical_json({**metadata, "version": version,
            "automatic_update": False, "tags": sorted(set(metadata["tags"]) | {"preview"}),
            "release_notes": "Unsigned branch preview. Review permissions and enable untrusted installation to test this source snapshot.",
            "build": {"source_digest": fingerprint, "source_commit": commit,
                "source_path": source.relative_to(root).as_posix(),
                "builder": "tools/build_unsigned_previews.py", "version_bump": bump}})
        files[SIGNATURE_ENVELOPE] = canonical_json(signature_envelope(manifest, None))
        manifest["integrity"] = {"sha256": canonical_payload_digest(files.items()),
            "signature": None, "key_id": None}
        package = output / f"{manifest['plugin_id']}-{version}.utp"
        write_package(package, manifest, files)
        validate_package(package, full=True)
        verify_package(package)
        records.append({"plugin_id": manifest["plugin_id"], "version": version,
            "package": package.name, "package_sha256": hashlib.sha256(package.read_bytes()).hexdigest(),
            "source_digest": fingerprint, "source_commit": commit, "signed": False})
    (output / "index.json").write_text(json.dumps(records, indent=2) + "\n", encoding="utf-8")
    (output / "README.md").write_text(
        "# Unsigned branch previews\n\n"
        f"Source commit: `{commit}`. Each .utp is built from this branch's current source. "
        "These are previews, not published or trusted releases.\n\n"
        "In Administration → Plugins → Install, upload the chosen .utp. Review its "
        "permissions, explicitly allow the untrusted preview, and reauthenticate if asked. "
        "An older version is pinned and automatic updates are disabled by the host. "
        "Keep it pinned while testing; use the normal update review to return to a verified release.\n", encoding="utf-8")
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "unsigned-dist")
    args = parser.parse_args()
    print(f"Built {len(build(ROOT, args.output.resolve()))} unsigned source previews")


if __name__ == "__main__":
    main()
