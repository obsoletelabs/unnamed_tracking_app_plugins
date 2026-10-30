"""RetroAchievements console coverage and cursor handling, with mocked HTTP only."""

from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest

from sdk import metadata_provider as sdk
from test_metadata_providers import plugin


@pytest.fixture
def gateway(monkeypatch):
    state = SimpleNamespace(requested=[], games={})

    def request(method, capability, payload):
        if method == "metadata_providers.configuration":
            return {"values": {"api_key": "disposable"}}
        if method == "storage.get":
            return {"value": None}
        if method == "storage.compare_and_swap":
            return {"swapped": True}
        assert method == "network.request"
        url = urlsplit(payload["url"])
        query = parse_qs(url.query)
        if url.path.endswith("API_GetGameList.php"):
            console = int(query["i"][0])
            state.requested.append(console)
            return {"status": 200, "data": state.games.get(console, [])}
        raise AssertionError("Unexpected endpoint " + url.path)

    monkeypatch.setattr(sdk, "request", request)
    return state


def search(module, query, cursor=None):
    work = {"policy": "interactive", "query": query, "limit": 20}
    if cursor is not None:
        work["cursor"] = cursor
    return module.search({"request": work})


def test_reported_omissions_and_previously_covered_systems_are_mapped(monkeypatch):
    module = plugin("retroachievements", monkeypatch)
    names = module.CONSOLE_NAMES
    assert names[5] == "Game Boy Advance" and names[40] == "Dreamcast" and names[41] == "PlayStation Portable"
    assert {1, 2, 3, 4, 7, 8, 11, 12, 15, 18, 21} <= set(module.CONSOLES)
    assert len(module.CONSOLES) > 11 and len(set(module.CONSOLES)) == len(module.CONSOLES)
    # Existing saved cursors index the original eleven consoles in their original order.
    assert module.CONSOLES[:11] == (1, 2, 3, 4, 7, 8, 11, 12, 15, 18, 21)
    # Events and hubs are not game systems.
    assert not {101, 102} & set(module.CONSOLES)


@pytest.mark.parametrize("console,title", [(5, "Metroid Fusion"), (40, "Crazy Taxi"), (41, "Daxter")])
def test_games_on_newly_covered_systems_are_discoverable_across_cursor_pages(gateway, monkeypatch, console, title):
    module = plugin("retroachievements", monkeypatch)
    gateway.games[console] = [{"ID": 900 + console, "Title": title, "ConsoleName": None}]
    cursor, found = None, []
    for _ in range(len(module.CONSOLES) + 1):
        result = search(module, title.lower(), cursor)
        found += result["candidates"]
        cursor = result["next_cursor"]
        if cursor is None:
            break
    assert cursor is None and sorted(gateway.requested) == sorted(module.CONSOLES)
    assert [item["title"] for item in found] == [title]
    # A missing ConsoleName falls back to the mapped system name.
    assert found[0]["platforms"] == [module.CONSOLE_NAMES[console]]


def test_unsupported_or_stale_cursors_end_the_search_without_a_request(gateway, monkeypatch):
    module = plugin("retroachievements", monkeypatch)
    for cursor in (str(len(module.CONSOLES)), "9999", "-1"):
        assert search(module, "anything", cursor) == {"candidates": [], "next_cursor": None}
    assert gateway.requested == []
    assert search(module, "anything", "abc") == {"failure": {"code": "invalid_response"}}


def test_last_console_has_no_next_cursor(gateway, monkeypatch):
    module = plugin("retroachievements", monkeypatch)
    result = search(module, "x", str(len(module.CONSOLES) - 1))
    assert result["next_cursor"] is None and gateway.requested == [module.CONSOLES[-1]]
