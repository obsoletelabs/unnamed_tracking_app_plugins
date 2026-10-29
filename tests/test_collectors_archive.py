"""The official archive consumes public DTOs and owns all feature state."""

import importlib.util
import json
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest

SOURCE = Path(__file__).parents[1] / "official/collectors-archive"
USER, OTHER, GAME, OTHER_GAME = map(str, (uuid4(), uuid4(), uuid4(), uuid4()))


@pytest.fixture
def archive(monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE))
    modules = {}
    for name in ("archive_storage", "prestige", "bounties", "cards", "transport", "plugin"):
        spec = importlib.util.spec_from_file_location(name, SOURCE / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    storage, calls, legacy = {}, [], {USER: {}, OTHER: {}}
    local = threading.local()
    lock = threading.RLock()
    denied = set()
    achievements = [{"id": str(uuid4()), "provider": "retroachievements", "external_id": "1", "name": "First clear", "tier": "missable", "unlocked": True, "unlocked_at": 10}]
    game = {"id": GAME, "title": "The Quest for a Safe Import", "status": "MASTERED", "tags": [], "features": [],
        "collections": ["Imported classics"], "achievement_total": 1, "achievement_unlocked": 1,
        "created_at": 10, "last_played_at": None}
    catalogue = [game]
    media = [{"id": str(uuid4()), "filename": "clear.png", "kind": "screenshot", "url": "/protected/clear.png"}]

    def gateway(method, capability, payload):
        with lock:
            calls.append((method, capability, payload))
            if capability in denied:
                raise RuntimeError("permission has not been granted")
            key = payload.get("key")
            if method == "storage.get":
                return {"value": storage.get(key)}
            if method == "storage.delete":
                storage.pop(key, None)
                return {}
            if method == "storage.compare_and_swap":
                if storage.get(key) != payload.get("expected"):
                    return {"swapped": False}
                if payload.get("value") is None:
                    storage.pop(key, None)
                else:
                    storage[key] = payload["value"]
                return {"swapped": True}
            if method == "storage.keys":
                return {"keys": sorted(key for key in storage if key.startswith(payload["prefix"]))}
            if method == "games.get":
                if payload["game_id"] != GAME or getattr(local, "user", USER) != USER:
                    raise RuntimeError("game not found")
                return {"game": game.copy(), "achievements": [item.copy() for item in achievements], "complete": True, "next_offset": len(achievements)}
            if method == "games.details.list":
                return {"games": catalogue.copy() if getattr(local, "user", USER) == USER else [], "complete": True, "next_offset": len(catalogue)}
            if method == "games.media.list":
                if payload["game_id"] != GAME or getattr(local, "user", USER) != USER:
                    raise RuntimeError("game not found")
                return {"media": media.copy(), "complete": True, "next_offset": len(media)}
            if method == "library.legacy.export":
                rows = legacy[getattr(local, "user", USER)].get(payload["table"], [])
                offset = int(payload["offset"])
                selected = rows[offset:offset + 2]
                return {"records": selected, "complete": offset + len(selected) >= len(rows), "next_offset": offset + len(selected)}
            raise AssertionError((method, capability))

    monkeypatch.setattr(modules["archive_storage"], "request", gateway)
    monkeypatch.setattr(modules["plugin"], "request", gateway)

    def invoke(function, values=None, *, user=USER):
        local.user = user
        return function({**(values or {}), "_plugin_context": {"user_id": user, "is_admin": False}})

    def imported(user=USER):
        for table in modules["plugin"].TABLES:
            offset = 0
            while True:
                result = invoke(modules["plugin"].import_legacy, {"table": table, "offset": offset}, user=user)
                if result["complete"]:
                    break
                offset = result["next_offset"]
    return modules, invoke, imported, storage, legacy, game, achievements, media, denied, calls


def operation(archive, path, method="GET", body=None, *, user=USER):
    modules, invoke, *_ = archive
    return invoke(modules["plugin"].api, {"path": path, "method": method, "body": body or {}, "user_id": OTHER}, user=user)


def test_import_retains_identifiers_customization_relations_and_reward_history(archive):
    modules, invoke, imported, storage, legacy, *_ = archive
    set_id, card_id, bounty_id, objective_id, evidence_id, journal_id, points_id = [str(uuid4()) for _ in range(7)]
    legacy[USER] = {
        "sets": [{"id": set_id, "name": "First set", "description": "Saved", "target_total": 1, "created_at": 1, "updated_at": 2}],
        "cards": [{"id": card_id, "game_id": GAME, "archive_number": 42, "set_id": set_id, "bounty_id": bounty_id, "rarity": "rare", "card_customization": {"customArt": "data:image/png;base64,OLD", "frontTemplate": "minimal"}, "status": "printed", "created_at": 3, "updated_at": 4}],
        "bounties": [{"id": bounty_id, "title": "Original prestige", "type": "challenge", "game_id": GAME, "status": "completed", "progress_value": 100, "progress_target": 100, "progress_mode": "binary", "points_reward": 200, "created_at": 1, "started_at": 2, "completed_at": 3, "auto_generated": True}],
        "bounty_objectives": [{"id": objective_id, "bounty_id": bounty_id, "title": "Original objective", "kind": "checkbox", "done": True, "created_at": 1}],
        "bounty_evidence": [{"id": evidence_id, "bounty_id": bounty_id, "kind": "note", "text": "Original evidence", "created_at": 2}],
        "bounty_journal_entries": [{"id": journal_id, "bounty_id": bounty_id, "text": "Original journal", "created_at": 3}],
        "bounty_point_transactions": [{"id": points_id, "bounty_id": bounty_id, "amount": 150, "reason": "Historical reward", "created_at": 4}],
    }
    assert operation(archive, "cards")["status_code"] == 409
    imported()
    card = operation(archive, "cards/" + card_id)["body"]
    assert card == legacy[USER]["cards"][0]
    goal = operation(archive, "bounties/" + bounty_id)["body"]["bounty"]
    assert goal["objectives"][0]["id"] == objective_id
    assert goal["evidence"][0]["text"] == "Original evidence"
    assert goal["journal"][0]["text"] == "Original journal"
    assert operation(archive, "bounties/points/total")["body"]["total"] == 150
    points = operation(archive, "bounties/points/history")["body"]["transactions"]
    assert points[0]["id"] == points_id
    assert operation(archive, "sets/" + set_id)["body"]["is_complete"] is True
    operation(archive, "cards/" + card_id, "PATCH", {"rarity": "mythic"})
    imported()
    assert operation(archive, "cards/" + card_id)["body"]["rarity"] == "mythic"
    created = operation(archive, "cards", "POST", {"game_id": GAME})["body"]
    assert created["archive_number"] == 43
    imported(OTHER)
    assert operation(archive, "cards/" + card_id, user=OTHER)["status_code"] == 404
    assert operation(archive, "cards", user=OTHER)["body"] == []
    assert legacy[USER]["cards"][0]["rarity"] == "rare"


def test_interrupted_import_retries_without_losing_or_duplicating_records(archive):
    modules, invoke, imported, storage, legacy, *_ = archive
    legacy[USER]["sets"] = [{"id": str(uuid4()), "name": f"Set {index}", "target_total": None, "created_at": index} for index in range(5)]
    first = invoke(modules["plugin"].import_legacy, {"table": "sets", "offset": 0})
    assert first["next_offset"] == 2 and first["complete"] is False
    assert invoke(modules["plugin"].migration_status)["imported"] is False
    imported()
    assert len(operation(archive, "sets")["body"]) == 5
    imported()
    assert len(operation(archive, "sets")["body"]) == 5


def test_concurrent_card_numbers_and_rewards_are_unique(archive):
    modules, invoke, imported, *_ = archive
    imported()
    with ThreadPoolExecutor(max_workers=4) as workers:
        created = list(workers.map(lambda _: operation(archive, "cards", "POST", {"game_id": GAME}), range(10)))
    assert all(item["status_code"] == 201 for item in created)
    assert sorted(item["body"]["archive_number"] for item in created) == list(range(1, 11))
    goal = operation(archive, "bounties", "POST", {"title": "Once", "points_reward": 25})["body"]["bounty"]
    with ThreadPoolExecutor(max_workers=4) as workers:
        list(workers.map(lambda _: operation(archive, "bounties/" + goal["id"] + "/complete", "POST"), range(10)))
    assert operation(archive, "bounties/points/total")["body"]["total"] == 25
    assert len(operation(archive, "bounties/points/history")["body"]["transactions"]) == 1


def test_set_edit_completion_and_deletion_preserve_cards(archive):
    archive[2]()
    saved = operation(archive, "sets", "POST", {"name": "Completed classics", "target_total": 1})["body"]
    card = operation(archive, "cards", "POST", {"game_id": GAME, "set_id": saved["id"]})["body"]
    assert operation(archive, "sets/" + saved["id"])["body"]["is_complete"] is True
    assert operation(archive, "sets", "POST", {"name": saved["name"]})["status_code"] == 409
    assert operation(archive, "sets/" + saved["id"], "PATCH", {"name": "Renamed", "target_total": 2})["body"]["is_complete"] is False
    assert operation(archive, "sets/" + saved["id"], "DELETE")["status_code"] == 204
    assert operation(archive, "cards/" + card["id"])["body"]["set_id"] is None


def test_large_artwork_is_atomic_and_transfers_stay_personal(archive):
    modules, invoke, imported, storage, *_ = archive
    imported()
    card = operation(archive, "cards", "POST", {"game_id": GAME})["body"]
    payload = {"path": "cards/" + card["id"], "method": "PATCH", "body": {
        "card_customization": {"customArt": "data:image/png;base64," + "A" * 3_100_000}},
        "_plugin_context": {"user_id": OTHER}}
    encoded, token = json.dumps(payload), str(uuid4())
    size = modules["transport"].CHUNK_CHARACTERS
    count = (len(encoded) + size - 1) // size
    for index in range(count):
        invoke(modules["transport"].write, {"token": token, "index": index, "count": count,
            "content": encoded[index * size:(index + 1) * size]})
    with pytest.raises(ValueError, match="expired"):
        invoke(modules["transport"].incoming, {"request_id": token}, user=OTHER)
    result = invoke(modules["plugin"].api, {"request_id": token})
    transfer = result["transfer"]
    chunks = [invoke(modules["transport"].read, {"token": transfer["token"], "index": index})["content"] for index in range(transfer["count"])]
    response = json.loads("".join(chunks))
    assert response["status_code"] == 200
    assert response["body"]["card_customization"] == payload["body"]["card_customization"]
    saved = modules["archive_storage"].get(USER, "cards", card["id"])
    assert saved["card_customization"] == payload["body"]["card_customization"]
    with pytest.raises(ValueError, match="expired"):
        invoke(modules["transport"].read, {"token": transfer["token"], "index": 0}, user=OTHER)
    invoke(modules["transport"].drop, {"token": token})
    invoke(modules["transport"].drop, {"token": transfer["token"]})
    assert not any("/transfers/" in key for key in storage)
    assert all(len(json.dumps(call[2]).encode()) < 64_000 for call in archive[-1] if call[0].startswith("storage."))


def test_prestige_uses_real_verified_signals_and_one_linked_challenge(archive):
    modules, invoke, imported, storage, legacy, game, achievements, *_ = archive
    imported()
    card = operation(archive, "cards", "POST", {"game_id": GAME})["body"]
    achievements[0]["unlocked"] = False
    assert operation(archive, "cards/" + card["id"] + "/prestige-challenge", "POST")["status_code"] == 400
    achievements[0]["unlocked"] = True
    endpoint = "cards/" + card["id"] + "/prestige-challenge"
    first = operation(archive, endpoint, "POST")["body"]
    second = operation(archive, endpoint, "POST")["body"]
    assert first["bounty_id"] == second["bounty_id"]
    bounty = operation(archive, "bounties/" + first["bounty_id"])["body"]["bounty"]
    assert bounty["title"].startswith("Missable Sweep")
    assert bounty["points_reward"] == 0
    assert len(operation(archive, "bounties")["body"]["bounties"]) == 1


@pytest.mark.parametrize("kind", ["completion", "mastery", "achievement", "collection"])
def test_automatic_goals_follow_owned_game_progress(archive, kind):
    modules, invoke, imported, storage, legacy, game, achievements, *_ = archive
    imported()
    body = {"title": "Automatic " + kind, "type": kind, "game_id": GAME,
        "target_collection_name": "Imported classics", "target_achievement_id": achievements[0]["id"], "points_reward": 10}
    goal = operation(archive, "bounties", "POST", body)["body"]["bounty"]
    assert goal["status"] == "completed"
    assert operation(archive, "bounties/points/total")["body"]["total"] == 10


def test_objectives_evidence_journal_and_status_transitions(archive):
    modules, invoke, imported, storage, legacy, game, achievements, media, *_ = archive
    imported()
    goal = operation(archive, "bounties", "POST", {"title": "A full challenge", "type": "challenge", "points_reward": 20, "game_id": GAME})["body"]["bounty"]
    base = "bounties/" + goal["id"]
    operation(archive, base + "/pause", "POST")
    assert operation(archive, base)["body"]["bounty"]["status"] == "paused"
    operation(archive, base + "/resume", "POST")
    objective = operation(archive, base + "/objectives", "POST", {"title": "Win twice", "kind": "numeric", "progress_target": 2})["body"]["objective"]
    evidence = operation(archive, base + "/evidence", "POST", {"kind": "screenshot", "media_item_id": media[0]["id"]})["body"]["bounty"]["evidence"]
    assert evidence[0]["media_url"] == "/protected/clear.png"
    assert operation(archive, base + "/evidence", "POST", {"kind": "screenshot", "media_item_id": str(uuid4())})["status_code"] == 404
    assert operation(archive, base + "/evidence", "POST", {"kind": "link", "url": "javascript:alert(1)"})["status_code"] == 400
    operation(archive, base + "/journal", "POST", {"text": "Reached the second run"})
    completed = operation(archive, base + "/objectives/" + objective["id"], "PATCH", {"progress_value": 2})["body"]["bounty"]
    assert completed["status"] == "completed"
    assert completed["journal"][0]["text"] == "Reached the second run"
    assert operation(archive, base, "DELETE")["status_code"] == 400
    assert operation(archive, "bounties/points/total")["body"]["total"] == 20


def test_grants_and_context_cannot_be_bypassed(archive):
    modules, invoke, imported, storage, legacy, game, achievements, media, denied, *_ = archive
    imported()
    denied.add("games.read")
    with pytest.raises(RuntimeError, match="not been granted"):
        operation(archive, "cards", "POST", {"game_id": GAME})
    assert not modules["archive_storage"].records(USER, "cards")
    denied.clear()
    imported(OTHER)
    with pytest.raises(RuntimeError, match="game not found"):
        operation(archive, "cards", "POST", {"game_id": GAME}, user=OTHER)
    with pytest.raises(modules["archive_storage"].ArchiveError, match="Sign in"):
        modules["plugin"].migration_status({"user_id": USER})


def test_large_archives_use_bounded_record_pages(archive):
    modules, invoke, imported, storage, *_ = archive
    imported()
    for index in range(60):
        modules["archive_storage"].create(USER, "sets", {"name": f"Set {index:03}", "target_total": None})
    first = operation(archive, "sets")
    assert len(first["body"]) == 25 and first["next_offset"] == 25
    second = operation(archive, "sets?offset=25")
    assert len(second["body"]) == 25 and second["next_offset"] == 50
    assert len(operation(archive, "sets?offset=50")["body"]) == 10


def test_startup_bundle_defers_editor_code_and_styles_but_packages_every_chunk():
    from tools.distribution import collect_payload

    manifest = json.loads((SOURCE / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["native_frontend"]["styles"] == []
    files, _ = collect_payload(SOURCE.parent.parent, SOURCE, manifest)
    native = (SOURCE / "native").resolve()
    visited = set()

    def static_dependencies(path):
        assert path.is_relative_to(native) and path.is_file()
        if path in visited:
            return
        visited.add(path)
        source = path.read_text(encoding="utf-8")
        for dependency in re.findall(r'from\s+["\'](\.[^"\']+)["\']', source):
            static_dependencies((path.parent / dependency).resolve())

    entry = native / "app.js"
    static_dependencies(entry)
    # Global provider registration must stay small even as the card editor grows.
    assert sum(path.stat().st_size for path in visited) < 32 * 1024
    deferred = re.findall(r'import\(["\'](\.[^"\']+)["\']\)', entry.read_text(encoding="utf-8"))
    assert len(deferred) == 6
    for reference in deferred:
        asset = (entry.parent / reference).resolve()
        assert asset not in visited
        assert asset.is_relative_to(native)
        assert files[asset.relative_to(SOURCE).as_posix()] == asset.read_bytes().replace(b"\r\n", b"\n")
    assert files["native/style.css"] == (native / "style.css").read_bytes().replace(b"\r\n", b"\n")
