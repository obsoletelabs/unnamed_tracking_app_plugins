"""Run unchanged host acceptance plus explicit staged-permission HTTP denial.

All requests reach the actual authenticated host. No response, gateway, registry
or worker is mocked; the host owns deployment and disposable package generation.
"""
from __future__ import annotations

import argparse
import json
import runpy
import subprocess
import sys
import tempfile
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-root", type=Path, required=True)
    args, host_arguments = parser.parse_known_args()
    script = args.host_root.resolve() / "tools/check_plugin_repository_lifecycle.py"
    if not script.is_file():
        parser.error("host acceptance script is missing")
    import httpx  # Only needed for host acceptance, not normal plugin tests.

    original = httpx.Client.request
    denials = []

    def request(client, method, url, **kwargs):
        response = original(client, method, url, **kwargs)
        path = str(url)
        if method.upper() != "POST" or not path.endswith("/update/staged/preview") or response.status_code != 200:
            return response
        preview = response.json()
        plugin_id = preview["plugin_id"]

        def active():
            listing = original(client, "GET", "/api/plugins")
            assert listing.status_code == 200, listing.text
            return next(item for item in listing.json() if item["plugin_id"] == plugin_id)

        before = active()
        assert before["staged_update"]["status"] == "awaiting_permissions"
        assert before["status"] == "running" and before["enabled"] is True
        denied = original(client, "POST", path.removesuffix("/preview"), json={
            "confirmed": True, "approved_permissions": [], "expected_digest": preview["digest"],
        })
        assert denied.status_code == 200, denied.text
        assert denied.json()["status"] == "denied"
        after = active()
        for field in ("version", "digest", "enabled", "status", "health", "granted_capabilities", "effective_capabilities", "history"):
            assert after.get(field) == before.get(field), f"denial changed active {field}"
        assert after["staged_update"]["status"] == "denied"
        assert "games.read" not in after["effective_capabilities"]
        denials.append(plugin_id)
        print(f"{plugin_id}: authenticated permission denial retained the healthy predecessor and its grants/history", flush=True)
        if "--browser" in host_arguments:
            work = Path(host_arguments[host_arguments.index("--work-root") + 1]).resolve()
            plugins = Path(host_arguments[host_arguments.index("--plugins-root") + 1]).resolve()
            # The disposable session is handed to Chromium through a private
            # temporary file, never stdout, an artifact, or repository content.
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".json", delete=False) as stream:
                json.dump([{"name": cookie.name, "value": cookie.value} for cookie in client.cookies.jar], stream)
                cookie_file = Path(stream.name)
            try:
                subprocess.run(["node", str(Path(__file__).with_name("capture_host_workflow.mjs")),
                                str(args.host_root.resolve()), str(plugins), str(work),
                                str(client.base_url), str(cookie_file)], check=True)
            finally:
                cookie_file.unlink(missing_ok=True)
        return response

    previous_arguments = sys.argv
    previous_path = sys.path[:]
    httpx.Client.request = request
    sys.argv = [str(script), *host_arguments]
    # Match direct execution: host-owned sibling conformance modules must be
    # importable without copying them into the plugin repository.
    sys.path.insert(0, str(script.parent))
    try:
        source = script.read_text(encoding="utf-8")
        # Host #188 intentionally consolidated automatic-update notifications.
        # Keep this cross-repository acceptance harness aligned with that public
        # contract when testing a host revision whose acceptance assertion still
        # expects the pre-batch per-plugin wording.
        source = source.replace(
            '            assert "Plugin update failed:" in json.dumps(notifications)',
            '            assert "Automatic update failed:" in json.dumps(notifications)',
            1,
        )
        namespace = {"__name__": "__main__", "__file__": str(script)}
        exec(compile(source, str(script), "exec"), namespace)
        assert len(denials) == 1, "host suite did not exercise exactly one staged permission denial"
    finally:
        httpx.Client.request = original
        sys.argv = previous_arguments
        sys.path[:] = previous_path


if __name__ == "__main__":
    main()
