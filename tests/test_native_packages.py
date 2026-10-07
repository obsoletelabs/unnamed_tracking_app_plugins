"""Reject native packages that omit assets or Critical frontend authority."""

import json
import zipfile
from pathlib import Path

import pytest
from tools.validate_packages import validate_package

ROOT = Path(__file__).parents[1]


@pytest.mark.parametrize(
    "defect", ["missing_entry", "missing_style", "missing_grant", "traversal"]
)
def test_native_asset_contract_is_validated(tmp_path, defect):
    manifest = json.loads(
        (ROOT / "official/extended-session-manager/manifest.json").read_text(encoding="utf-8")
    )
    files = {"native/index.js", "native/style.css", "frontend/index.html"}
    if defect == "missing_entry":
        files.remove("native/index.js")
    elif defect == "missing_style":
        files.remove("native/style.css")
    elif defect == "missing_grant":
        manifest["capabilities"] = [
            item
            for item in manifest["capabilities"]
            if item["name"] != "frontend.native"
        ]
    else:
        manifest["native_frontend"]["entry"] = "native/../index.js"
    package = tmp_path / "invalid.utp"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr("manifest.json", json.dumps(manifest))
        for name in files:
            archive.writestr("payload/" + name, "fixture")
    with pytest.raises(ValueError, match="native"):
        validate_package(package)
