"""Execute the Linux workflow selector with offline GitHub API and Git transports."""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
VERIFIED_RUNTIME_REF = "main"


@pytest.mark.parametrize(
    "scenario",
    [
        ("", "main", "main", False, "main"),
        ("", "feature/example", "feature/example", True, "feature/example"),
        ("", "feature/example", "main", False, "main"),
        # A stale branch without an open host PR must not shadow the merged main.
        ("", "feature/example", "feature/example", False, "main"),
        ("pinned-host-sha", "main", "main", False, "pinned-host-sha"),
        ("main", "main", "main", False, "main"),
    ],
)
@pytest.mark.parametrize(
    "workflow_name,job",
    [("host-integration.yml", "lifecycle"), ("ci.yml", "test-and-build")],
)
def test_workflow_selects_owned_host_target(tmp_path, scenario, workflow_name, job):
    """Explicit refs and open paired branches precede each workflow's verified fallback."""
    requested, branch, remote_branch, open_pr, expected = scenario
    workflow = yaml.safe_load((ROOT / ".github/workflows" / workflow_name).read_text())
    checkout = next(step for step in workflow["jobs"][job]["steps"]
                    if step.get("with", {}).get("path") == ".validation/host")
    assert checkout["with"]["repository"] == "obsoletelabs/unnamed_tracking_app_2"
    step = next(
        step for step in workflow["jobs"][job]["steps"] if step.get("id") == "companion"
    )
    assert "https://github.com/obsoletelabs/unnamed_tracking_app_2.git" in step["run"]
    if job == "lifecycle":
        assert step["env"]["DEFAULT_HOST_REF"] == VERIFIED_RUNTIME_REF
        if not requested and expected == "main":
            expected = VERIFIED_RUNTIME_REF
    git = tmp_path / "git"
    git.write_text(
        "#!/bin/sh\n"
        'for arg do last="$arg"; done\n'
        '[ "$last" = "refs/heads/$AVAILABLE_HOST_BRANCH" ]\n'
    )
    git.chmod(0o755)
    curl = tmp_path / "curl"
    curl.write_text("#!/bin/sh\nprintf '%s' \"$OPEN_PR_RESPONSE\"\n")
    curl.chmod(0o755)
    output = tmp_path / "output"
    result = subprocess.run(
        ["bash", "-e", "-c", step["run"]],
        env={
            **os.environ,
            "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
            "OPEN_PR_RESPONSE": '[{}]' if open_pr else '[]',
            "GITHUB_TOKEN": "test-token",
            "REQUESTED_REF": requested,
            "DEFAULT_HOST_REF": step["env"].get("DEFAULT_HOST_REF", "main"),
            "COMPANION_BRANCH": branch,
            "AVAILABLE_HOST_BRANCH": remote_branch,
            "GITHUB_OUTPUT": str(output),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert output.read_text().strip() == "ref=" + expected, result.stdout
