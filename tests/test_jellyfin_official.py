"""Realistic Jellyfin 12 DTOs and failure/restart checkpoints; host tested separately."""

import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4, uuid5, NAMESPACE_URL

import pytest

SOURCE = Path(__file__).parents[1] / "official/jellyfin-media-sync"
USER, OTHER = str(uuid4()), str(uuid4())
REMOTE = "a" * 32
LIBRARY = "b" * 32
TOKEN = "DisposableTokenForTests"


def context(user=USER, admin=False, **values):
    return {"_plugin_context": {"user_id": user, "is_admin": admin}, **values}


def film(index=1):
    return {
        "Id": uuid5(NAMESPACE_URL, f"fixture-film:{index}").hex,
        "Type": "Movie",
        "Name": f"Film {index}",
        "ProductionYear": 2025,
        "ProviderIds": {"Tmdb": str(index)},
        "RunTimeTicks": 6000000000,
        "Overview": "A real-shaped synopsis",
        "Genres": ["Drama"],
        "ImageTags": {"Primary": "tag", "Logo": "logo"},
        "BackdropImageTags": ["backdrop"],
        "UserData": {
            "Played": False,
            "PlaybackPositionTicks": 3000000000,
            "PlayCount": 2,
            "LastPlayedDate": "2026-10-01T12:00:00Z",
        },
    }


@pytest.fixture
def service(monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE))
    modules = {}
    for name in ("jellyfin", "plugin", "attention", "sync"):
        spec = importlib.util.spec_from_file_location(name, SOURCE / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(__import__("sys").modules, name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    storage, calls, imports = {}, [], []
    catalogue = [film()]
    remote_errors, denied = {}, set()
    quick = {"approved": False}

    def gateway(method, capability, payload):
        calls.append((method, capability, payload))
        if capability in denied:
            raise RuntimeError("A denial may contain remote diagnostics SECRET")
        key = payload.get("key")
        if method == "storage.get":
            return {"value": storage.get(key)}
        if method == "storage.put":
            storage[key] = payload["value"]
            return {}
        if method == "storage.delete":
            storage.pop(key, None)
            return {}
        if method == "storage.keys":
            return {
                "keys": sorted(
                    k for k in storage if k.startswith(payload.get("prefix", ""))
                )
            }
        if method == "tasks.request":
            if payload["capability"] in denied:
                raise RuntimeError("denied SECRET")
            if payload["method"] == "notifications.send":
                return {"sent": True}
            if payload["method"] in {"notification_sources.register", "notifications.publish"}:
                return {"created": True, "registered": True}
            data = payload["payload"]
            imports.append(data)
            return {
                "id": str(uuid5(NAMESPACE_URL, data["external_id"])),
                "revision": "0" * 64,
            }
        if method == "network.request":
            url = urlsplit(payload["url"])
            path = url.path.removeprefix("/jellyfin")
            query = parse_qs(url.query)
            if path in remote_errors:
                return remote_errors[path]
            data = {}
            if path == "/System/Info/Public":
                data = {"Version": "12.1.0", "Id": "fixture-server"}
            elif path == "/System/Info":
                assert TOKEN in payload["headers"]["Authorization"]
                data = {"Version": "12.1.0"}
            elif path == "/Library/VirtualFolders":
                data = [
                    {"ItemId": LIBRARY, "Name": "Films", "CollectionType": "movies"},
                    {"ItemId": "c" * 32, "Name": "Music", "CollectionType": "music"},
                ]
            elif path == "/Users":
                data = [{"Id": REMOTE, "Name": "fixture-user"}]
            elif path in {
                "/Users/AuthenticateByName",
                "/Users/AuthenticateWithQuickConnect",
            }:
                assert payload["method"] == "POST"
                data = {
                    "User": {"Id": REMOTE, "Name": "fixture-user"},
                    "AccessToken": TOKEN,
                }
            elif path == "/QuickConnect/Enabled":
                data = True
            elif path == "/QuickConnect/Initiate":
                assert payload["method"] == "POST"
                data = {"Secret": "DisposableQuickSecret", "Code": "123456"}
            elif path == "/QuickConnect/Connect":
                data = {"Authenticated": quick["approved"]}
            elif path == "/Items":
                assert query["CollapseBoxSetItems"] == ["false"]
                rows = [
                    row
                    for row in catalogue
                    if not isinstance(row, dict)
                    or (
                        row.get("Type") != "Episode"
                        if query["IncludeItemTypes"] == ["Movie,Series"]
                        else row.get("Type") == "Episode"
                    )
                ]
                start, limit = int(query["StartIndex"][0]), int(query["Limit"][0])
                data = {
                    "Items": rows[start : start + limit],
                    "TotalRecordCount": len(rows),
                }
            elif path.startswith("/user_usage_stats/"):
                reported_day = (
                    datetime.now(timezone.utc).date() - timedelta(days=2)
                ).isoformat()
                data = (
                    [
                        {
                            "Id": film()["Id"],
                            "Type": "Movie",
                            "Time": "12:00:00",
                            "Duration": "100",
                            "RowId": "1",
                        }
                    ]
                    if "/" + reported_day + "/" in path
                    else []
                )
            return {"status": 200, "data": data}
        return {}

    for module in modules.values():
        monkeypatch.setattr(module, "request", gateway)
    monkeypatch.setattr(__import__("sdk.notification_stories", fromlist=["x"]), "request", gateway)
    plugin, sync, jellyfin = (modules[k] for k in ("plugin", "sync", "jellyfin"))
    server_id = plugin.save_server(
        context(admin=True, url="https://fixture.test/jellyfin/", api_key=TOKEN)
    )["server_id"]
    plugin.test_connection(context(admin=True, server_id=server_id))
    account_id = plugin.login(
        context(
            server_id=server_id, username="fixture-user", password="disposable-password"
        )
    )["account_id"]
    return (
        plugin,
        sync,
        jellyfin,
        server_id,
        account_id,
        storage,
        calls,
        imports,
        catalogue,
        remote_errors,
        denied,
        quick,
    )


def finish(service, maximum=200):
    plugin, sync, _, _, account_id, *_ = service
    account = plugin.account_by_id(USER, account_id)
    plugin.sync_now(context(account_id=account_id))
    for _ in range(maximum):
        sync.run_account(USER, account)
        state = plugin.status(context())["accounts"][account_id]
        if state["phase"] == "error":
            return state
        if state["phase"] == "idle" and state.get("finished_at"):
            return state
    pytest.fail("census did not finish")


def test_credentials_are_private_and_replacement_removal_retain_config(service):
    plugin, _, _, server, account, storage, *_ = service
    config = plugin.get_config(context())
    assert TOKEN not in json.dumps(config) and "disposable-password" not in json.dumps(
        storage
    )
    assert config["accounts"][0]["credential_configured"]
    plugin.save_account(
        context(account_id=account, background_sync=True, libraries=[LIBRARY])
    )
    plugin.clear_account_credential(context(account_id=account))
    assert plugin.account_by_id(USER, account)["libraries"] == [LIBRARY]
    assert not plugin.get_config(context())["accounts"][0]["credential_configured"]
    with pytest.raises(Exception, match="Reconnect"):
        plugin.account_token(
            USER, plugin.account_by_id(USER, account), plugin.server_by_id(server)
        )
    plugin.login(
        context(
            server_id=server,
            account_id=account,
            username="fixture-user",
            password="another-password",
        )
    )
    assert plugin.account_by_id(USER, account)["libraries"] == [LIBRARY]


def test_admin_and_other_user_boundaries(service):
    plugin, _, jellyfin, server, account, *_ = service
    with pytest.raises(jellyfin.SyncError, match="Administrator"):
        plugin.save_mappings(context(server_id=server, mappings={LIBRARY: "anime"}))
    with pytest.raises(jellyfin.SyncError, match="belong"):
        plugin.save_account(context(user=OTHER, account_id=account))
    other = plugin.get_config(context(user=OTHER))
    assert not other["accounts"] and not other["reviews"]
    assert all(
        "users" not in s and "identity_access" not in s for s in other["servers"]
    )


def test_multiple_accounts_quick_connect_does_not_return_secret(service):
    plugin, _, _, server, account, _, _, _, _, _, _, quick = service
    started = plugin.quick_connect_start(context(server_id=server))
    assert "secret" not in json.dumps(started).lower()
    assert plugin.quick_connect_finish(context(pending_id=started["pending_id"]))[
        "pending"
    ]
    quick["approved"] = True
    second = plugin.quick_connect_finish(context(pending_id=started["pending_id"]))[
        "account_id"
    ]
    assert second != account
    plugin.order_accounts(context(account_ids=[second, account]))
    assert [a["id"] for a in plugin.get_config(context())["accounts"]] == [
        second,
        account,
    ]


def test_large_library_pagination_incremental_writes_and_two_census_tombstone(service):
    plugin, _, _, _, account, _, calls, imports, catalogue, *_ = service
    catalogue[:] = [film(i) for i in range(151)]
    assert finish(service)["processed"] == 151
    root_offsets = [
        parse_qs(urlsplit(p["url"]).query)["StartIndex"][0]
        for m, _, p in calls
        if m == "network.request"
        and "/Items?" in p["url"]
        and "Movie%2CSeries" in p["url"]
    ]
    assert root_offsets == ["0", "100"]
    first_count = len(imports)
    finish(service)
    assert len(imports) == first_count
    state_key = service[1].item_key(USER, account, film(0)["Id"])
    mapped = plugin.load(state_key)["host_id"]
    catalogue.pop(0)
    finish(service)
    assert plugin.load(state_key)["available"]
    finish(service)
    assert not plugin.load(state_key)["available"]
    assert plugin.load(state_key)["host_id"] == mapped


def test_rejected_host_write_is_not_checkpointed_and_resume_is_idempotent(service):
    plugin, sync, _, _, account, _, _, imports, _, _, denied, _ = service
    denied.add("media.write")
    failure = finish(service)
    assert failure["phase"] == "error" and "SECRET" not in failure["error"]
    item = plugin.load(sync.item_key(USER, account, film()["Id"]))
    assert not item.get("digest")
    denied.clear()
    assert finish(service)["phase"] == "idle"
    assert imports


def test_notifications_denied_authentication_paused_and_retry_cap(service):
    plugin, sync, _, _, account, _, calls, _, _, errors, denied, _ = service
    plugin.save_account(
        context(account_id=account, notifications=True, background_sync=True)
    )
    errors["/Items"] = {"status": 401, "error": "remote SECRET"}
    denied.add("notifications.send")
    state = finish(service)
    assert state["error_code"] == "authentication" and "SECRET" not in state["error"]
    before = len(calls)
    sync.run_account(USER, plugin.account_by_id(USER, account))
    assert not any(m == "network.request" for m, _, _ in calls[before:])
    status_key = "status/" + USER + "/" + account
    plugin.store(
        status_key, {**plugin.load(status_key), "next_auto_at": 0, "retry_at": 0}
    )
    before = len(calls)
    sync.run_account(USER, plugin.account_by_id(USER, account))
    assert not any(m == "network.request" for m, _, _ in calls[before:])


def test_reported_sessions_and_no_fabricated_history_when_unavailable(service):
    plugin, _, _, _, account, _, _, imports, *_ = service
    plugin.save_account(context(account_id=account, history_enabled=True))
    state = finish(service)
    assert state["phase"] == "idle"
    events = [e for p in imports for e in p["history"]]
    assert events and all(
        e["provenance"] == "reported_session" and e["external_id"] == "report:1"
        for e in events
    )


def test_malformed_page_cannot_finalize_or_erase_mappings(service):
    plugin, sync, _, _, account, _, _, _, catalogue, *_ = service
    finish(service)
    original = plugin.load(sync.item_key(USER, account, film()["Id"]))
    catalogue[:] = [None]
    failure = finish(service)
    assert failure["error_code"] == "remote_data"
    assert (
        plugin.load(sync.item_key(USER, account, film()["Id"]))["available"]
        == original["available"]
    )


def test_disabling_automatic_preserves_the_current_generation_and_offset(service):
    plugin, sync, _, _, account, _, _, _, catalogue, *_ = service
    catalogue[:] = [film(i) for i in range(151)]
    plugin.save_account(context(account_id=account, background_sync=True))
    sync.run_account(USER, plugin.account_by_id(USER, account))
    cursor_path = sync.base(USER, {"id": account}) + "cursor"
    initial = plugin.load(cursor_path)
    assert initial["offset"] == 100
    plugin.save_account(context(account_id=account, background_sync=False))
    sync.run_account(USER, plugin.account_by_id(USER, account))
    resumed = plugin.load(cursor_path)
    assert (
        resumed["generation"] == initial["generation"]
        and resumed["phase"] == "episodes"
    )


def test_rate_limit_retry_cap_and_next_automatic_run_replace_old_retry(service):
    plugin, sync, _, server, account, _, calls, *_ = service
    errors = service[9]
    errors["/Items"] = {"status": 429, "retry_after_seconds": 120}
    state = finish(service)
    assert (
        state["error_code"] == "transient"
        and state["retry_at"] >= int(sync.time.time()) + 119
    )
    config = plugin.server_by_id(server)
    config["max_retries"] = 0
    plugin.store("servers/" + server, config)
    status_path = "status/" + USER + "/" + account
    plugin.store(status_path, {**state, "retry_at": 0})
    before = len(calls)
    sync.run_account(USER, plugin.account_by_id(USER, account))
    assert not any(m == "network.request" for m, _, _ in calls[before:])
    errors.clear()
    plugin.save_account(context(account_id=account, background_sync=True))
    plugin.store(status_path, {**plugin.load(status_path), "next_auto_at": 0})
    sync.run_account(USER, plugin.account_by_id(USER, account))
    assert (
        plugin.load(status_path)["phase"] == "syncing"
        and plugin.load(status_path)["retry_at"] is None
    )


def test_http_warning_certificate_trust_and_anime_namespaces(service):
    plugin, _, jellyfin, server, _, _, _, _, _, errors, *_ = service
    saved = plugin.server_by_id(server)
    saved["url"] = "http://fixture.test/jellyfin"
    plugin.store("servers/" + server, saved)
    assert plugin.test_connection(context(admin=True, server_id=server))["warnings"]
    errors["/System/Info/Public"] = {"status": 0, "code": "certificate_untrusted"}
    result = plugin.test_connection(context(admin=True, server_id=server))
    assert not result["ok"] and "CA" in result["message"]
    row = film()
    row["ProviderIds"]["TmdbCollection"] = "123"
    anime = jellyfin.normalized(row, saved, "anime")
    assert anime["provider_ids"] == {"tmdb.movie": "1", "tmdbcollection": "123"}


def test_missing_history_endpoint_retains_counts_without_inventing_sessions(service):
    plugin, sync, _, _, account, _, _, imports, *_ = service
    plugin.save_account(context(account_id=account, history_enabled=True))
    original = sync.api

    def api(*args, **kwargs):
        if args[2].startswith("/user_usage_stats/"):
            raise service[2].SyncError("Unavailable", code="configuration")
        return original(*args, **kwargs)

    sync.api = api
    state = finish(service)
    assert "no past sessions are invented" in state["history_warning"]
    assert not any(p["history"] for p in imports)
    assert imports[0]["playback"]["play_count"] == 2


def test_nullable_runtime_unnumbered_episode_progress_and_explicit_mapping(service):
    plugin, sync, _, _, account, _, _, imports, catalogue, *_ = service
    root = {**film(), "Type": "Series", "RunTimeTicks": None}
    external = "d" * 32
    catalogue[:] = [
        root,
        {
            "Id": external,
            "SeriesId": root["Id"],
            "Type": "Episode",
            "Name": "Unnumbered special",
            "IndexNumber": None,
            "ParentIndexNumber": None,
            "RunTimeTicks": None,
            "UserData": {"Played": True, "PlayCount": 2},
        },
    ]
    assert finish(service)["phase"] == "idle"
    assert any(external in p["episode_progress"] for p in imports)
    assert not any(e["external_id"] == external for p in imports for e in p["episodes"])
    review = plugin.get_config(context())["reviews"][0]
    assert review["reason"] == "missing_episode_number"
    values = context(
        account_id=account,
        external_id=external,
        decision="map_episode",
        season=0,
        number=1,
    )
    values["_plugin_context"]["confirmed"] = True
    plugin.resolve_review(values)
    assert finish(service)["phase"] == "idle"
    assert any(
        e["external_id"] == external and e["season"] == 0 and e["number"] == 1
        for p in imports
        for e in p["episodes"]
    )
    assert not plugin.get_config(context())["reviews"]


def test_approved_episode_parent_missing_from_roots_uses_user_scoped_lookup(service):
    plugin, sync, _, _, account, _, _, imports, catalogue, *_ = service
    parent = {**film(), "Type": "Series"}
    catalogue[:] = [
        {
            "Id": "e" * 32,
            "SeriesId": parent["Id"],
            "Type": "Episode",
            "Name": "Special",
            "IndexNumber": 1,
            "ParentIndexNumber": 0,
            "UserData": {"Played": True},
        }
    ]
    original = sync.api
    fetched = []

    def api(server, token, path, **kwargs):
        if path == "/Users/" + REMOTE + "/Items/" + parent["Id"]:
            fetched.append(path)
            return parent
        return original(server, token, path, **kwargs)

    sync.api = api
    assert finish(service)["phase"] == "idle"
    assert len(fetched) == 1 and any(
        e["external_id"] == "e" * 32 for p in imports for e in p["episodes"]
    )
    assert plugin.load(sync.item_key(USER, account, parent["Id"]))["host_id"]


def test_reported_history_does_not_complete_a_partially_numbered_series(service):
    plugin, sync, _, _, account, _, _, imports, catalogue, *_ = service
    root = {**film(), "Type": "Series"}
    external = "d" * 32
    catalogue[:] = [
        root,
        {
            "Id": external,
            "SeriesId": root["Id"],
            "Type": "Episode",
            "Name": "Unnumbered recording",
            "UserData": {"Played": True},
        },
    ]
    plugin.save_account(context(account_id=account, history_enabled=True))
    original = sync.api

    def api(*args, **kwargs):
        if args[2].startswith("/user_usage_stats/"):
            return [
                {
                    "Id": external,
                    "Type": "Episode",
                    "Time": "12:00:00",
                    "Duration": "100",
                    "RowId": "recorded-session",
                }
            ]
        return original(*args, **kwargs)

    sync.api = api
    assert finish(service)["phase"] == "idle"
    history = [p for p in imports if p["history"]]
    assert history and all(not p["inventory_complete"] for p in history)
    assert all(p["history"][0]["episode_external_id"] == external for p in history)


def background_calls(calls, method):
    return [
        p["payload"]
        for m, c, p in calls
        if m == "tasks.request" and p["method"] == method
    ]


def test_sync_problems_are_one_story_per_account_that_resolves_on_recovery(service):
    plugin, sync, _, _, account, _, calls, _, _, errors, denied, _ = service
    plugin.save_account(context(account_id=account, notifications=True))
    errors["/Items"] = {"status": 500, "error": "remote SECRET"}
    state = finish(service)
    assert state["phase"] == "error"
    published = background_calls(calls, "notifications.publish")
    assert len(published) == 1 and background_calls(calls, "notifications.send") == []
    event = published[0]
    assert event["story"] == {"key": "sync:" + account, "phase": "attention"}
    assert event["content"]["actions"][0]["target"] == {
        "kind": "host_route",
        "path": "/plugins/official.jellyfin-media-sync/accounts",
    }
    assert "SECRET" not in json.dumps(event)
    assert background_calls(calls, "notification_sources.register")
    # The same failure again is not a second event; a recovery resolves the same story.
    status_key = "status/" + USER + "/" + account
    plugin.store(status_key, {**plugin.load(status_key), "retry_at": 0, "failures": 0})
    sync.run_account(USER, plugin.account_by_id(USER, account))
    assert len(background_calls(calls, "notifications.publish")) == 1
    errors.clear()
    assert finish(service)["phase"] == "idle"
    resolved = background_calls(calls, "notifications.publish")[-1]
    assert resolved["story"] == {"key": "sync:" + account, "phase": "resolved"}
    assert plugin.load(status_key)["notified_error"] is None


def test_unavailable_story_contract_falls_back_to_the_plain_message(service):
    plugin, _, _, _, account, _, calls, _, _, errors, denied, _ = service
    plugin.save_account(context(account_id=account, notifications=True))
    errors["/Items"] = {"status": 500, "error": "remote SECRET"}
    denied.add("notifications.canonical")
    state = finish(service)
    assert state["phase"] == "error" and "SECRET" not in state["error"]
    sent = background_calls(calls, "notifications.send")
    assert len(sent) == 1 and sent[0]["body"] == state["error"]


def test_stories_are_not_published_when_the_user_disabled_notifications(service):
    plugin, _, _, _, account, _, calls, _, _, errors, _, _ = service
    plugin.save_account(context(account_id=account, notifications=False))
    errors["/Items"] = {"status": 500, "error": "x"}
    finish(service)
    assert not background_calls(calls, "notifications.publish")
    assert not background_calls(calls, "notifications.send")


def _watch(service, **extra):
    return service[0].watch_now(
        {"_plugin_context": {"user_id": USER, "is_admin": False, "resource_id": WATCH_MEDIA}, **extra})


WATCH_MEDIA = str(uuid4())


def _seed_watch(service, available=True, user=USER):
    plugin, _, _, server, account, *_ = service
    plugin.store("watch/" + user + "/" + WATCH_MEDIA + "/" + account,
                 {"external_id": film()["Id"], "library_id": LIBRARY, "available": available})
    plugin.save_mappings(context(admin=True, server_id=server, mappings={LIBRARY: "movie"}))


def _reads(service):
    return sum(1 for m, c, _ in service[6] if m == "storage.get")


def test_watch_lookup_is_cached_after_the_first_open(service):
    plugin, *_ = service
    _seed_watch(service)
    first = _watch(service)
    assert first["ok"] and "cached" not in first
    before = _reads(service)
    second = _watch(service)
    assert second["ok"] and second["cached"] is True and second["url"] == first["url"]
    assert _reads(service) - before == 1  # one cache read, no account or server lookups
    assert [m for m, *_ in service[6][-1:]] == ["storage.get"]


def test_cached_only_returns_immediately_on_a_miss_without_looking_up(service):
    _seed_watch(service)
    before = len(service[6])
    pending = _watch(service, cached_only=True)
    assert pending == {"ok": False, "pending": True, "message": "Looking up your Jellyfin libraries."}
    assert [m for m, *_ in service[6][before:]] == ["storage.get"]
    assert _watch(service)["ok"]
    assert _watch(service, cached_only=True)["cached"] is True


def test_entries_expire_and_negative_results_expire_sooner(service, monkeypatch):
    plugin, *_ = service
    _seed_watch(service, available=False)
    clock = {"now": 1_000_000.0}
    monkeypatch.setattr(plugin.time, "time", lambda: clock["now"])
    assert _watch(service)["ok"] is False
    assert _watch(service)["cached"] is True
    clock["now"] += plugin.WATCH_MISS_TTL + 1
    assert "cached" not in _watch(service)
    _seed_watch(service)  # mapping becomes available; a hit would still be the stale miss
    plugin.invalidate_watch_cache(USER)
    assert _watch(service)["ok"]
    clock["now"] += plugin.WATCH_MISS_TTL + 1
    assert _watch(service)["cached"] is True  # positive results live for the longer TTL
    clock["now"] += plugin.WATCH_CACHE_TTL
    assert "cached" not in _watch(service)


def test_failed_open_refresh_evicts_and_looks_up_again(service):
    _seed_watch(service)
    _watch(service)
    before = _reads(service)
    refreshed = _watch(service, refresh=True)
    assert refreshed["ok"] and "cached" not in refreshed and _reads(service) - before > 1
    assert _watch(service)["cached"] is True


def test_configuration_changes_invalidate_the_cache(service):
    plugin, _, _, server, account, *_ = service
    _seed_watch(service)
    ignoring = lambda: plugin.save_mappings(context(admin=True, server_id=server, mappings={LIBRARY: "ignore"}))
    for change in (
        lambda: plugin.save_account(context(account_id=account, background_sync=True)),
        ignoring,
        lambda: plugin.order_accounts(context(account_ids=[account])),
    ):
        plugin.save_mappings(context(admin=True, server_id=server, mappings={LIBRARY: "movie"}))
        assert _watch(service)["ok"]
        assert _watch(service)["cached"] is True
        change()
        result = _watch(service)
        assert "cached" not in result
        if change is ignoring:
            assert result["ok"] is False  # an ignored library never serves a stale URL


def test_cache_is_per_user_bounded_and_cleared_on_completed_sync_and_restart(service):
    plugin, sync, _, _, account, storage, *_ = service
    _seed_watch(service)
    _watch(service)
    assert "watchcache/" + USER in storage and "watchcache/" + OTHER not in storage
    other = plugin.watch_now({"_plugin_context": {"user_id": OTHER, "is_admin": False, "resource_id": WATCH_MEDIA}})
    assert other["ok"] is False and "cached" not in other  # nothing leaks across users
    # The bound is enforced on write.
    for _ in range(plugin.WATCH_CACHE_MAX + 20):
        plugin.watch_now({"_plugin_context": {"user_id": USER, "is_admin": False, "resource_id": str(uuid4())}})
    assert len(json.loads(storage["watchcache/" + USER])["entries"]) <= plugin.WATCH_CACHE_MAX
    finish(service)
    assert "watchcache/" + USER not in storage  # a completed sync may change mappings
    _watch(service)
    plugin.invalidate_watch_cache()
    assert not [k for k in storage if k.startswith("watchcache/")]
