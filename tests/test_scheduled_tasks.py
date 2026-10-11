"""Plugin-side schedule declarations and public gateway consumer behavior."""

import json
import shutil
import subprocess
import sys

import pytest

from tools.distribution import ROOT
from tools.validate_packages import validate_scheduled_tasks


@pytest.mark.parametrize(
    "changes",
    [
        {"action_id": "missing"},
        {"default_interval_minutes": 1},
        {"min_interval_minutes": 120},
    ],
)
def test_invalid_target_or_interval_is_rejected(changes):
    declaration = {"id": "summary", "action_id": "summary", **changes}
    with pytest.raises(ValueError):
        validate_scheduled_tasks(
            {"scheduled_tasks": [declaration]},
            {"actions": [{"id": "summary", "handler": "plugin:summary"}]},
            (1, 1, 0),
            {"tasks.background"},
        )


def test_schedules_require_explicit_permission_unique_ids_and_no_confirmation():
    manifest = {"scheduled_tasks": [{"id": "summary", "action_id": "summary"}]}
    document = {"actions": [{"id": "summary", "handler": "plugin:summary"}]}
    for version, permissions in (((1, 0, 0), {"tasks.background"}), ((1, 1, 0), set())):
        with pytest.raises(ValueError):
            validate_scheduled_tasks(manifest, document, version, permissions)
    validate_scheduled_tasks(manifest, document, (1, 1, 0), {"tasks.background"})
    manifest["scheduled_tasks"].append(manifest["scheduled_tasks"][0])
    with pytest.raises(ValueError, match="duplicate"):
        validate_scheduled_tasks(manifest, document, (1, 1, 0), {"tasks.background"})
    manifest["scheduled_tasks"].pop()
    document["actions"][0]["confirmation"] = "Approve this"
    with pytest.raises(ValueError, match="no confirmation"):
        validate_scheduled_tasks(manifest, document, (1, 1, 0), {"tasks.background"})


def test_personal_schedules_require_api_1_1_11():
    manifest = {"scheduled_tasks": [{"id": "sync", "action_id": "sync", "scope": "user"}]}
    document = {"actions": [{"id": "sync", "handler": "plugin:sync"}]}
    with pytest.raises(ValueError, match="personal scheduled tasks require"):
        validate_scheduled_tasks(manifest, document, (1, 1, 10), {"tasks.background"})
    validate_scheduled_tasks(manifest, document, (1, 1, 11), {"tasks.background"})


def test_summary_example_uses_only_public_scoped_gateway_and_returns_bounded_feedback(tmp_path):
    shutil.copytree(ROOT / "sdk", tmp_path / "sdk", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copyfile(ROOT / "examples/ui-api/plugin.py", tmp_path / "plugin.py")
    program = "import json,plugin; print(json.dumps({'result':plugin.scheduled_summary({'_scheduled_task':{'id':'library-summary','trigger':'manual'}})}))"
    reply = {"payload": {"games": [{"id": "a"}, {"id": "b"}, {"id": "c"}]}}
    result = subprocess.run(
        [sys.executable, "-c", program],
        cwd=tmp_path,
        input=json.dumps(reply) + "\n",
        text=True,
        capture_output=True,
        check=True,
    )
    requests = [json.loads(line) for line in result.stdout.splitlines()]
    assert requests[0]["method"] == "games.list" and requests[0]["capability"] == "games.read"
    assert requests[-1]["result"] == {
        "completed": True,
        "summary": "Read 3 games from the background administrator's library.",
    }
