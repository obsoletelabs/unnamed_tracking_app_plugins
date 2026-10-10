from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

from test_domain_plugins import plugin_root

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT))
PLUGINS = (
    "ui-api",
    "playtime-report",
    "recently-played-notifier",
    "metadata-curator",
    "ui-playground",
    "scoped-document-viewer",
    "extended-session-manager",
    "discord-notifications",
)


def _load_plugin(name: str):
    path = plugin_root(name) / "plugin.py"
    spec = importlib.util.spec_from_file_location(
        f"smoke_{name.replace('-', '_')}", path
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_all_real_plugins_execute_their_main_logic(monkeypatch) -> None:
    responses = {
        "games.list": {
            "games": [
                {
                    "id": "1",
                    "title": "Alpha",
                    "playtime_minutes": 120,
                    "last_played": "2026-09-29T00:00:00Z",
                },
                {
                    "id": "2",
                    "title": "Beta",
                    "playtime_minutes": 30,
                    "last_played": "2026-09-28T00:00:00Z",
                },
            ]
        },
        "settings.get": {"value": "Example Game"},
        "games.metadata.search": {
            "results": [{"id": "m1", "title": "Example Game", "provider": "smoke"}]
        },
        "storage.put": {},
        "notifications.send": {},
        "lifecycle.ready": {},
    }

    calls: list[tuple[str, str, dict]] = []

    def fake_request(method: str, capability: str, payload: dict) -> dict:
        calls.append((method, capability, payload))
        return responses.get(method, {})

    for name, action in (("ui-api", "refresh"), ("playtime-report", "refresh"), ("recently-played-notifier", "run"), ("metadata-curator", "search")):
        module = _load_plugin(name)
        monkeypatch.setattr(module, "request", fake_request)
        result = getattr(module, action)({"_plugin_context": {"user_id": "test-user"}})
        assert isinstance(result, dict)
        assert any(method == "games.list" or method == "games.metadata.search" for method, _, _ in calls)
        if name != "ui-api":
            assert any(method == "storage.put" and payload["key"].startswith("users/test-user/") for method, _, payload in calls)
        calls.clear()


def test_ui_playground_action_never_echoes_secret(tmp_path: Path) -> None:
    _load_plugin("ui-playground")
    data_dir = tmp_path / "plugin-data" / "secrets"
    data_dir.mkdir(parents=True)
    (data_dir / "discord_webhook").write_text(
        "https://discord.example/SECRET", encoding="utf-8"
    )
    monkeypatch_env = os.environ.copy()
    monkeypatch_env["PLUGIN_DATA_DIR"] = str(data_dir.parent)
    monkeypatch_env["PYTHONPATH"] = (
        str(ROOT) + os.pathsep + monkeypatch_env.get("PYTHONPATH", "")
    )

    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "examples" / "ui-playground" / "plugin.py"),
            "announce",
        ],
        input=json.dumps(
            {
                "_plugin_context": {
                    "page_title": "Overview",
                    "path": "/plugins/example.ui-playground",
                }
            }
        )
        + "\n",
        text=True,
        capture_output=True,
        env=monkeypatch_env,
        check=False,
    )
    assert result.returncode == 0
    assert "SECRET" not in result.stdout
    payload = json.loads(result.stdout)
    assert payload["discord"] is True
    assert "content" in payload


def test_ui_playground_frontend_entry_is_complete() -> None:
    frontend = ROOT / "examples" / "ui-playground" / "frontend"
    entry = frontend / "index.html"
    assert entry.is_file()
    html = entry.read_text(encoding="utf-8")
    assert 'src="./app.js"' in html
    assert 'href="./style.css"' in html
    assert (frontend / "app.js").is_file()
    assert (frontend / "style.css").is_file()


def test_every_example_package_source_has_safe_paths_and_valid_frontend() -> None:
    for name in ("ui-api", *PLUGINS):
        manifest = json.loads((plugin_root(name) / "manifest.json").read_text(encoding="utf-8"))
        frontend = manifest.get("frontend")
        if frontend:
            entry = frontend["entry"]
            assert ".." not in Path(entry).parts
            assert (plugin_root(name) / entry).is_file()
