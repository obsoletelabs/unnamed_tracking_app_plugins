"""Official preview acceptance through real host, runtime, database and HTTP.

Use a disposable migrated database. Remote fixtures implement Jellyfin 12's
actual authentication, discovery, pagination and Playback Reporting contracts.
Nothing bypasses installation review, gateway grants or plugin actions.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import httpx

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = "official.jellyfin-media-sync"
PASSWORD = "Disposable-test-password1!"
TOKEN = "DisposableJellyfinFixtureToken"
LIBRARIES = [str(i) * 32 for i in (1, 2, 3)]


class Jellyfin(BaseHTTPRequestHandler):
    """HTTP fixture, including authentication POST and mutable watched state."""

    quick_approved = False
    items_error = 0
    played = False
    calls = []

    def log_message(self, *_args):
        pass

    def reply(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        path = urlsplit(self.path).path.removeprefix("/second")
        size = int(self.headers.get("Content-Length", "0"))
        data = json.loads(self.rfile.read(size)) if size else {}
        if path == "/QuickConnect/Initiate":
            return self.reply(
                {"Secret": "DisposableQuickConnectSecret", "Code": "123456"}, 201
            )
        if path == "/Users/AuthenticateByName":
            if data != {"Username": "fixture-user", "Pw": "fixture-password"}:
                return self.reply({"Error": "Authentication failed"}, 401)
        elif path == "/Users/AuthenticateWithQuickConnect":
            if (
                not self.quick_approved
                or data.get("Secret") != "DisposableQuickConnectSecret"
            ):
                return self.reply({}, 401)
        else:
            return self.reply({}, 404)
        return self.reply(
            {"AccessToken": TOKEN, "User": {"Id": "a" * 32, "Name": "fixture-user"}}
        )

    def do_GET(self):
        url = urlsplit(self.path)
        path = url.path.removeprefix("/second")
        query = parse_qs(url.query)
        self.calls.append((path, query))
        if path == "/System/Info/Public":
            return self.reply(
                {
                    "Version": "12.1.0",
                    "Id": "fixture-second"
                    if url.path.startswith("/second")
                    else "fixture-first",
                }
            )
        if path == "/QuickConnect/Enabled":
            return self.reply(True)
        if path == "/QuickConnect/Connect":
            return self.reply({"Authenticated": self.quick_approved})
        if TOKEN not in self.headers.get("Authorization", ""):
            return self.reply({"Error": "Credential rejected"}, 401)
        if path == "/System/Info":
            return self.reply({"Version": "12.1.0"})
        if path == "/Users":
            return self.reply([{"Id": "a" * 32, "Name": "fixture-user"}])
        if path == "/Users/" + "a" * 32:
            return self.reply({"Id": "a" * 32, "Name": "fixture-user"})
        if path == "/Library/VirtualFolders":
            return self.reply(
                [
                    {
                        "ItemId": LIBRARIES[0],
                        "Name": "Films",
                        "CollectionType": "movies",
                    },
                    {"ItemId": LIBRARIES[1], "Name": "TV", "CollectionType": "tvshows"},
                    {
                        "ItemId": LIBRARIES[2],
                        "Name": "Anime",
                        "CollectionType": "tvshows",
                    },
                    {"ItemId": "9" * 32, "Name": "Music", "CollectionType": "music"},
                ]
            )
        if path == "/Items":
            if self.items_error:
                return self.reply(
                    {"Error": "Remote diagnostics must not be exposed"},
                    self.items_error,
                )
            assert query["CollapseBoxSetItems"] == ["false"]
            library = query["ParentId"][0]
            userdata = {
                "Played": self.played,
                "PlaybackPositionTicks": 0 if self.played else 3000000000,
                "PlayCount": 2,
                "LastPlayedDate": "2026-10-01T12:00:00Z",
            }
            rows = []
            if query["IncludeItemTypes"] == ["Movie,Series"]:
                rows = (
                    [
                        {
                            "Id": "4" * 32,
                            "Name": "Fixture film",
                            "Type": "Movie",
                            "ProviderIds": {"Tmdb": "42"},
                            "ProductionYear": 2025,
                            "RunTimeTicks": 6000000000,
                            "UserData": userdata,
                            "Overview": "Imported synopsis",
                            "ImageTags": {"Primary": "tag"},
                            "BackdropImageTags": ["tag"],
                        }
                    ]
                    if library == LIBRARIES[0]
                    else [
                        {
                            "Id": "5" * 32,
                            "Name": "Fixture show",
                            "Type": "Series",
                            "ProviderIds": {"Tvdb": "52"},
                            "ProductionYear": 2025,
                            "UserData": {"Played": False},
                        }
                    ]
                    if library == LIBRARIES[1]
                    else [
                        {
                            "Id": "6" * 32,
                            "Name": "Fixture anime film",
                            "Type": "Movie",
                            "Genres": ["Anime"],
                            "ProductionYear": 2025,
                            "UserData": {"Played": True},
                        }
                    ]
                    if library == LIBRARIES[2]
                    else []
                )
            elif library == LIBRARIES[1]:
                rows = [
                    {
                        "Id": "7" * 32,
                        "SeriesId": "5" * 32,
                        "Name": "Special",
                        "Type": "Episode",
                        "ParentIndexNumber": 0,
                        "IndexNumber": 1,
                        "UserData": {"Played": True},
                    }
                ]
            start = int(query["StartIndex"][0])
            limit = int(query["Limit"][0])
            return self.reply(
                {"Items": rows[start : start + limit], "TotalRecordCount": len(rows)}
            )
        if path.startswith("/user_usage_stats/"):
            day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
            return self.reply(
                [
                    {
                        "RowId": "1",
                        "Id": "4" * 32,
                        "Type": "Movie",
                        "Time": "12:00:00",
                        "Duration": "120",
                    }
                ]
                if "/" + day + "/" in path
                else []
            )
        return self.reply({}, 404)


def build_preview(work: Path, version: str) -> Path:
    source = work / "source"
    if not source.exists():
        source.mkdir()
        (source / "examples").mkdir()
        for name in ("tools", "sdk", "publishers"):
            shutil.copytree(
                ROOT / name, source / name, ignore=shutil.ignore_patterns("__pycache__")
            )
        shutil.copytree(
            ROOT / "official/jellyfin-media-sync",
            source / "official/jellyfin-media-sync",
        )
    manifest_path = source / "official/jellyfin-media-sync/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["version"] = version
    manifest_path.write_text(json.dumps(manifest))
    subprocess.run(
        [sys.executable, str(source / "tools/build_packages.py")],
        check=True,
        capture_output=True,
    )
    return source / ".validation/dist" / f"{PLUGIN}-{version}.utp"


def acceptance(args):
    sys.path.insert(0, str(args.host_root / "tools"))
    from check_plugin_repository_lifecycle import available_port, wait_until
    from plugin_conformance import InstalledPluginConformance

    work = args.work_root
    work.mkdir(parents=True, exist_ok=False)
    report = {
        "plugin_id": PLUGIN,
        "status": "running",
        "isolation": args.isolation,
        "passed": [],
    }

    def checkpoint(name):
        report["passed"].append(name)
        (work / "conformance.json").write_text(json.dumps(report, indent=2))
        print(name, flush=True)

    package = build_preview(work, "0.0.1")
    port, runtime_port = available_port(), available_port()
    env = {
        **os.environ,
        "PRIMARY_USER_USERNAME": "jellyfin-test-" + uuid4().hex,
        "PRIMARY_USER_EMAIL": uuid4().hex + "@example.invalid",
        "PRIMARY_USER_PASSWORD": PASSWORD,
        "PLUGIN_RUNTIME_URL": f"http://127.0.0.1:{runtime_port}",
        "PLUGIN_RUNTIME_TOKEN": uuid4().hex + uuid4().hex,
        "PLUGIN_GATEWAY_URL": f"http://127.0.0.1:{port}",
        "STARTUP_MODE": "testing",
        "DEBUG": "false",
        "PLUGIN_MANAGER_STATE_PATH": str(work / "manager.json"),
        "PLUGIN_CATALOGUE_REGISTRY": str(work / "catalogues.json"),
        "NONBUBBLE_ENV": "true" if args.isolation == "reduced" else "false",
    }
    processes, logs = [], []

    def launch(mode, selected_port):
        log = (work / f"{mode}-{len(logs)}.log").open("w")
        logs.append(log)
        process = subprocess.Popen(
            [
                sys.executable,
                str(args.host_root / "tools/check_plugin_repository_lifecycle.py"),
                "--mode",
                mode,
                "--port",
                str(selected_port),
                "--work-root",
                str(work),
            ],
            env=env,
            cwd=args.host_root / "src/backend",
            stdout=log,
            stderr=log,
        )
        processes.append(process)
        return process

    runtime, host = launch("runtime", runtime_port), launch("host", port)
    jellyfin = ThreadingHTTPServer(("127.0.0.1", 0), Jellyfin)
    threading.Thread(target=jellyfin.serve_forever, daemon=True).start()
    try:
        with httpx.Client(base_url=env["PLUGIN_GATEWAY_URL"], timeout=45) as client:
            wait_until(
                lambda: (
                    client.post(
                        "/api/auth/login",
                        json={
                            "username_or_email": env["PRIMARY_USER_USERNAME"],
                            "password": PASSWORD,
                        },
                    ).status_code
                    == 200
                )
            )
            conformance = InstalledPluginConformance(client, PLUGIN)
            action, request = conformance.action, conformance.request
            candidate = package.read_bytes()
            preview = request(
                "POST", "/install/preview", files={"file": (package.name, candidate)}
            )
            assert (
                preview["version"] == "0.0.1" and preview["trust_status"] == "unsigned"
            )
            assert "official" in preview["tags"] and "preview" in preview["tags"]
            keys = [p["key"] for p in preview["permissions"]]
            request("POST", "/install", 409, files={"file": (package.name, candidate)})
            request(
                "POST",
                "/install",
                201,
                files={"file": (package.name, candidate)},
                data={"admin_password": PASSWORD},
                params={
                    "allow_untrusted": True,
                    "confirm_dangerous": True,
                    "approved_permissions": keys,
                },
            )
            conformance.assert_ready()
            checkpoint(
                "real .utp preview, untrusted consent, privileged reauthentication and startup"
            )
            seed = client.post(
                "/api/movie/create",
                json={
                    "title": "Fixture film",
                    "release_date": "2025-01-01",
                    "provider_ids": {"tmdb": "42"},
                    "rating_overall": 9,
                    "note": "Keep local note",
                },
            )
            assert seed.status_code == 201, seed.text
            movie_id = seed.json()["id"]
            server = action(
                "save-server",
                {
                    "name": "Fixture server",
                    "url": f"http://127.0.0.1:{jellyfin.server_port}",
                    "api_key": TOKEN,
                    "history_days": 2,
                    "max_retries": 0,
                },
            )["server_id"]
            assert action("test-connection", {"server_id": server})["warnings"]
            action(
                "save-mappings",
                {
                    "server_id": server,
                    "mappings": {
                        LIBRARIES[0]: "movie",
                        LIBRARIES[1]: "tv_show",
                        LIBRARIES[2]: "anime",
                    },
                },
            )
            account = action(
                "login",
                {
                    "server_id": server,
                    "username": "fixture-user",
                    "password": "fixture-password",
                },
            )["account_id"]
            action(
                "save-account",
                {
                    "account_id": account,
                    "history_enabled": True,
                    "libraries": LIBRARIES,
                },
            )

            def synchronize(selected=account):
                before = (
                    action("status")["accounts"].get(selected, {}).get("finished_at", 0)
                )
                action("sync-now", {"account_id": selected})
                wait_until(
                    lambda: (
                        action("status")["accounts"].get(selected, {}).get("phase")
                        == "syncing"
                    ),
                    timeout=30,
                )
                wait_until(
                    lambda: (
                        (s := action("status")["accounts"].get(selected, {})).get(
                            "phase"
                        )
                        == "idle"
                        and s.get("finished_at", 0) >= before
                    ),
                    timeout=90,
                )

            synchronize()
            movies = client.get("/api/movie/list").json()["items"]
            assert len(movies) == 1 and movies[0]["id"] == movie_id
            native = client.get("/api/movie/get/" + movie_id).json()
            assert (
                float(native["rating_overall"]) == 9
                and native["note"] == "Keep local note"
            )
            state = client.get(
                "/api/media/provider-state",
                params={"media_type": "movie", "media_id": movie_id},
            ).json()
            assert (
                state["sources"][0]["playback"]["percentage"] == 50
                and len(state["history"]) == 1
            )
            assert client.get("/api/tv/list").json()["items"]
            assert client.get("/api/anime/list").json()["items"]
            assert TOKEN not in json.dumps(action("get-config"))
            checkpoint(
                "configuration, password login, films/TV/anime/specials, progress, history and local merge"
            )
            second = action(
                "save-server",
                {
                    "name": "Second",
                    "url": f"http://127.0.0.1:{jellyfin.server_port}/second",
                    "api_key": TOKEN,
                },
            )["server_id"]
            action("test-connection", {"server_id": second})
            quick = action("quick-connect-start", {"server_id": second})
            assert "Secret" not in json.dumps(quick)
            Jellyfin.quick_approved = True
            second_account = action(
                "quick-connect-finish", {"pending_id": quick["pending_id"]}
            )["account_id"]
            action(
                "save-account",
                {"account_id": second_account, "libraries": [LIBRARIES[0]]},
            )
            action("order-accounts", {"account_ids": [second_account, account]})
            synchronize(second_account)
            assert len(client.get("/api/movie/list").json()["items"]) == 1
            sources = client.get(
                "/api/media/provider-state",
                params={"media_type": "movie", "media_id": movie_id},
            ).json()["sources"]
            links = [item for item in sources if item.get("watch_url")]
            assert any("/second/web/" in item["watch_url"] for item in links)
            assert all(TOKEN not in item["watch_url"] for item in links)
            assert all(str(item["watch_label"]).startswith("Jellyfin") for item in links)
            checkpoint(
                "multiple servers/accounts, Quick Connect, cross-account merging and host-rendered Watch links"
            )

            def persisted():
                data = action("get-config")
                return {"servers": data["servers"], "accounts": data["accounts"]}

            baseline = persisted()
            review = {
                "allow_untrusted": True,
                "confirm_dangerous": True,
                "approved_permissions": [],
                "admin_password": PASSWORD,
            }
            conformance.preserving_lifecycle(persisted, reinstall_review=review)
            runtime.terminate()
            runtime.wait(timeout=10)
            runtime = launch("runtime", runtime_port)
            wait_until(lambda: conformance.current()["status"] == "running", timeout=30)
            assert persisted() == baseline
            host.terminate()
            host.wait(timeout=10)
            host = launch("host", port)
            wait_until(
                lambda: client.get("/api/plugins/runtime/health").status_code == 200,
                timeout=30,
            )
            assert persisted() == baseline
            checkpoint(
                "stop/start, disable/enable, reinstall, runtime restart and host reload preserve credentials/config"
            )
            Jellyfin.items_error = 503
            action("sync-now", {"account_id": account})
            wait_until(
                lambda: action("status")["accounts"][account]["phase"] == "error",
                timeout=30,
            )
            Jellyfin.items_error = 0
            synchronize()
            checkpoint("remote failure preserves checkpoints and manual retry resumes")
            action("clear-account-credential", {"account_id": account})
            cleared = next(
                a for a in action("get-config")["accounts"] if a["id"] == account
            )
            assert (
                not cleared["credential_configured"]
                and cleared["libraries"] == LIBRARIES
            )
            action(
                "login",
                {
                    "server_id": server,
                    "account_id": account,
                    "username": "fixture-user",
                    "password": "fixture-password",
                },
            )
            assert next(
                a for a in action("get-config")["accounts"] if a["id"] == account
            )["credential_configured"]
            checkpoint(
                "credential removal and replacement retain preferences and mappings"
            )
            updated = build_preview(work, "0.0.2")
            request(
                "PUT",
                f"/{PLUGIN}/update",
                files={"file": (updated.name, updated.read_bytes())},
                data={"admin_password": PASSWORD},
                params={
                    "allow_untrusted": True,
                    "confirm_dangerous": True,
                    "approved_permissions": keys,
                },
            )
            conformance.assert_ready()
            assert conformance.current()["version"] == "0.0.2"
            assert (
                next(a for a in action("get-config")["accounts"] if a["id"] == account)[
                    "libraries"
                ]
                == LIBRARIES
            )
            checkpoint(
                "real package update preserves independent official identity, grants, storage and sync mappings"
            )
            if args.browser:
                browser_env = {
                    **env,
                    "JELLYFIN_HOST_ROOT": str(args.host_root),
                    "INTEGRATION_WORK_ROOT": str(work),
                    "JELLYFIN_FRONTEND_PORT": str(available_port()),
                    "JELLYFIN_SCREENSHOT_DIR": str(work / "screenshots"),
                }
                subprocess.run(
                    ["node", str(ROOT / "tools/capture_jellyfin_official.mjs")],
                    env=browser_env,
                    check=True,
                )
                checkpoint(
                    "actual installed official admin/user pages, progress/history, Watch Now and mobile layout"
                )
            if args.live_url:
                live_token = args.live_token
                live = action(
                    "save-server",
                    {
                        "name": "Read-only live acceptance",
                        "url": args.live_url,
                        "api_key": live_token,
                    },
                )["server_id"]
                try:
                    assert action("test-connection", {"server_id": live})["ok"]
                    config = action("get-config")
                    live_server = next(s for s in config["servers"] if s["id"] == live)
                    remote = next(
                        u
                        for u in live_server["users"]
                        if u["name"] == args.live_username
                    )
                    action(
                        "authorize-identity",
                        {
                            "server_id": live,
                            "host_user_id": config["host_user_id"],
                            "remote_user_id": remote["id"],
                            "approved": True,
                        },
                    )
                    live_account = action(
                        "link-approved",
                        {"server_id": live, "remote_user_id": remote["id"]},
                    )["account_id"]
                    action("sync-now", {"account_id": live_account})
                    wait_until(
                        lambda: (
                            action("status")["accounts"]
                            .get(live_account, {})
                            .get("phase")
                            in {"idle", "error"}
                        ),
                        timeout=1200,
                    )
                    live_status = action("status")["accounts"][live_account]
                    assert live_status["phase"] == "idle", live_status.get("error")
                    assert live_token not in json.dumps(action("get-config"))
                    report["live"] = {
                        k: live_status.get(k)
                        for k in ("phase", "processed", "reviews", "library_total")
                    }
                    checkpoint(
                        "read-only real Jellyfin discovery, approved identity, full paginated sync and private credential handling"
                    )
                finally:
                    action("clear-server-credential", {"server_id": live})
            report.update(
                status="passed", runtime_isolation=request("GET", "/runtime/health")
            )
            (work / "conformance.json").write_text(json.dumps(report, indent=2))
    finally:
        jellyfin.shutdown()
        jellyfin.server_close()
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        for log in logs:
            log.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host-root", required=True, type=Path)
    parser.add_argument("--work-root", required=True, type=Path)
    parser.add_argument("--isolation", choices=("strict", "reduced"), default="strict")
    parser.add_argument("--browser", action="store_true")
    parser.add_argument("--live-url")
    parser.add_argument("--live-username")
    args = parser.parse_args()
    args.host_root = args.host_root.resolve()
    args.work_root = args.work_root.resolve()
    if args.live_url:
        if not args.live_username:
            parser.error(
                "live testing requires --live-username; supply its key on stdin"
            )
        args.live_token = sys.stdin.readline().strip()
        if not args.live_token:
            parser.error("supply the live test key on stdin")
    acceptance(args)


if __name__ == "__main__":
    main()
