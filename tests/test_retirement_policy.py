"""Exercise reviewed retirement against real signed packages and retained history."""

import json
import shutil
import subprocess
import sys

import pytest
from test_release_lifecycle import checkout, commit, run_build

from tools.distribution import (
    ROOT,
    discover_plugins,
    load_histories,
    load_retired_plugins,
    validate_immutable_history,
)

__all__ = ["checkout"]


def write_policy(root, plugin_ids):
    """Write a retirement decision in the isolated release-simulation checkout."""
    records = [
        {
            "plugin_id": plugin_id,
            "status": "retired",
            "reason": "Source is no longer maintained.",
        }
        for plugin_id in plugin_ids
    ]
    (root / "retired_plugins.json").write_text(
        json.dumps({"version": 1, "plugins": records})
    )


@pytest.fixture(name="published_release")
def publish_real_release(request):
    """Publish the existing Help Button implementation with its disposable test signer."""
    root, env = request.getfixturevalue("checkout")
    shutil.copytree(ROOT / "examples/ui-api", root / "examples/ui-api")
    commit(root, "feat: retain an active reference beside the retirement")
    run_build(root, env, "--publish")
    commit(root, "chore: publish a retained release")
    return root, env


def test_retirement_policy_keeps_all_maintained_sources():
    """Reviewed absent sources are retired; all maintained providers remain active."""
    retired = load_retired_plugins(ROOT)
    assert retired == {"example.advanced", "example.events", "example.lifecycle",
                       "example.discord-delivery-provider"}
    assert not retired.intersection(
        manifest["plugin_id"] for _, manifest in discover_plugins(ROOT)
    )
    assert retired.issubset(load_histories(ROOT))


def test_absent_retirement_policy_keeps_existing_publishers_compatible(tmp_path):
    """Independent repositories need no policy when they have not retired a package."""
    assert load_retired_plugins(tmp_path) == set()


@pytest.mark.parametrize(
    "data",
    [
        [],
        {"version": 2, "plugins": []},
        {"version": 1, "plugins": {}},
        {
            "version": 1,
            "plugins": [
                {"plugin_id": "../escape", "status": "retired", "reason": "Old"}
            ],
        },
        {
            "version": 1,
            "plugins": [
                {"plugin_id": "example.old", "status": "active", "reason": "Old"}
            ],
        },
        {
            "version": 1,
            "plugins": [
                {"plugin_id": "example.old", "status": "retired", "reason": " "}
            ],
        },
        {
            "version": 1,
            "plugins": [
                {"plugin_id": "example.old", "status": "retired", "reason": "Old"},
                {
                    "plugin_id": "example.old",
                    "status": "retired",
                    "reason": "Duplicate",
                },
            ],
        },
    ],
)
def test_invalid_retirement_decisions_are_rejected(tmp_path, data):
    """Malformed identities, missing reasons and duplicate decisions cannot waive CI."""
    (tmp_path / "retired_plugins.json").write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_retired_plugins(tmp_path)


@pytest.mark.parametrize("record", [None, {"plugin_id": 123}])
def test_retirement_records_require_typed_identities(tmp_path, record):
    """Malformed record types cannot become catalogue-removal exemptions."""
    (tmp_path / "retired_plugins.json").write_text(
        json.dumps({"version": 1, "plugins": [record]})
    )
    with pytest.raises(TypeError, match="string plugin_id"):
        load_retired_plugins(tmp_path)


def retire_published_help(root, env):
    """Retire the owned simulation's source and build a real, complete distribution."""
    write_policy(root, ["example.help-button"])
    shutil.rmtree(root / "examples/help-button")
    run_build(root, env)
    return root / ".validation"


def test_explicit_retirement_preserves_signed_archive_and_release_records(
    published_release,
):
    """The catalogue can drop a reviewed retirement while every historical byte stays."""
    root, env = published_release
    original = {
        path.relative_to(root): path.read_bytes()
        for directory in ("dist", "releases")
        for path in (root / directory).iterdir()
    }
    output = retire_published_help(root, env)
    verified = subprocess.run(
        [
            sys.executable,
            str(root / "tools/distribution.py"),
            "--root",
            str(output),
            "--check-source",
            "--baseline-ref",
            "HEAD",
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert verified.returncode == 0, verified.stderr
    assert {
        entry["plugin_id"]
        for entry in json.loads((output / "list.json").read_text())["plugins"]
    } == {"example.ui-api"}
    assert original == {name: (output / name).read_bytes() for name in original}


@pytest.mark.parametrize("remaining", ["catalogue", "source"])
def test_retirement_cannot_hide_an_active_plugin(published_release, remaining):
    """A retirement must leave neither a current catalogue entry nor maintained source."""
    root, _ = published_release
    write_policy(root, ["example.help-button"])
    if remaining == "source":
        document = json.loads((root / "list.json").read_text())
        document["plugins"] = [
            entry
            for entry in document["plugins"]
            if entry["plugin_id"] != "example.help-button"
        ]
        (root / "list.json").write_text(json.dumps(document))
    with pytest.raises(ValueError, match="current catalogue|maintained sources"):
        validate_immutable_history(root, root, "HEAD")


def test_retirement_requires_a_retained_history(published_release):
    """A policy entry cannot waive history checks for a nonexistent release."""
    root, _ = published_release
    write_policy(root, ["example.never-published"])
    with pytest.raises(ValueError, match="no retained release history"):
        validate_immutable_history(root, root, "HEAD")


@pytest.mark.parametrize(
    "defect", ["missing_archive", "changed_archive", "changed_record"]
)
def test_retirement_never_allows_historical_mutation(published_release, defect):
    """Retirement does not excuse deleting archives or rewriting packages and metadata."""
    root, env = published_release
    output = retire_published_help(root, env)
    archive = (
        output
        / "dist"
        / load_histories(output)["example.help-button"][0]["package"]["filename"]
    )
    if defect == "missing_archive":
        archive.unlink()
    elif defect == "changed_archive":
        archive.write_bytes(archive.read_bytes() + b"changed")
    else:
        path = output / "releases/example.help-button.json"
        record = json.loads(path.read_text())
        record["releases"][0]["release_notes"] = "Rewritten historical notes"
        path.write_text(json.dumps(record))
    with pytest.raises(
        ValueError,
        match="historical distribution|historical artifact|historical release",
    ):
        validate_immutable_history(output, root, "HEAD")
