"""Personal goals, stable achievement targets, evidence, journal and reward history."""

from __future__ import annotations

import random
import time
from urllib.parse import urlsplit

import archive_storage as store

TYPES = ("completion", "mastery", "achievement", "collection", "challenge", "watch", "custom")
STATUSES = ("not_started", "active", "paused", "completed", "abandoned")
DIFFICULTIES = ("easy", "normal", "hard", "extreme")
MODES = ("binary", "percentage", "numeric")
KINDS = ("screenshot", "clip", "document", "note", "link")
AUTOMATIC = {"completion": "binary", "mastery": "percentage", "achievement": "binary", "collection": "numeric"}
FINISHED = {"BEATEN", "MASTERED"}


def achievement(game_id, value):
    _game, items = store.game(game_id)
    found = next((item for item in items if item["id"] == store.identifier(value)), None)
    if found is None:
        raise store.ArchiveError("Achievement not found for that game.", 404)
    return found


def create(user: str, body: dict, *, record_id=None, auto_generated=False) -> dict:
    kind = store.choice(body.get("type", "custom"), TYPES, "bounty type")
    status = store.choice(body.get("status", "active"), STATUSES, "bounty status")
    mode = store.choice(AUTOMATIC.get(kind, body.get("progress_mode", "binary")), MODES, "progress mode")
    difficulty = body.get("difficulty")
    if difficulty is not None:
        store.choice(difficulty, DIFFICULTIES, "difficulty")
    target_game = body.get("game_id")
    if target_game:
        target_game = store.identifier(target_game)
        store.game(target_game)
    if kind in AUTOMATIC and kind != "collection" and not target_game:
        raise store.ArchiveError("This bounty needs a target game.")
    collection = body.get("target_collection_name")
    if kind == "collection" and not collection:
        raise store.ArchiveError("Collection bounties need a target collection.")
    target = achievement(target_game, body.get("target_achievement_id")) if kind == "achievement" else None
    evidence = body.get("required_evidence_kinds", [])
    for value in evidence:
        store.choice(value, KINDS, "evidence kind")
    reward = store.number(body.get("points_reward", 0), "Points reward")
    if not reward.is_integer():
        raise store.ArchiveError("Points reward must be a whole number.")
    now = int(time.time())
    value = store.create(user, "bounties", {
        "title": store.title(body.get("title")), "description": body.get("description"),
        "type": kind, "difficulty": difficulty, "status": status, "auto_generated": auto_generated,
        "game_id": target_game, "target_collection_name": collection,
        "target_achievement_provider": target["provider"] if target else None,
        "target_achievement_external_id": target["external_id"] if target else None,
        "progress_mode": mode, "progress_value": 0,
        "progress_target": store.number(body["progress_target"], "Progress target", minimum=1) if body.get("progress_target") is not None else None,
        "points_reward": int(reward), "required_evidence_kinds": evidence,
        "target_date": body.get("target_date"), "started_at": now if status == "active" else None,
        "completed_at": now if status == "completed" else None,
    }, record_id=record_id)
    if status == "completed":
        award(user, value)
    return value


def children(user, bounty_id, kind):
    return sorted(store.records(user, kind + "/" + store.identifier(bounty_id)), key=lambda row: (row["created_at"], row["id"]))


def award(user, bounty):
    if bounty["points_reward"] <= 0:
        return
    key = store.prefix(user, "points") + bounty["id"]
    transaction = {"id": bounty["id"], "bounty_id": bounty["id"], "amount": bounty["points_reward"],
        "reason": bounty["title"], "created_at": bounty.get("completed_at") or int(time.time())}
    store.swap(key, None, transaction)


def complete(user, value):
    bounty = store.update(user, "bounties", value, lambda saved: {
        **saved, "status": "completed", "completed_at": saved.get("completed_at") or int(time.time())})
    award(user, bounty)
    return bounty


def objective_done(objective, achievements):
    if objective["kind"] == "numeric":
        return bool(objective.get("progress_target") and objective["progress_value"] >= objective["progress_target"])
    if objective["kind"] == "achievement":
        return any(item["provider"] == objective.get("target_achievement_provider") and
            item["external_id"] == objective.get("target_achievement_external_id") and item["unlocked"] for item in achievements)
    return bool(objective.get("done"))


def read(user, value, *, game_cache=None, all_games=None):
    bounty = store.get(user, "bounties", value)
    objectives = children(user, value, "objectives")
    game_cache = game_cache if game_cache is not None else {}
    game, achievements = None, []
    if bounty.get("game_id"):
        target = bounty["game_id"]
        if target not in game_cache:
            try:
                game_cache[target] = store.game(target)
            except RuntimeError as exc:
                # A missing/deleted game is historical, but withdrawn permissions must fail closed.
                if "not found" not in str(exc).lower():
                    raise
                game_cache[target] = (None, [])
        game, achievements = game_cache[target]
    for objective in objectives:
        objective["done"] = objective_done(objective, achievements)
    if bounty["status"] == "active" and (objectives or bounty["type"] in AUTOMATIC):
        if objectives:
            mode, target, progress = "numeric", len(objectives), sum(item["done"] for item in objectives)
        elif bounty["type"] == "completion":
            mode, target, progress = "binary", 100, 100 if game and game["status"] in FINISHED else 0
        elif bounty["type"] == "mastery":
            mode, target, progress = "percentage", 100, sum(bool(item["unlocked"]) for item in achievements) / len(achievements) * 100 if achievements else 0
        elif bounty["type"] == "achievement":
            mode, target = "binary", 100
            progress = 100 if any(item["provider"] == bounty.get("target_achievement_provider") and
                item["external_id"] == bounty.get("target_achievement_external_id") and item["unlocked"] for item in achievements) else 0
        else:
            selected = [item for item in (all_games if all_games is not None else store.games()) if bounty["target_collection_name"] in (item.get("collections") or [])]
            mode, target, progress = "numeric", len(selected), sum(item["status"] in FINISHED for item in selected)
        def refresh(saved):
            if saved["status"] != "active":
                return saved
            result = {**saved, "progress_mode": mode, "progress_target": target, "progress_value": progress}
            if target > 0 and progress >= target:
                result.update(status="completed", completed_at=saved.get("completed_at") or int(time.time()))
            return result
        # Reads are frequent (search and notification providers); only write on change.
        if ((bounty.get("progress_mode"), bounty.get("progress_target"), bounty.get("progress_value"))
                != (mode, target, progress) or (target > 0 and progress >= target)):
            bounty = store.update(user, "bounties", value, refresh)
    if bounty["status"] == "completed":
        award(user, bounty)
    evidence = children(user, value, "evidence")
    if bounty.get("game_id") and any(item.get("media_item_id") for item in evidence):
        owned_media = {item["id"]: item for item in store.media(bounty["game_id"])}
        for item in evidence:
            media = owned_media.get(item.get("media_item_id"))
            item["media_url"] = media["url"] if media else None
            item["media_filename"] = media["filename"] if media else None
    target_achievement = next((item for item in achievements if item["provider"] == bounty.get("target_achievement_provider") and item["external_id"] == bounty.get("target_achievement_external_id")), None)
    return {**bounty, "game_title": game["title"] if game else None,
        "target_achievement_name": target_achievement["name"] if target_achievement else None,
        "objectives": objectives, "evidence": evidence, "journal": children(user, value, "journal")}


def edit(user, value, body):
    bounty = store.get(user, "bounties", value)
    updates = {key: body[key] for key in ("description", "difficulty", "target_date", "required_evidence_kinds") if key in body}
    if "title" in body:
        updates["title"] = store.title(body["title"])
    if body.get("difficulty") is not None:
        store.choice(body["difficulty"], DIFFICULTIES, "difficulty")
    for kind in body.get("required_evidence_kinds", []):
        store.choice(kind, KINDS, "evidence kind")
    if "points_reward" in body:
        reward = store.number(body["points_reward"], "Points reward")
        if not reward.is_integer():
            raise store.ArchiveError("Points reward must be a whole number.")
        updates["points_reward"] = int(reward)
    if bounty["type"] not in AUTOMATIC and not children(user, value, "objectives"):
        for key in ("progress_value", "progress_target"):
            if body.get(key) is not None:
                updates[key] = store.number(body[key], key)
    store.update(user, "bounties", value, lambda saved: {**saved, **updates})
    return read(user, value)


def change_status(user, value, operation):
    if operation == "complete":
        return complete(user, value)
    expected = {"pause": ("active",), "resume": ("paused", "not_started"), "abandon": STATUSES}
    if operation not in expected:
        raise store.ArchiveError("Unknown bounty status change.")
    status = {"pause": "paused", "resume": "active", "abandon": "abandoned"}[operation]
    def change(saved):
        if saved["status"] not in expected[operation]:
            raise store.ArchiveError("This bounty cannot make that status change.")
        return {**saved, "status": status,
            "started_at": saved.get("started_at") or (int(time.time()) if status == "active" else None)}
    return store.update(user, "bounties", value, change)


def add_child(user, value, kind, body):
    bounty = store.get(user, "bounties", value)
    fields = {"bounty_id": bounty["id"]}
    if kind == "objectives":
        objective_kind = store.choice(body.get("kind", "checkbox"), ("checkbox", "numeric", "achievement"), "objective kind")
        target = achievement(bounty.get("game_id"), body.get("target_achievement_id")) if objective_kind == "achievement" else None
        fields.update(title=store.title(body.get("title"), field="Objective title"), kind=objective_kind,
            done=False, progress_value=0, progress_target=store.number(body["progress_target"], "Target", minimum=1) if body.get("progress_target") is not None else None,
            target_achievement_provider=target["provider"] if target else None,
            target_achievement_external_id=target["external_id"] if target else None)
    elif kind == "evidence":
        evidence_kind = store.choice(body.get("kind"), KINDS, "evidence kind")
        media_id = body.get("media_item_id")
        if evidence_kind in ("screenshot", "clip", "document"):
            media_id = store.identifier(media_id)
            selected = next((item for item in store.media(bounty.get("game_id")) if item["id"] == media_id), None)
            if selected is None:
                raise store.ArchiveError("Media item not found for that game.", 404)
        text = body.get("text")
        url = body.get("url")
        if evidence_kind == "note":
            text = store.title(text, field="Evidence text", maximum=100_000)
        if evidence_kind == "link":
            url = store.title(url, field="Evidence URL", maximum=4000)
            parsed = urlsplit(url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise store.ArchiveError("Use an HTTP or HTTPS evidence URL.")
        fields.update(kind=evidence_kind, media_item_id=media_id, media_url=None, media_filename=None, text=text, url=url)
    elif kind == "journal":
        fields["text"] = store.title(body.get("text"), field="Journal text", maximum=100_000)
    else:
        raise store.ArchiveError("Unknown bounty detail.", 404)
    child = store.create(user, kind + "/" + bounty["id"], fields)
    return child, read(user, value)


def edit_objective(user, value, child_id, body):
    store.get(user, "bounties", value)
    kind = "objectives/" + store.identifier(value)
    objective = store.get(user, kind, child_id)
    updates = {}
    if "title" in body:
        updates["title"] = store.title(body["title"], field="Objective title")
    if objective["kind"] == "checkbox" and "done" in body:
        if not isinstance(body["done"], bool):
            raise store.ArchiveError("Objective completion must be true or false.")
        updates["done"] = body["done"]
    if objective["kind"] == "numeric":
        for key in ("progress_value", "progress_target"):
            if body.get(key) is not None:
                updates[key] = store.number(body[key], key)
    updated = store.update(user, kind, child_id, lambda saved: {**saved, **updates})
    return updated, read(user, value)


def proposal(user, all_games=None):
    candidates, mastery = [], []
    saved = store.records(user, "bounties")
    targeted = {(item.get("game_id"), item["type"]) for item in saved}
    cutoff = int(time.time()) - 14 * 86400
    for game in all_games if all_games is not None else store.games():
        total = game.get("achievement_total", 0)
        unlocked = game.get("achievement_unlocked", 0)
        if total and .5 <= unlocked / total < 1 and (game["id"], "mastery") not in targeted:
            mastery.append({"title": "Master " + game["title"], "type": "mastery", "points_reward": 200, "game_id": game["id"], "game_title": game["title"]})
        idle = game.get("last_played_at") or game.get("created_at") or 0
        if game["status"] in {"DROPPED", "ON_HOLD", "BACKLOG"} and idle <= cutoff and (game["id"], "completion") not in targeted:
            candidates.append({"title": "Finish " + game["title"], "type": "completion", "points_reward": 100, "game_id": game["id"], "game_title": game["title"]})
    pool = mastery or candidates
    return random.choice(pool) if pool else None


def maybe_propose(user, all_games):
    saved = [item for item in store.records(user, "bounties") if item.get("auto_generated")]
    if sum(item["status"] == "active" for item in saved) >= 2:
        return
    if saved and int(time.time()) - max(item["created_at"] for item in saved) < 7 * 86400:
        return
    picked = proposal(user, all_games)
    if picked:
        create(user, picked, auto_generated=True)
