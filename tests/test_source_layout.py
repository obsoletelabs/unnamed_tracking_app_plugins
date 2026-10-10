"""Fail rather than silently dropping misplaced or incomplete plugin sources."""
import json
import shutil

import pytest

from tools.check_source_layout import check
from tools.distribution import ROOT, discover_plugins


def test_all_maintained_sources_have_full_contracts(built_distribution):
    check()
    current = json.loads((built_distribution / "list.json").read_text(encoding="utf-8"))
    assert {m["plugin_id"] for _, m in discover_plugins(ROOT)} == {
        p["plugin_id"] for p in current["plugins"]
    }


@pytest.mark.parametrize("contract", [None, "1.0.0"])
def test_source_validation_rejects_unmigrated_contracts(tmp_path, contract):
    shutil.copytree(ROOT / "examples/ui-api", tmp_path / "examples/ui-api")
    path = tmp_path / "examples/ui-api/manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if contract is None:
        manifest.pop("api_contract_version")
    else:
        manifest["api_contract_version"] = contract
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="explicitly target a supported Plugin API contract version"):
        check(tmp_path)


@pytest.mark.parametrize("defect", ["old_tree", "missing_manifest", "missing_entrypoint", "duplicate_id"])
def test_discovery_rejects_layout_drift(tmp_path, defect):
    shutil.copytree(ROOT / "examples/ui-api", tmp_path / "examples/ui-api")
    if defect == "old_tree":
        (tmp_path / "examples.old").mkdir()
    elif defect == "missing_manifest":
        (tmp_path / "examples/stub").mkdir()
        (tmp_path / "examples/stub/README.md").write_text("Obsolete stub", encoding="utf-8")
    elif defect == "missing_entrypoint":
        (tmp_path / "examples/ui-api/plugin.py").unlink()
    else:
        shutil.copytree(tmp_path / "examples/ui-api", tmp_path / "examples/duplicate")
    with pytest.raises(ValueError):
        discover_plugins(tmp_path)
