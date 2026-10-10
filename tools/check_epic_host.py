#!/usr/bin/env python3
"""Exercise a packaged Epic plugin through a disposable host's public HTTP API.

Use a migrated test database and an Epic-shaped provider HTTP fixture. Host/runtime
startup and provider acquisition substitution belong to the validation environment;
this script imports no application models or plugin implementation.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
import time
from pathlib import Path
from uuid import uuid4

import httpx

PLUGIN = "official.epic-games"
CODE = "b" * 32


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--package", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--fixture-state", required=True, type=Path)
    parser.add_argument("--browser", action="store_true")
    parser.add_argument(
        "--browser-only",
        action="store_true",
        help="Capture an already connected disposable installation",
    )
    parser.add_argument(
        "--reuse",
        action="store_true",
        help="Resume validation of this same disposable installation",
    )
    args = parser.parse_args()
    username, password = (
        os.environ["UI_REVIEW_USERNAME"],
        os.environ["UI_REVIEW_PASSWORD"],
    )
    args.evidence.mkdir(parents=True, exist_ok=True)
    report = {
        "plugin_id": PLUGIN,
        "provider_http_fixture": True,
        "real_host_runtime_database": True,
        "reduced_isolation_validation": True,
        "checks": [],
    }

    def checkpoint(message):
        report["checks"].append(message)
        (args.evidence / "conformance.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )
        print(message, flush=True)

    def fixture(**state):
        args.fixture_state.write_text(json.dumps(state))

    with httpx.Client(base_url=args.host, timeout=45) as client:

        def api(method, path, *, body=None, expected=200, session=client, **kwargs):
            response = session.request(method, path, json=body, **kwargs)
            assert response.status_code == expected, (
                path,
                response.status_code,
                response.text[:1000],
            )
            return response.json() if response.content else None

        api(
            "POST",
            "/api/auth/login",
            body={"username_or_email": username, "password": password},
        )
        candidate = args.package.read_bytes()
        preview = api(
            "POST",
            "/api/plugins/install/preview",
            files={"file": (args.package.name, candidate)},
        )
        assert preview["trust_status"] == "unsigned" and preview["installable"]
        keys = [permission["key"] for permission in preview["permissions"]]
        if args.reuse:
            replacement = api(
                "PUT",
                f"/api/plugins/{PLUGIN}/update/preview",
                files={"file": (args.package.name, candidate)},
                params={"operation": "replace"},
            )
            api(
                "PUT",
                f"/api/plugins/{PLUGIN}/update",
                files={"file": (args.package.name, candidate)},
                data={
                    "admin_password": password,
                    "expected_installed_version": replacement["installed_version"],
                    "expected_digest": replacement["digest"],
                },
                params={
                    "operation": "replace",
                    "allow_untrusted": True,
                    "confirm_dangerous": True,
                    "approved_permissions": replacement["new_permission_keys"],
                    "permissions_reviewed": True,
                    "version_change_confirmed": True,
                },
            )
        else:
            api(
                "POST",
                "/api/plugins/install",
                expected=409,
                files={"file": (args.package.name, candidate)},
            )
            api(
                "POST",
                "/api/plugins/install",
                expected=201,
                files={"file": (args.package.name, candidate)},
                data={"admin_password": password},
                params={
                    "allow_untrusted": True,
                    "confirm_dangerous": True,
                    "approved_permissions": keys,
                },
            )
        if not args.browser_only:
            checkpoint(
                "Actual unsigned .utp preview and reviewed replacement passed."
                if args.reuse
                else "Actual unsigned .utp preview, default denial, explicit consent and installation passed."
            )
        for _ in range(100):
            installed = next(
                item
                for item in api("GET", "/api/plugins")
                if item["plugin_id"] == PLUGIN
            )
            if installed["status"] == "running" and installed["health"] == "healthy":
                break
            time.sleep(0.1)
        assert (
            installed["api_contract_version"] == "1.1.3"
            and installed["status"] == "running"
        )
        assert installed["digest"] == preview["digest"], (
            "The worker must execute the reviewed package"
        )
        report["package_digest"] = preview["digest"]
        report["api_contract_version"] = installed["api_contract_version"]
        assert (
            api("GET", "/api/plugins/" + PLUGIN + "/ui")["frontend"]["entry"]
            == "frontend/index.html"
        )
        if args.browser_only:
            capture_browser(client, args)
            return

        def action(name, values=None, *, session=client, expected=200):
            return api(
                "POST",
                f"/api/plugins/{PLUGIN}/actions/{name}",
                expected=expected,
                session=session,
                body={"values": values or {}, "confirmed": True},
            )

        def complete():
            for _ in range(100):
                state = action("step")
                if state["phase"] == "complete":
                    return state
            raise AssertionError("Import failed to complete")

        connected = action("connect", {"authorization_code": CODE})
        assert connected["connected"] and "token" not in json.dumps(connected)
        fixture()
        action("start")
        result = complete()
        assert (
            result["imported"] == 27
            and result["skipped"] == 1
            and result["inventory_count"] == 28
        )
        games = [
            game
            for game in api("GET", "/api/game/list", params={"limit": 200})
            if game["source"] == "Epic Games"
        ]
        assert len(games) == 27 and len({game["id"] for game in games}) == 27
        first = next(
            game
            for game in games
            if game["title"] in {"Epic review one 0", "Personal Epic title"}
        )
        assert first["playtime_seconds"] == 600
        checkpoint(
            "Real worker imported 27 PostgreSQL games from two pages/namespaces; DLC skipped, playtime persisted."
        )
        api(
            "PATCH",
            "/api/game/update/" + first["id"],
            body={
                "status": "MASTERED",
                "title": "Personal Epic title",
                "notes": "Personal notes",
                "rating_overall": 9,
                "locked_fields": ["title"],
            },
        )
        fixture(playtime_failure=True)
        action("start")
        assert complete()["warning"]
        saved = api("GET", "/api/game/get/" + first["id"])
        assert saved["status"] == "MASTERED" and saved["title"] == "Personal Epic title"
        assert (
            saved["notes"] == "Personal notes"
            and float(saved["rating_overall"]) == 9
            and saved["playtime_seconds"] == 600
        ), {key: saved[key] for key in ("notes", "rating_overall", "playtime_seconds")}
        assert (
            len(
                [
                    game
                    for game in api("GET", "/api/game/list", params={"limit": 200})
                    if game["source"] == "Epic Games"
                ]
            )
            == 27
        )
        checkpoint(
            "Repeated imports preserved exact IDs, manual status/title locks, notes/rating and unavailable playtime."
        )
        fixture(inventory_failure=True)
        action("start")
        failed = action("step")
        assert failed.get("ok") is False and "secret" not in json.dumps(failed).lower()
        assert api("GET", "/api/game/get/" + first["id"])["stale_since"] is None
        fixture()
        assert complete()["phase"] == "complete"
        checkpoint(
            "A real provider HTTP failure retained the checkpoint and availability; resume recovered."
        )

        other = "epic-review-" + uuid4().hex
        other_password = "Disposable-Epic-Review1!"
        api(
            "POST",
            "/api/auth/users",
            expected=201,
            body={
                "username": other,
                "email": other + "@example.invalid",
                "password": other_password,
            },
        )
        with httpx.Client(base_url=args.host, timeout=45) as second:
            api(
                "POST",
                "/api/auth/login",
                session=second,
                body={"username_or_email": other, "password": other_password},
            )
            state = action("status", session=second)
            assert not state["connected"]
            assert api(
                "GET", "/api/game/get/" + first["id"], session=second, expected=404
            )["detail"]
        checkpoint(
            "Another authenticated user cannot see this connection or imported game."
        )

        fixture(empty=True)
        action("start")
        complete()
        assert api("GET", "/api/game/get/" + first["id"])["stale_since"] is not None
        fixture()
        action("start")
        complete()
        assert api("GET", "/api/game/get/" + first["id"])["stale_since"] is None
        checkpoint(
            "Complete empty inventory marked existing games unavailable without deletion; a later inventory restored availability."
        )

        api("POST", f"/api/plugins/{PLUGIN}/stop")
        api("POST", f"/api/plugins/{PLUGIN}/start")
        assert action("status")["connected"]
        checkpoint(
            "Worker stop/start retained the private connection and saved import."
        )

        if args.browser:
            capture_browser(client, args)
            checkpoint(
                "Actual installed sandbox UI verified on phone and desktop, with navigation and pause/reload/resume evidence."
            )

        action("disconnect")
        assert not action("status")["connected"]
        assert api("GET", "/api/game/get/" + first["id"])["status"] == "MASTERED"
        logs = api("GET", f"/api/plugins/{PLUGIN}/logs")
        assert "disposable-access" not in json.dumps(
            logs
        ) and "disposable-refresh" not in json.dumps(logs)
        checkpoint(
            "Disconnect retained imported games and personal state; runtime logs contain no fixture credentials."
        )
        report["status"] = "passed"
        (args.evidence / "conformance.json").write_text(
            json.dumps(report, indent=2) + "\n"
        )


def capture_browser(client, args):
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as stream:
        json.dump(
            [
                {"name": cookie.name, "value": cookie.value}
                for cookie in client.cookies.jar
            ],
            stream,
        )
        cookie_file = Path(stream.name)
    try:
        subprocess.run(
            [
                "node",
                str(Path(__file__).with_name("capture_epic_host.mjs")),
                str(Path(__file__).parents[1]),
                str(args.evidence),
                args.host,
                str(cookie_file),
            ],
            check=True,
        )
    finally:
        cookie_file.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
