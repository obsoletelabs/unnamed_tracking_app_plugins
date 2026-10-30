"""Decide which CI areas a diff needs; unknown or shared changes select everything."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys

PLUGIN_ROOTS = ("examples", "official", "plugins")
DOC_ROOTS = ("wiki", "docs")
ZERO_SHA = "0" * 40
JELLYFIN = "official/jellyfin-media-sync"
PWA = "official/pwa"


def classify(files: list[str] | None) -> dict[str, object]:
    """Map changed paths to the CI areas that must run.

    ``None`` means the change set is unknown. Paths outside plugin sources, documentation
    and tests (SDK, tools, publishers, workflows, dependency files, ...) are shared and
    select everything; documentation-only diffs skip plugin lifecycle and package work.
    """
    if files is None:
        return everything()
    plugins: set[str] = set()
    shared = tests = False
    for raw in files:
        path = raw.strip().replace("\\", "/")
        if not path:
            continue
        parts = path.split("/")
        if parts[0] in PLUGIN_ROOTS and len(parts) > 2:
            plugins.add("/".join(parts[:2]))
        elif parts[0] in DOC_ROOTS or (len(parts) == 1 and path.endswith(".md")):
            continue
        elif parts[0] == "tests":
            tests = True
        else:
            shared = True
    return {
        "plugins": sorted(plugins),
        "lifecycle": shared or bool(plugins),
        "lifecycle_reference": shared or any(p.startswith("examples/") for p in plugins),
        "lifecycle_jellyfin": shared or JELLYFIN in plugins,
        "lifecycle_pwa": shared or PWA in plugins,
        "full_tests": shared or tests or bool(plugins),
    }


def everything() -> dict[str, object]:
    return {"plugins": ["*"], "lifecycle": True, "lifecycle_reference": True,
            "lifecycle_jellyfin": True, "lifecycle_pwa": True, "full_tests": True}


def changed_files(event: str, base: str, head: str) -> list[str] | None:
    if event not in {"pull_request", "push"} or not base or base == ZERO_SHA or not head:
        return None
    # Two dots on push (before..after); the PR base is merged into a three-dot range.
    spec = f"{base}...{head}" if event == "pull_request" else f"{base}..{head}"
    result = subprocess.run(["git", "diff", "--name-only", spec], capture_output=True, text=True)
    return result.stdout.splitlines() if result.returncode == 0 else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", default=os.environ.get("EVENT", ""))
    parser.add_argument("--base", default=os.environ.get("BASE_SHA", ""))
    parser.add_argument("--head", default=os.environ.get("HEAD_SHA", ""))
    parser.add_argument("--ref", default=os.environ.get("REF", ""), help="main and tags always run everything")
    args = parser.parse_args()
    if args.ref == "main" or args.ref.startswith("refs/tags/"):
        selection = everything()
    else:
        selection = classify(changed_files(args.event, args.base, args.head))
    lines = [f"{key}={str(value).lower() if isinstance(value, bool) else ','.join(value)}"
             for key, value in selection.items()]
    print("\n".join(lines))
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
