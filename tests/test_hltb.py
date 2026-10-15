"""HLTB initialization and completion categories use only the public gateway."""

import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import SimpleNamespace

import jsonschema
import pytest

from sdk import metadata_provider as sdk
from test_metadata_providers import plugin


@pytest.fixture
def gateway(monkeypatch):
    state = SimpleNamespace(calls=[], statuses=[200], entries=[{
        "game_id": 723, "game_name": "Portal", "comp_main": 3600,
        "comp_plus": 5400, "comp_100": 7200, "comp_all": 6000,
    }])

    def request(method, capability, payload):
        if method == "storage.get":
            return {"value": None}
        if method == "storage.compare_and_swap":
            return {"swapped": True}
        assert method == "network.request" and capability == "network.outbound"
        state.calls.append(payload)
        assert payload["headers"]["Origin"] == "https://howlongtobeat.com"
        assert "Chrome/" in payload["headers"]["User-Agent"]
        if "/site/init?" in payload["url"]:
            return {"status": 200, "data": {"token": "token-" + str(len(state.calls))}}
        assert payload["url"] == "https://howlongtobeat.com/api/search/site"
        assert payload["method"] == "POST"
        assert payload["body"]["searchTerms"] == ["Portal"]
        status = state.statuses.pop(0)
        return {"status": status, "data": {"data": state.entries} if status == 200 else {"secret": "discard"}}

    monkeypatch.setattr(sdk, "request", request)
    return state


def values(**candidate):
    return {"request": {"policy": "background"}, "candidate": {"title": "Portal", **candidate}}


def test_initializes_renews_once_and_emits_all_available_categories(gateway, monkeypatch):
    gateway.statuses = [403, 200]
    module = plugin("hltb", monkeypatch)
    result = module.metadata(values())
    assert result["metadata"] == {
        "time_to_beat_hours": 1.0, "time_to_beat_extras_hours": 1.5,
        "time_to_beat_completionist_hours": 2.0, "time_to_beat_all_hours": 1.7,
        "provider_ids": {"hltb": "723"},
    }
    assert len(gateway.calls) == 4
    assert gateway.calls[1]["headers"]["X-Auth-Token"] == "token-1"
    assert gateway.calls[3]["headers"]["X-Auth-Token"] == "token-3"
    schema = json.loads((Path(__file__).parents[1] / "tools/schemas/metadata-response-v1.schema.json").read_text())
    jsonschema.validate(result, schema)


def test_repeated_rejection_stops_after_one_renewal_even_in_background(gateway, monkeypatch):
    gateway.statuses = [403, 403]
    assert plugin("hltb", monkeypatch).metadata(values()) == {"failure": {"code": "unavailable"}}
    assert len(gateway.calls) == 4


def test_partial_categories_do_not_require_a_main_story_estimate(gateway, monkeypatch):
    gateway.entries[0].update(comp_main=0, comp_plus=float("nan"), comp_all=True)
    result = plugin("hltb", monkeypatch).metadata(values())
    assert result["metadata"] == {"time_to_beat_completionist_hours": 2.0, "provider_ids": {"hltb": "723"}}


def test_known_identity_wins_and_ambiguous_titles_are_not_guessed(gateway, monkeypatch):
    gateway.entries.append({**gateway.entries[0], "game_id": 724, "comp_main": 7200})
    module = plugin("hltb", monkeypatch)
    assert module.metadata(values()) == {}
    gateway.statuses = [200]
    selected = module.metadata(values(provider_ids={"hltb": "724"}))
    assert selected["metadata"]["time_to_beat_hours"] == 2.0
    assert selected["metadata"]["provider_ids"] == {"hltb": "724"}


def test_actual_package_uses_its_bundled_sdk_and_only_the_public_gateway(tmp_path, current_packages):
    with zipfile.ZipFile(current_packages["official.metadata-hltb"]) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["api_contract_version"] == "1.1.13"
        assert {item["name"] for item in manifest["capabilities"]} == {
            "metadata_providers.register", "metadata_providers.metadata", "metadata_providers.health",
            "network.outbound", "plugin.storage",
        }
        for name in archive.namelist():
            if name.startswith("payload/") and not name.endswith("/"):
                path = tmp_path / name.removeprefix("payload/")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(archive.read(name))
    responses = [
        {"value": None}, {"swapped": True}, {"status": 200, "data": {"token": "public-token"}},
        {"value": None}, {"swapped": True}, {"status": 200, "data": {"data": [{
            "game_id": 723, "game_name": "Portal", "comp_main": 3600, "comp_plus": 5400,
            "comp_100": 7200, "comp_all": 6000,
        }]}},
    ]
    result = subprocess.run(
        [sys.executable, "-c", "import json, plugin; print(json.dumps(plugin.metadata({'request': {'policy': 'interactive'}, 'candidate': {'title': 'Portal'}})))"],
        cwd=tmp_path, input="".join(json.dumps({"payload": value}) + "\n" for value in responses),
        text=True, capture_output=True, timeout=10, check=True,
    )
    *wire, response = map(json.loads, result.stdout.splitlines())
    assert [call["method"] for call in wire] == [
        "storage.get", "storage.compare_and_swap", "network.request",
        "storage.get", "storage.compare_and_swap", "network.request",
    ]
    assert all(call["api_version"] == "v1" for call in wire)
    assert wire[2]["payload"]["url"].startswith("https://howlongtobeat.com/api/search/site/init?")
    assert wire[5]["payload"]["headers"]["X-Auth-Token"] == "public-token"
    assert response["metadata"] == {
        "time_to_beat_hours": 1.0, "time_to_beat_extras_hours": 1.5,
        "time_to_beat_completionist_hours": 2.0, "time_to_beat_all_hours": 1.7,
        "provider_ids": {"hltb": "723"},
    }
