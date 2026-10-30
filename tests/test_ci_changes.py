"""CI change selection: shared or unknown changes run everything; plugin diffs run their areas."""

from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))

from ci_changes import classify, everything


def test_unknown_change_sets_select_everything():
    assert classify(None) == everything()


@pytest.mark.parametrize("path", [
    "sdk/plugin_protocol.py", "tools/build_packages.py", "publishers/registry.json",
    ".github/workflows/ci.yml", "requirements-dev.txt", "package.json", "catalogue.json",
    "tools/ci_changes.py",
])
def test_shared_files_select_everything(path):
    selection = classify([path])
    assert selection["lifecycle"] and selection["lifecycle_reference"]
    assert selection["lifecycle_jellyfin"] and selection["lifecycle_pwa"] and selection["full_tests"]


def test_a_single_plugin_selects_only_its_acceptance_steps():
    jellyfin = classify(["official/jellyfin-media-sync/sync.py"])
    assert jellyfin["plugins"] == ["official/jellyfin-media-sync"]
    assert jellyfin["lifecycle"] and jellyfin["lifecycle_jellyfin"] and jellyfin["full_tests"]
    assert not jellyfin["lifecycle_pwa"] and not jellyfin["lifecycle_reference"]
    pwa = classify(["official/pwa/pwa/README.md"])
    assert pwa["lifecycle_pwa"] and not pwa["lifecycle_jellyfin"]
    example = classify(["examples/ui-api/plugin.py", "examples/help-button/ui.json"])
    assert example["plugins"] == ["examples/help-button", "examples/ui-api"]
    assert example["lifecycle_reference"] and not example["lifecycle_jellyfin"] and not example["lifecycle_pwa"]
    other = classify(["official/epic-games/epic.py"])
    assert other["lifecycle"] and not (
        other["lifecycle_jellyfin"] or other["lifecycle_pwa"] or other["lifecycle_reference"])


def test_documentation_only_changes_skip_plugin_lifecycle_and_package_work():
    selection = classify(["wiki/docs/index.md", "README.md", "docs/official-signing.md"])
    assert selection["plugins"] == []
    assert not any(selection[key] for key in selection if key != "plugins")


def test_test_only_changes_run_the_test_job_but_not_lifecycle():
    selection = classify(["tests/test_hltb.py"])
    assert selection["full_tests"] and not selection["lifecycle"]


def test_mixed_diff_combines_areas_and_unknown_paths_are_shared():
    selection = classify(["official/pwa/manifest.json", "wiki/docs/index.md", "Makefile"])
    assert selection["lifecycle_jellyfin"]  # an unrecognised root file is treated as shared
    assert classify(["official/pwa/manifest.json", "wiki/docs/index.md"])["lifecycle_pwa"]
    assert classify(["", "  "])["lifecycle"] is False


def test_main_tags_and_missing_base_run_everything(tmp_path):
    script = Path(__file__).parents[1] / "tools/ci_changes.py"
    def run(*args):
        return subprocess.run([sys.executable, str(script), *args], capture_output=True, text=True, check=True).stdout
    assert "lifecycle_pwa=true" in run("--ref", "main", "--event", "pull_request")
    assert "lifecycle_pwa=true" in run("--ref", "refs/tags/v1", "--event", "push")
    assert "lifecycle_pwa=true" in run("--ref", "feature", "--event", "push", "--base", "0" * 40, "--head", "abc")
    assert "plugins=*" in run("--ref", "feature", "--event", "workflow_dispatch")
