"""Exercise native core metadata providers against a real development host and provider APIs.

No provider responses are mocked. Credentials come from the environment; output contains
only bounded counts, classifications and elapsed times. Run only against a disposable host.
"""
from __future__ import annotations

import argparse
import http.cookiejar
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


class Host:
    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
        )

    def call(self, method: str, path: str, payload: Any = None) -> Any:
        body = json.dumps(payload).encode() if payload is not None else None
        return self.send(method, path, body, "application/json")

    def send(self, method: str, path: str, body: bytes | None, content_type: str) -> Any:
        request = urllib.request.Request(
            self.url + path, data=body, method=method, headers={"Content-Type": content_type}
        )
        try:
            with self.opener.open(request, timeout=30) as response:
                data = response.read()
                return json.loads(data) if data else None
        except urllib.error.HTTPError as exc:
            # Error bodies and request URLs can contain configuration. Do not print them.
            details = json.loads(exc.read()).get("detail", {})
            code = details.get("code") if isinstance(details, dict) else None
            self.failure_detail = details
            classification = f", {code}" if isinstance(code, str) and code.replace("_", "").isalnum() else ""
            raise RuntimeError(f"Development host request failed (HTTP {exc.code}{classification})") from None

    def upload(self, path: str, package: Path, password: str | None = None,
               *, method: str = "POST", values: dict[str, str] | None = None) -> Any:
        boundary = "metadata-smoke-" + uuid.uuid4().hex
        fields = [(
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
            f'filename="{package.name}"\r\nContent-Type: application/octet-stream\r\n\r\n'
        ).encode() + package.read_bytes() + b"\r\n"]
        if password is not None:
            fields.append((
                f'--{boundary}\r\nContent-Disposition: form-data; name="admin_password"'
                f'\r\n\r\n{password}\r\n'
            ).encode())
        for name, value in (values or {}).items():
            fields.append((f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
                           f'\r\n\r\n{value}\r\n').encode())
        fields.append(f"--{boundary}--\r\n".encode())
        return self.send(method, path, b"".join(fields), "multipart/form-data; boundary=" + boundary)

    def install(self, package: Path, password: str) -> None:
        preview = self.upload("/api/plugins/install/preview", package)
        existing = next((p for p in self.call("GET", "/api/plugins")
                         if p["plugin_id"] == preview["plugin_id"]), None)
        if existing:
            base = "/api/plugins/" + preview["plugin_id"] + "/update"
            preview = self.upload(base + "/preview", package, method="PUT")
            keys = preview["new_permission_keys"]
            parameters = [("allow_untrusted", "true"), ("confirm_dangerous", "true"),
                          ("permissions_reviewed", "true"), ("version_change_confirmed", "true"),
                          *(("approved_permissions", key) for key in keys)]
            self.upload(base + "?" + urllib.parse.urlencode(parameters), package, password,
                        method="PUT", values={"expected_digest": preview["digest"],
                                              "expected_installed_version": existing["version"]})
            print(json.dumps({"updated": preview["plugin_id"], "contract": preview["api_contract_version"]}))
            return
        parameters = [
            ("allow_untrusted", "true"), ("confirm_dangerous", "true"),
            *(("approved_permissions", permission["key"]) for permission in preview["permissions"]),
        ]
        self.upload("/api/plugins/install?" + urllib.parse.urlencode(parameters), package, password)
        print(json.dumps({"installed": preview["plugin_id"], "contract": preview["api_contract_version"]}))

    def providers(self) -> dict[str, Any]:
        return {provider["provider_id"]: provider
                for provider in self.call("GET", "/api/metadata/providers")["providers"]}

    def wait(self, condition, seconds: float = 35) -> Any:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = condition()
            if result:
                return result
            time.sleep(0.1)
        raise RuntimeError("Timed out waiting for the real provider operation")

    def configure(self, provider_id: str, value: str | None, scope: str = "user") -> None:
        self.call("PUT", "/api/metadata/providers/" + provider_id + "/configuration",
                  {"scope": scope, "values": {"api_key": value}})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="http://localhost:18083")
    args = parser.parse_args()
    host = Host(args.host)
    password = os.environ["PRIMARY_USER_PASSWORD"]
    host.call("POST", "/api/auth/login", {
        "username_or_email": os.environ["PRIMARY_USER_USERNAME"], "password": password,
    })
    steam = "core.steam"
    artwork = "core.steamgriddb"
    host.wait(lambda: steam in host.providers() and artwork in host.providers())
    host.configure(artwork, None)
    host.configure(artwork, None, "system")
    assert host.providers()[artwork]["state"] == "not_configured"
    print(json.dumps({"provider": "SteamGridDB", "missing_configuration": "not_configured"}))
    key = os.getenv("STEAMGRIDDB_API_KEY")
    if key:
        host.configure(artwork, "invalid-development-key", "system")
        host.wait(lambda: host.providers()[artwork]["state"] == "invalid_configuration")
        print(json.dumps({"provider": "SteamGridDB", "invalid_configuration": "rejected"}))
        host.configure(artwork, key, "user")
        host.wait(lambda: host.providers()[artwork]["state"] == "healthy")
        print(json.dumps({"provider": "SteamGridDB", "user_configuration": "healthy"}))

    started = time.monotonic()
    session = host.call("POST", "/api/metadata/sessions", {"query": "Portal 2", "media_type": "game"})
    session_id = session["id"]
    first = host.wait(lambda: host.call("GET", "/api/metadata/sessions/" + session_id)["results"])
    print(json.dumps({"first_result_seconds": round(time.monotonic() - started, 3),
                      "initial_assets": sum(len(candidate["assets"]) for candidate in first)}))
    assert all(not candidate["assets"] for candidate in first)
    candidate = next((item for item in first if item["provider_ids"].get("steam") == "620"), None)
    if candidate is None:
        complete = host.wait(lambda: (
            data if (data := host.call("GET", "/api/metadata/sessions/" + session_id))["state"]
            in {"completed", "degraded"} else None))
        candidate = next(item for item in complete["results"]
                         if item["provider_ids"].get("steam") == "620")
    host.call("POST", "/api/metadata/sessions/" + session_id + "/selection",
              {"candidate_id": candidate["id"]})
    def enriched():
        data = host.call("GET", "/api/metadata/sessions/" + session_id)
        selected = next(item for item in data["results"] if item["id"] == data["selected"])
        return selected if selected["metadata"].get("description") and (
            not key or selected["assets"]) else None
    selected = host.wait(enriched)
    print(json.dumps({"provider": "Steam", "metadata_fields": sorted(selected["metadata"]),
                      "selected_assets": len(selected["assets"]),
                      "total_seconds": round(time.monotonic() - started, 3)}))
    host.call("DELETE", "/api/metadata/sessions/" + session_id)
    if key:
        host.configure(artwork, key, "system")
        host.configure(artwork, None, "user")
        host.wait(lambda: host.providers()[artwork]["state"] == "healthy")
        print(json.dumps({"provider": "SteamGridDB", "system_configuration": "healthy"}))


if __name__ == "__main__":
    main()
