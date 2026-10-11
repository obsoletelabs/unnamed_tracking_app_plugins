"""Branch builds stay digest-valid while preserving immutable release artifacts."""

import json
import zipfile
from pathlib import Path

import pytest
import yaml

from tools.build_unsigned_previews import build
from tools.distribution import ROOT


def test_branch_previews_have_no_signer_and_leave_published_files_untouched(tmp_path):
    originals = {path: path.read_bytes() for directory in ("dist", "releases")
        for path in (ROOT / directory).glob("*") if path.is_file()}
    previews = build(ROOT, tmp_path / "unsigned-dist")
    assert len(previews) >= 15
    assert any(item["plugin_id"] == "official.collectors-archive" for item in previews)
    for item in previews:
        with zipfile.ZipFile(tmp_path / "unsigned-dist" / item["package"]) as package:
            manifest = json.loads(package.read("manifest.json"))
            metadata = json.loads(package.read("payload/distribution.json"))
            assert manifest["integrity"]["signature"] is None
            assert manifest["integrity"]["key_id"] is None
            assert metadata["automatic_update"] is False
            assert metadata["build"]["source_digest"] == item["source_digest"]
    assert all(path.read_bytes() == before for path, before in originals.items())


def test_branch_previews_reject_published_output():
    with pytest.raises(ValueError, match="published"):
        build(ROOT, ROOT / "dist")


def test_workflows_parse_and_unsigned_previews_run_for_all_branch_pushes():
    workflows = ROOT / ".github/workflows"
    for path in workflows.glob("*.yml"):
        assert isinstance(yaml.load(path.read_text(), Loader=yaml.BaseLoader), dict)
    checks = yaml.load((workflows / "ci.yml").read_text(), Loader=yaml.BaseLoader)
    assert "push" in checks["on"] and checks["on"]["push"] in ("", {})
    assert "pull_request" in checks["on"]
    preview = checks["jobs"]["unsigned-dist"]
    assert "if" not in preview
    assert any(step.get("with", {}).get("name") == "unsigned-dist" for step in preview["steps"])
    publication = yaml.load((workflows / "publish.yml").read_text(), Loader=yaml.BaseLoader)
    assert publication["on"]["push"]["branches"] == ["**"]


def test_bot_release_matches_registered_official_publisher_and_retains_manual_updates():
    """A maintained bot release must be signable without changing registry authority."""
    from tools.publisher_registry import load_registry

    source = ROOT / "official/discord-bot-notifications"
    release = json.loads((source / "release.json").read_text())
    manifest = json.loads((source / "manifest.json").read_text())
    assert release["publisher"] == "Unnamed Tracking Official"
    assert release["automatic_update"] is False
    assert any(
        record.publisher == release["publisher"]
        and record.channel == "official"
        and record.allows_plugin(manifest["plugin_id"], release=True)
        for record in load_registry().values()
    )
