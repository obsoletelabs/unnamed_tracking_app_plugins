from __future__ import annotations

import json
import shutil
import subprocess
import sys
import zipfile

import pytest
from test_domain_plugins import ROOT, plugin_root

from tools.package_format import canonical_payload_digest
from tools.validate_packages import validate_package
from tools.verify_packages import verify_package


@pytest.fixture
def packages(tmp_path):
    # Build an independent checkout; tests must not overwrite signed repository dist.
    for directory in ("tools", "sdk", "publishers"):
        shutil.copytree(
            ROOT / directory,
            tmp_path / directory,
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    for name in ("help-button", "jellyfin-media-sync", "extended-session-manager"):
        shutil.copytree(
            plugin_root(name),
            tmp_path / plugin_root(name).relative_to(ROOT),
            ignore=shutil.ignore_patterns("__pycache__"),
        )
    build = [sys.executable, str(tmp_path / "tools/build_packages.py"), "--output-root", str(tmp_path / "build")]
    subprocess.run(build, check=True, capture_output=True)
    first = {x.name: x.read_bytes() for x in (tmp_path / "build/dist").glob("*.utp")}
    subprocess.run(build, check=True, capture_output=True)
    assert first == {x.name: x.read_bytes() for x in (tmp_path / "build/dist").glob("*.utp")}
    return list((tmp_path / "build/dist").glob("*.utp"))


def test_native_assets_manifest_and_integrity_in_real_packages(packages):
    assert len(packages) == 3
    for path in packages:
        validate_package(path)
        verify_package(path)
        with zipfile.ZipFile(path) as archive:
            manifest = json.loads(archive.read("manifest.json"))
            files = {
                name.removeprefix("payload/"): archive.read(name)
                for name in archive.namelist()
                if name.startswith("payload/")
            }
        source_manifest = next(
            data for name in ("help-button", "jellyfin-media-sync", "extended-session-manager")
            if (data := json.loads((plugin_root(name) / "manifest.json").read_text(encoding="utf-8")))["plugin_id"] == manifest["plugin_id"]
        )
        expected_version = source_manifest["version"]
        assert manifest["version"] == expected_version
        assert manifest["integrity"]["signature"] is None
        assert manifest["integrity"]["sha256"] == canonical_payload_digest(
            files.items()
        )
        assert manifest["native_frontend"]["entry"] in files
        assert all(x in files for x in manifest["native_frontend"]["styles"])
        assert b"SECRET-token" not in b"".join(files.values())


@pytest.mark.parametrize("defect", ["undeclared", "ungranted", "missing-page"])
def test_session_replacement_contract_is_checked_in_the_actual_package(packages, defect):
    from tools.validate_packages import validate_current_contract

    path = next(path for path in packages if "self-service-session-manager" in path.name)
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        files = {name.removeprefix("payload/"): archive.read(name)
                 for name in archive.namelist() if name.startswith("payload/")}
    validate_current_contract(manifest, files)
    if defect == "missing-page":
        document = json.loads(files["ui.json"])
        document["page_replacements"][0]["page_id"] = "missing"
        files["ui.json"] = json.dumps(document).encode()
    elif defect == "undeclared":
        manifest["capabilities"] = [item for item in manifest["capabilities"]
                                    if item["name"] != "frontend.page.replace.sessions"]
    else:
        manifest["permissions"] = [item for item in manifest["permissions"]
                                   if item["capability"]["name"] != "frontend.page.replace.sessions"]
    with pytest.raises(ValueError, match="missing page|permissions"):
        validate_current_contract(manifest, files)


def test_native_asset_absence_and_permission_denial_are_rejected(packages, tmp_path):
    with zipfile.ZipFile(packages[0]) as archive:
        files = {name: archive.read(name) for name in archive.namelist()}
    manifest = json.loads(files["manifest.json"])
    for mode in ("missing", "denied", "traversal"):
        candidate = json.loads(json.dumps(manifest))
        if mode == "missing":
            candidate["native_frontend"]["entry"] = "native/missing.js"
        if mode == "traversal":
            candidate["native_frontend"]["entry"] = "native/../plugin.py"
        if mode == "denied":
            candidate["capabilities"] = [
                x for x in candidate["capabilities"] if x["name"] != "frontend.native"
            ]
            candidate["permissions"] = [
                x
                for x in candidate["permissions"]
                if x["capability"]["name"] != "frontend.native"
            ]
        path = tmp_path / (mode + ".utp")
        with zipfile.ZipFile(path, "w") as archive:
            for name, data in files.items():
                archive.writestr(
                    name, json.dumps(candidate) if name == "manifest.json" else data
                )
        with pytest.raises(ValueError, match="native"):
            validate_package(path)


def test_modified_payload_is_rejected(packages, tmp_path):
    path = tmp_path / "modified.utp"
    with (
        zipfile.ZipFile(packages[0]) as original,
        zipfile.ZipFile(path, "w") as changed,
    ):
        for name in original.namelist():
            changed.writestr(
                name,
                b"tampered" if name == "payload/native/app.js" else original.read(name),
            )
    with pytest.raises(ValueError, match="digest"):
        verify_package(path)
