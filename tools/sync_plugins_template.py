"""Synchronize public SDK, schemas, and contract versions to the plugins-template repository."""

from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def get_commit_sha(repo_root: Path) -> str:
    """Get the current git commit short SHA."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def sync_template(
    template_root: Path,
    *,
    check: bool = False,
    run_tests: bool = True,
) -> bool:
    """Synchronize SDK and schemas to the template repository.

    Returns True if changes were made (or if differences exist under check).
    """
    template_root = template_root.resolve()
    if not (template_root / "pyproject.toml").is_file():
        raise FileNotFoundError(f"Not a valid plugins-template root: {template_root}")

    has_drift = False

    # 1. Sync sdk/
    source_sdk = ROOT / "sdk"
    target_sdk = template_root / "sdk"
    target_sdk.mkdir(parents=True, exist_ok=True)

    for item in source_sdk.iterdir():
        if item.name.startswith((".", "__pycache__")):
            continue
        dest = target_sdk / item.name
        if item.is_file():
            src_bytes = item.read_bytes().replace(b"\r\n", b"\n")
            dst_bytes = dest.read_bytes().replace(b"\r\n", b"\n") if dest.is_file() else None
            if src_bytes != dst_bytes:
                has_drift = True
                if not check:
                    dest.write_bytes(src_bytes)
        elif item.is_dir():
            if not check:
                shutil.copytree(item, dest, dirs_exist_ok=True)

    # 2. Sync tools/schemas/
    source_schemas = ROOT / "tools/schemas"
    target_schemas = template_root / "tools/schemas"
    target_schemas.mkdir(parents=True, exist_ok=True)

    for item in source_schemas.iterdir():
        if item.suffix == ".json" or item.name == "README.md":
            dest = target_schemas / item.name
            src_bytes = item.read_bytes().replace(b"\r\n", b"\n")
            dst_bytes = dest.read_bytes().replace(b"\r\n", b"\n") if dest.is_file() else None
            if src_bytes != dst_bytes:
                has_drift = True
                if not check:
                    dest.write_bytes(src_bytes)

    # 3. Read API_CONTRACT_VERSION
    protocol_path = (target_sdk if not check else source_sdk) / "plugin_protocol.py"
    match = re.search(r'API_CONTRACT_VERSION\s*=\s*["\']([^"\']+)["\']', protocol_path.read_text(encoding="utf-8"))
    if not match:
        raise ValueError("Could not find API_CONTRACT_VERSION in sdk/plugin_protocol.py")
    contract_version = match.group(1)

    # 4. Update hello-world starter manifest.json and ui.json if needed
    starter_manifest = template_root / "plugins/hello-world/manifest.json"
    if starter_manifest.is_file():
        manifest_data = json.loads(starter_manifest.read_text(encoding="utf-8"))
        if manifest_data.get("api_contract_version") != contract_version:
            has_drift = True
            if not check:
                manifest_data["api_contract_version"] = contract_version
                starter_manifest.write_text(
                    json.dumps(manifest_data, indent=2) + "\n",
                    encoding="utf-8",
                )

    starter_ui = template_root / "plugins/hello-world/ui.json"
    if starter_ui.is_file():
        ui_data = json.loads(starter_ui.read_text(encoding="utf-8"))
        if ui_data.get("api_contract_version") != contract_version:
            has_drift = True
            if not check:
                ui_data["api_contract_version"] = contract_version
                starter_ui.write_text(
                    json.dumps(ui_data, indent=2) + "\n",
                    encoding="utf-8",
                )

    # 5. Update tests/test_v1_1_contract.py assertion
    contract_test = template_root / "tests/test_v1_1_contract.py"
    if contract_test.is_file():
        test_content = contract_test.read_text(encoding="utf-8")
        updated_content = re.sub(
            r'assert manifest\["api_contract_version"\] == API_CONTRACT_VERSION == "[^"]+"',
            f'assert manifest["api_contract_version"] == API_CONTRACT_VERSION == "{contract_version}"',
            test_content,
        )
        updated_content = re.sub(
            r'assert json\.loads\(files\["ui\.json"\]\)\["api_contract_version"\] == "[^"]+"',
            f'assert json.loads(files["ui.json"])["api_contract_version"] == "{contract_version}"',
            updated_content,
        )
        if test_content != updated_content:
            has_drift = True
            if not check:
                contract_test.write_text(updated_content, encoding="utf-8")

    # 6. Update docs/UPSTREAM.md
    upstream_doc = template_root / "docs/UPSTREAM.md"
    if upstream_doc.is_file() and not check and has_drift:
        sha = get_commit_sha(ROOT)
        date_str = datetime.datetime.now(datetime.timezone.utc).strftime("%d %B %Y")
        section = f"""## Synchronization: Contract {contract_version} ({date_str})

Public SDK, exported schemas, and starter contracts synchronized with companion
revision `{sha}`.
- Updated `API_CONTRACT_VERSION` to `{contract_version}`.
- Synchronized SDK modules (metadata providers, notification stories, appearance bridge).
- Synchronized capability schemas for manifest and UI validation.

"""
        existing = upstream_doc.read_text(encoding="utf-8")
        title_marker = "# Tooling provenance and deliberate comparison\n\n"
        if title_marker in existing:
            new_text = existing.replace(title_marker, title_marker + section, 1)
        else:
            new_text = section + existing
        upstream_doc.write_text(new_text, encoding="utf-8")

    # 7. Verification tests
    if not check and run_tests:
        print(f"Running pytest in {template_root}...")
        res = subprocess.run(["python3", "-m", "pytest"], cwd=template_root)
        if res.returncode != 0:
            raise RuntimeError("Template tests failed after synchronization!")
        print("Template tests passed successfully.")

    return has_drift


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--template-root",
        type=Path,
        default=ROOT.parent / "plugins-template",
        help="Path to the plugins-template repository clone.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check for drift without writing changes.",
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="Skip running pytest after synchronization.",
    )
    args = parser.parse_args()

    drift = sync_template(
        args.template_root,
        check=args.check,
        run_tests=not args.no_tests,
    )
    if args.check:
        if drift:
            print("Drift detected: plugins-template is out of date with SDK/schemas.")
            sys.exit(1)
        else:
            print("plugins-template is up to date.")
            sys.exit(0)
    else:
        if drift:
            print("Successfully synchronized plugins-template.")
        else:
            print("plugins-template was already up to date.")


if __name__ == "__main__":
    main()
