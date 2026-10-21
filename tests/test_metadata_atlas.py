"""Atlas provider: wire shape, URL handling and certainty rules, against a faked gateway."""
import importlib.util
import json
from pathlib import Path

import jsonschema
import pytest

from sdk import metadata_provider as sdk

ROOT = Path(__file__).resolve().parents[1]
TOKEN = "atl_secret_token"
GAME = {"id": "atlas:" + "a" * 26, "title": "Portal 2", "release_date": "2011-04-19",
        "description": "Co-op puzzles.", "developer": "Valve", "publisher": "Valve",
        "tags": ["Puzzle"], "features": ["Co-op"], "platforms": ["pc"],
        "provider_ids": {"steam": "620", "igdb": "72"}}


@pytest.fixture
def atlas(monkeypatch):
    directory = ROOT / "official" / "metadata-atlas"
    monkeypatch.syspath_prepend(str(directory))
    spec = importlib.util.spec_from_file_location("metadata_test_atlas", directory / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Gateway:
    def __init__(self, monkeypatch, config=None, routes=None):
        self.config = {"base_url": "https://atlas.test/", "api_token": TOKEN} if config is None else config
        self.routes = routes or {}
        self.calls = []
        monkeypatch.setattr(sdk, "request", self)

    def __call__(self, method, capability, payload=None):
        if method == "metadata_providers.configuration":
            return {"values": self.config}
        assert method == "network.request" and capability == "network.outbound"
        self.calls.append(payload)
        url = payload["url"].split("?")[0]
        for suffix, response in self.routes.items():
            if url.endswith(suffix):
                return response
        return {"status": 404, "error": "not found"}


def work(**extra):
    return {"request": {"query": "portal", "limit": 5, **extra}}


def test_registration_declares_url_as_plain_setting_and_token_as_secret(atlas):
    schema = json.loads((ROOT / "tools/schemas/metadata-registration-v1.schema.json").read_text())
    jsonschema.validate(atlas.DECLARATION, schema)
    fields = {item["key"]: item for item in atlas.DECLARATION["configuration"]}
    assert fields["base_url"]["secret"] is False
    assert fields["api_token"].get("secret", True) is True


def test_search_maps_games_and_sends_token_only_in_authorization(atlas, monkeypatch):
    gateway = Gateway(monkeypatch, routes={"/api/v2/games": {"status": 200, "data": {"results": [GAME]}}})
    result = atlas.search(work())
    assert result["candidates"] == [{
        "provider": atlas.PROVIDER_ID, "external_id": GAME["id"], "title": "Portal 2", "media_type": "game",
        "provider_ids": {"atlas": GAME["id"], "steam": "620", "igdb": "72"}, "year": 2011}]
    call = gateway.calls[0]
    assert call["url"].startswith("https://atlas.test/api/v2/games?q=portal&limit=5")
    assert TOKEN not in call["url"] and call["headers"]["Authorization"] == "Bearer " + TOKEN


def test_metadata_by_atlas_id_matches_response_schema(atlas, monkeypatch):
    Gateway(monkeypatch, routes={"/games/" + GAME["id"]: {"status": 200, "data": GAME}})
    selected = {"provider": atlas.PROVIDER_ID, "external_id": GAME["id"], "title": "Portal 2"}
    result = atlas.metadata({"request": {}, "candidate": selected})
    schema = json.loads((ROOT / "tools/schemas/metadata-response-v1.schema.json").read_text())
    jsonschema.validate(result, schema)
    assert result["metadata"]["developer"] == "Valve" and result["metadata"]["year"] == 2011
    assert result["metadata"]["provider_ids"] == {"atlas": GAME["id"], "steam": "620", "igdb": "72"}


def test_unknown_or_malformed_id_returns_nothing_not_failure(atlas, monkeypatch):
    gateway = Gateway(monkeypatch)
    missing = {"provider": atlas.PROVIDER_ID, "external_id": "atlas:" + "b" * 26, "title": "x"}
    assert atlas.metadata({"request": {}, "candidate": missing}) == {}
    hostile = {"provider": atlas.PROVIDER_ID, "external_id": "../../admin/tokens", "title": "x"}
    assert atlas.metadata({"request": {}, "candidate": hostile}) == {}
    assert len(gateway.calls) == 1  # the hostile id never reached the network


@pytest.mark.parametrize("method, accepted", [("crosswalk", True), ("exact", True), ("fuzzy", False), ("none", False)])
def test_identity_lookup_only_accepts_certain_matches(atlas, monkeypatch, method, accepted):
    result = {"results": [{"canonical_id": GAME["id"], "method": method, "game": GAME}]}
    gateway = Gateway(monkeypatch, routes={"/resolve": {"status": 200, "data": result}})
    selected = {"provider": "official.metadata-steam.steam", "title": "Portal 2", "year": 2011,
                "provider_ids": {"steam": "620", "Bad Key!": "x"}}
    out = atlas.metadata({"request": {}, "candidate": selected})
    assert bool(out) is accepted
    body = gateway.calls[0]["body"]
    assert gateway.calls[0]["method"] == "POST"
    assert body["items"][0]["provider_ids"] == {"steam": "620"}


@pytest.mark.parametrize("url", ["", "ftp://atlas.test", "https://user:pw@atlas.test", "https://atlas.test/?x=1",
                                 "https://atlas.test/#f", "atlas.test", "https://"])
def test_bad_server_urls_are_rejected_before_any_request(atlas, monkeypatch, url):
    gateway = Gateway(monkeypatch, config={"base_url": url, "api_token": TOKEN})
    assert atlas.search(work()) == {"failure": {"code": "invalid_configuration"}}
    assert gateway.calls == []


def test_path_prefix_and_trailing_slash_are_supported(atlas, monkeypatch):
    gateway = Gateway(monkeypatch, config={"base_url": "http://192.168.1.20:8000/atlas/", "api_token": TOKEN},
                      routes={"/games": {"status": 200, "data": {"results": []}}})
    assert atlas.search(work()) == {"candidates": []}
    assert gateway.calls[0]["url"].startswith("http://192.168.1.20:8000/atlas/api/v2/games?")


def test_missing_configuration_and_rejected_token_are_typed(atlas, monkeypatch):
    Gateway(monkeypatch, config={})
    assert atlas.search(work())["failure"]["code"] == "not_configured"
    Gateway(monkeypatch, routes={"/games": {"status": 401, "error": "unauthorized"}})
    assert atlas.search(work())["failure"]["code"] == "invalid_configuration"
    Gateway(monkeypatch, routes={"/games": {"status": 429, "retry_after_seconds": 30}})
    assert atlas.search(work())["failure"] == {"code": "rate_limited", "retry_after_seconds": 30}
    Gateway(monkeypatch, routes={"/games": {"status": 200, "data": [1, 2]}})
    assert atlas.search(work())["failure"]["code"] == "invalid_response"


def test_health_validates_url_and_token(atlas, monkeypatch):
    Gateway(monkeypatch, routes={"/games": {"status": 200, "data": {"results": []}}})
    assert atlas.health(work()) == {"health": "healthy"}
    Gateway(monkeypatch, routes={"/games": {"status": 401, "error": "no"}})
    assert atlas.health(work())["failure"]["code"] == "invalid_configuration"


def test_media_lists_only_cached_artwork_as_public_links(atlas, monkeypatch):
    digest = "a" * 64
    art = {"results": [
        {"kind": "key_art", "media_url": f"/api/v2/media/{digest}", "width": 600, "height": 900},
        {"kind": "screenshot", "media_url": None, "url": "https://provider.test/s.jpg"},  # not cached: skipped
        {"kind": "weird", "media_url": f"/api/v2/media/{'b' * 64}"},
        {"kind": "hero", "media_url": "/api/v2/media/../../etc/passwd"}]}
    gateway = Gateway(monkeypatch, routes={"/games/" + GAME["id"] + "/artwork": {"status": 200, "data": art}})
    selected = {"provider": atlas.PROVIDER_ID, "external_id": GAME["id"], "title": "Portal 2"}
    out = atlas.media({"request": {}, "candidate": selected})
    assert out == {"assets": [{"kind": "key_art", "url": f"https://atlas.test/media/{digest}", "priority": 0,
                               "width": 600, "height": 900}]}
    schema = json.loads((ROOT / "tools/schemas/metadata-response-v1.schema.json").read_text())
    jsonschema.validate(out, schema)
    assert all("provider.test" not in call["url"] for call in gateway.calls)


def test_media_without_a_certain_match_returns_no_assets(atlas, monkeypatch):
    Gateway(monkeypatch, routes={"/resolve": {"status": 200, "data": {"results": [{"method": "fuzzy", "game": GAME}]}}})
    out = atlas.media({"request": {}, "candidate": {"provider": "x", "title": "Portal 2", "year": 2011}})
    assert out == {"assets": []}


def test_richer_atlas_fields_are_forwarded_and_validated_against_the_host_schema(atlas, monkeypatch):
    rich = {**GAME, "genres": ["Puzzle", "puzzle", "Platformer"], "themes": ["Sci-fi"], "languages": ["English"],
            "aliases": ["Portal Two", "Portal 2", ""], "age_rating": "PEGI 12", "website": "https://thinkwithportals.com",
            "critic_score": 95, "user_score": 90}
    Gateway(monkeypatch, routes={"/games/" + GAME["id"]: {"status": 200, "data": rich}})
    selected = {"provider": atlas.PROVIDER_ID, "external_id": GAME["id"], "title": "Portal 2"}
    result = atlas.metadata({"request": {}, "candidate": selected})
    jsonschema.validate(result, json.loads((ROOT / "tools/schemas/metadata-response-v1.schema.json").read_text()))
    data = result["metadata"]
    assert data["genres"] == ["Puzzle", "Platformer"] and data["tags"] == ["Puzzle", "Sci-fi"]
    assert data["languages"] == ["English"] and data["alternate_titles"] == ["Portal Two"]
    assert data["age_rating"] == "PEGI 12" and data["scores"] == {"critic": 95, "user": 90}
    assert data["links"] == [{"label": "Website", "url": "https://thinkwithportals.com"}]


@pytest.mark.parametrize("hostile", [
    {"genres": "Puzzle", "languages": [1, None], "aliases": {"a": 1}, "age_rating": 12, "website": "javascript:alert(1)",
     "critic_score": "95", "user_score": True},
    {"website": "https://evil.test/a b", "critic_score": 101, "user_score": -1, "genres": ["x" * 500]},
])
def test_malformed_optional_fields_are_dropped_not_forwarded(atlas, monkeypatch, hostile):
    Gateway(monkeypatch, routes={"/games/" + GAME["id"]: {"status": 200, "data": {**GAME, **hostile}}})
    selected = {"provider": atlas.PROVIDER_ID, "external_id": GAME["id"], "title": "Portal 2"}
    result = atlas.metadata({"request": {}, "candidate": selected})
    jsonschema.validate(result, json.loads((ROOT / "tools/schemas/metadata-response-v1.schema.json").read_text()))
    for key in ("genres", "languages", "alternate_titles", "age_rating", "links", "scores"):
        assert key not in result["metadata"], key
