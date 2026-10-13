"""Game-night state transitions and hard-rule eligibility, independent of the host."""

from __future__ import annotations

import copy
import hashlib
import re
import secrets
import time
import unicodedata
from typing import Any


class SessionError(ValueError):
    """Safe, actionable participant errors."""


def game_key(game: dict, matching: dict | None = None) -> str:
    matching = matching or {"title_fallback": True}
    providers = game.get("provider_ids") or {}
    steam = providers.get("steam") if isinstance(providers, dict) else None
    if steam and not matching.get("title_fallback", True):
        return "steam:" + str(steam)
    title = re.sub(r"\s+", " ", str(game.get("title", "")).strip()).casefold()
    if not title or len(title) > 500:
        raise SessionError("Use a game title of at most 500 characters.")
    if matching.get("title_fallback", True):
        title = "".join(char for char in unicodedata.normalize("NFKC", title) if char.isalnum())
    if not title:
        raise SessionError("A title needs at least one letter or number.")
    return "title:" + title


def platform_key(value: str, *, aliases: bool = True) -> str:
    key = value.strip().casefold()
    if aliases:
        key = {"windows": "pc", "windows pc": "pc", "steam": "pc", "win": "pc",
               "ps5": "playstation 5", "ps4": "playstation 4", "switch": "nintendo switch",
               "macos": "mac", "os x": "mac", "web": "browser"}.get(key, key)
    return key


def fresh_room(context: dict, now: int) -> dict:
    return {"revision": 0, "host_id": context["actor_id"], "created_at": now,
            "expires_at": now + context["retention_hours"] * 3600,
            "mode": "strict", "participants": {}, "shortlist": [], "selected": None,
            "history": [], "round": 0, "phase": "lobby",
            "matching": {"title_fallback": True, "platform_aliases": True, "skip_empty": True}}


def manual_game(value: Any) -> dict:
    if not isinstance(value, dict) or set(value) - {
        "title", "platform", "min_players", "max_players", "duration_minutes", "genres",
        "owned", "crossplay", "provider_ids",
    }:
        raise SessionError("Use the supported manual-game fields.")
    if (not isinstance(value.get("title"), str) or not value["title"].strip()
            or len(value["title"].strip()) > 200):
        raise SessionError("A manual game needs a title of at most 200 characters.")
    platform = value.get("platform")
    minimum, maximum = value.get("min_players"), value.get("max_players")
    if (not isinstance(platform, str) or not 1 <= len(platform) <= 80
            or type(minimum) is not int or type(maximum) is not int
            or not 1 <= minimum <= maximum <= 32 or type(value.get("owned")) is not bool
            or type(value.get("crossplay", False)) is not bool):
        raise SessionError("Confirm access, platform and a valid supported player range.")
    duration = value.get("duration_minutes")
    if duration is not None and (type(duration) is not int or not 1 <= duration <= 1440):
        raise SessionError("Play time must be 1–1440 minutes, or unknown.")
    genres = value.get("genres", [])
    if not isinstance(genres, list) or len(genres) > 10 or any(not isinstance(g, str) or len(g) > 50 for g in genres):
        raise SessionError("Choose at most ten short genre labels.")
    result = {**value, "title": value["title"].strip(), "genres": genres,
              "provenance": "self_reported", "retrieved_at": int(time.time())}
    providers = value.get("provider_ids", {})
    if not isinstance(providers, dict) or set(providers) - {"steam"}:
        raise SessionError("Manual provider matching currently supports a Steam app ID.")
    if providers and not re.fullmatch(r"[0-9]{1,12}", str(providers.get("steam", ""))):
        raise SessionError("Enter a valid Steam app ID.")
    result["key"] = game_key(result)
    return result


def preferences(value: Any) -> dict:
    defaults = {"platform": "Any", "max_minutes": None, "genres": [], "avoid_genres": [],
                "budget": 0, "currency": "USD", "minimum_discount": 0, "allow_purchase": False,
                "owned_only": True}
    if not isinstance(value, dict) or set(value) - defaults.keys():
        raise SessionError("Use the supported preference fields.")
    result = {**defaults, **value}
    for key in ("budget", "minimum_discount"):
        number = result[key]
        if type(number) not in {int, float} or not 0 <= number <= (100 if key == "minimum_discount" else 10000):
            raise SessionError("Enter a valid budget and discount percentage.")
    if not re.fullmatch(r"[A-Z]{3}", str(result["currency"])):
        raise SessionError("Use a three-letter currency code.")
    if not isinstance(result["platform"], str) or len(result["platform"]) > 80:
        raise SessionError("Choose a valid platform.")
    if result["max_minutes"] is not None and (type(result["max_minutes"]) is not int or not 1 <= result["max_minutes"] <= 1440):
        raise SessionError("Session length must be 1–1440 minutes.")
    for key in ("allow_purchase", "owned_only"):
        if type(result[key]) is not bool:
            raise SessionError("Confirm your own purchase and ownership preferences.")
    for key in ("genres", "avoid_genres"):
        if (not isinstance(result[key], list) or len(result[key]) > 10
                or any(not isinstance(g, str) or len(g) > 50 for g in result[key])):
            raise SessionError("Choose at most ten short genre labels.")
    return result


def detected_multiplayer(game: dict) -> bool:
    labels = [label for field in ("features", "tags")
              if isinstance(game.get(field), list) for label in game[field]]
    return any(isinstance(label, str) and re.search(
        r"multiplayer|coop|onlinepvp|lanpvp|mmo", re.sub(r"[^a-z0-9]", "", label.casefold())
    ) for label in labels)


def automatic_game(game: dict) -> bool:
    return game.get("owned") is True and (
        detected_multiplayer(game) or isinstance(game.get("play_compatibility"), dict)
    )


def has_games(person: dict) -> bool:
    return bool(person["manual"]) or any(automatic_game(game) for game in person["library"])


def _contributions(person: dict, matching: dict) -> dict[str, dict]:
    result = {}
    manual_keys = {game_key(game, matching) for game in person["manual"]}
    for game in person["library"]:
        key = game_key(game, matching)
        if not automatic_game(game) and key not in manual_keys:
            continue
        saved = game.get("play_compatibility")
        compatibility = None
        if (isinstance(saved, dict) and isinstance(game.get("platform"), str)
                and type(saved.get("min_players")) is int and type(saved.get("max_players")) is int
                and 1 <= saved["min_players"] <= saved["max_players"] <= 32):
            compatibility = {**saved, "platform": game["platform"], "genres": game.get("tags", [])}
        result[key] = {**game, "key": key, "owned": game.get("owned") is True,
                       "compatibility": compatibility,
                       "available": game.get("source_state") == "connected"}
    for game in person["manual"]:
        key = game_key(game, matching)
        imported = result.get(key)
        if imported:
            # A manual compatibility annotation never upgrades a revoked imported claim.
            result[key] = {**imported, "compatibility": game,
                           "owned": imported["owned"] or game["owned"],
                           "available": imported["available"]}
        else:
            result[key] = {**game, "compatibility": game, "available": True}
    return result


def evaluate(room: dict, *, now: int) -> dict:
    matching = room.get("matching", {"title_fallback": True, "platform_aliases": True, "skip_empty": True})
    people = {pid: person for pid, person in room["participants"].items() if person["active"]
              and (not matching["skip_empty"] or has_games(person))}
    count = len(people)
    contributions = {pid: _contributions(person, matching) for pid, person in people.items()}
    keys = sorted({key for games in contributions.values() for key in games})
    eligible, excluded = [], []
    for key in keys:
        variants = [games[key] for games in contributions.values() if key in games]
        display = variants[0]
        reasons, access, owners, score = [], [], 0, 0
        platforms, crossplay = set(), True
        for pid, person in people.items():
            game = contributions[pid].get(key)
            pref = person["preferences"]
            label = person["display_name"]
            if key in person["vetoes"]:
                reasons.append(f"{label} vetoed this game")
                continue
            if not game or not game["available"]:
                reasons.append(f"{label}: access unavailable or instance offline")
                continue
            owned = game["owned"]
            owners += int(owned)
            if not owned:
                # Price filters are paused until a pricing provider is available.
                # Consent still belongs to this participant and never authorizes a purchase.
                if pref["owned_only"] or not pref["allow_purchase"]:
                    reasons.append(f"{label}: ownership or purchase-consent rule")
                    continue
            compatibility = game.get("compatibility")
            if not compatibility:
                reasons.append(f"{label}: confirm group compatibility and player count")
                continue
            platform = compatibility["platform"]
            platforms.add(platform_key(platform, aliases=matching["platform_aliases"]))
            crossplay = crossplay and compatibility.get("crossplay", False)
            if pref["platform"] != "Any" and platform_key(pref["platform"], aliases=matching["platform_aliases"]) != platform_key(platform, aliases=matching["platform_aliases"]):
                reasons.append(f"{label}: platform rule")
            if not compatibility["min_players"] <= count <= compatibility["max_players"]:
                reasons.append(f"{label}: player-count rule")
            duration = compatibility.get("duration_minutes")
            if pref["max_minutes"] and (duration is None or duration > pref["max_minutes"]):
                reasons.append(f"{label}: session length unavailable or too long")
            genres = {g.casefold() for g in compatibility["genres"]}
            if genres.intersection(g.casefold() for g in pref["avoid_genres"]):
                reasons.append(f"{label}: excluded genre")
            score += 2 * len(genres.intersection(g.casefold() for g in pref["genres"]))
            access.append({"participant_id": pid, "name": label, "owned": owned,
                           "avatar_path": person.get("avatar_path"),
                           "provenance": game.get("ownership_provenance", "self_reported"),
                           "platform": platform, "compatibility": "self_reported",
                           "cost": 0 if owned else None, "purchase_required": not owned})
        if len(platforms) > 1 and not crossplay:
            reasons.append("Cross-platform play was not confirmed by everyone")
        if count == 0:
            reasons.append("No active participants")
        if room["mode"] == "strict" and owners != count:
            reasons.append("Strict requires ownership for everyone")
        elif room["mode"] == "balanced" and owners < max(1, (count + 1) // 2):
            reasons.append("Balanced requires ownership for at least half the group")
        elif room["mode"] == "discovery" and owners < 1:
            reasons.append("Discovery needs at least one confirmed owner")
        purchase_required = any(item["purchase_required"] for item in access)
        candidate = {"key": key, "title": display["title"], "access": access,
                     "provider_ids": display.get("provider_ids", {}),
                     "score": score + owners, "reasons": ["Everyone owns it or consented to considering a purchase" if purchase_required else "Everyone has access",
                     "Price unknown; price filters are paused" if purchase_required else "No purchase required",
                     "Player count confirmed", "Personal hard rules satisfied"], "excluded_reasons": reasons,
                     "price_status": "unavailable" if purchase_required else "not_required", "evaluated_at": now,
                     "match_provenance": "provider_id" if key.startswith("steam:") else "title_match"}
        if not reasons:
            eligible.append(candidate)
        else:
            excluded.append(candidate)
    eligible.sort(key=lambda item: (-item["score"], item["title"].casefold()))
    return {"eligible": eligible, "excluded": excluded, "player_count": count}


def _public(room: dict, actor_id: str, now: int) -> dict:
    pool = evaluate(room, now=now)
    valid = {game["key"] for game in pool["eligible"]}
    shortlist = []
    for candidate in room["shortlist"]:
        if candidate["key"] not in valid:
            continue
        voters = [pid for pid, person in room["participants"].items()
                  if person["active"] and person["vote"] == candidate["key"]]
        shortlist.append({**candidate, "votes": len(voters)})
    return {"revision": room["revision"], "mode": room["mode"], "phase": room["phase"],
            "matching": room["matching"],
            "host_id": room["host_id"], "round": room["round"], "expires_at": room["expires_at"],
            "participants": [{"id": pid, "display_name": person["display_name"],
                              "avatar_path": person.get("avatar_path"),
                              "active": person["active"], "connected": person["connected"],
                              "last_seen_at": person["last_seen_at"], "ready": has_games(person),
                              "spectating": room["matching"]["skip_empty"] and not has_games(person),
                              "vote_cast": person["vote"] is not None}
                             for pid, person in room["participants"].items()],
            "me": {**room["participants"][actor_id], "id": actor_id},
            "pool": pool, "shortlist": shortlist,
            "selected": room["selected"] if room["selected"] and room["selected"]["key"] in valid else None,
            "history": room["history"][-20:]}


def transition(saved: dict | None, values: dict, context: dict, *, now: int | None = None) -> tuple[dict, dict]:
    now = int(time.time()) if now is None else now
    actor_id = context["actor_id"]
    room = copy.deepcopy(saved) if saved and saved["expires_at"] > now else fresh_room(context, now)
    room.setdefault("matching", {"title_fallback": True, "platform_aliases": True, "skip_empty": True})
    participants = room["participants"]
    # Preserve vetoes and reconnect inputs from rooms created before soft title matching.
    for member in participants.values():
        aliases = {}
        for game in member["library"] + member["manual"]:
            old_key = game.get("key") or game_key(game, {"title_fallback": False})
            new_key = game_key(game, room["matching"])
            aliases[old_key] = new_key
            if "key" in game:
                game["key"] = new_key
        member["vetoes"] = [aliases.get(key, key) for key in member["vetoes"]]
        member["vote"] = aliases.get(member["vote"], member["vote"])
    if actor_id not in participants:
        if len(participants) >= 32:
            raise SessionError("This game night already has 32 participants.")
        participants[actor_id] = {"display_name": context["display_name"], "last_seen_at": now,
            "active": True, "connected": context["connected"], "library": [], "manual": [],
            "preferences": preferences({}), "vetoes": [], "vote": None}
    person = participants[actor_id]
    person.update({"display_name": context["display_name"], "last_seen_at": now,
                   "avatar_path": context.get("avatar_path"),
                   "connected": context["connected"], "library": context["library"]})
    for member in participants.values():
        if member["last_seen_at"] + 90 < now:
            member["active"] = False
        for game in member["library"]:
            game["source_state"] = context["source_states"].get(game["source_id"], "offline")
    operation = values.get("operation", "snapshot")
    if operation != "leave":
        person["active"] = True
    if room["host_id"] not in participants or not participants[room["host_id"]]["active"]:
        room["host_id"] = next((pid for pid, member in participants.items() if member["active"]), actor_id)
    if operation in {"mode", "matching", "roll", "finalize", "transfer"} and actor_id != room["host_id"]:
        raise SessionError("Only the current host can change the mode or selection round.")
    if operation == "preferences":
        person["preferences"] = preferences(values.get("preferences"))
        person["vote"] = None
    elif operation == "manual":
        if not context["allow_guests"] and not context["connected"]:
            raise SessionError("Connect an instance first; the owner has disabled guest participation.")
        game = manual_game(values.get("game"))
        game["key"] = game_key(game, room["matching"])
        person["manual"] = [item for item in person["manual"] if item["key"] != game["key"]]
        if len(person["manual"]) >= 100:
            raise SessionError("Remove a manual entry before adding another.")
        person["manual"].append(game)
        person["vote"] = None
    elif operation == "remove-manual":
        person["manual"] = [game for game in person["manual"] if game["key"] != values.get("key")]
    elif operation == "mode":
        if values.get("mode") not in {"strict", "balanced", "discovery"}:
            raise SessionError("Choose strict, balanced or discovery.")
        room["mode"], room["shortlist"], room["selected"] = values["mode"], [], None
        room["phase"] = "lobby"
    elif operation == "matching":
        options = values.get("matching")
        if not isinstance(options, dict) or set(options) != set(room["matching"]) or any(type(value) is not bool for value in options.values()):
            raise SessionError("Choose the supported room matching options.")
        old_matching = room["matching"]
        for member in participants.values():
            aliases = {game_key(game, old_matching): game_key(game, options)
                       for game in member["library"] + member["manual"]}
            member["vetoes"] = [aliases.get(key, key) for key in member["vetoes"]]
            member["vote"] = None
        room["matching"], room["shortlist"], room["selected"], room["phase"] = options, [], None, "lobby"
    elif operation == "veto":
        key = values.get("key")
        if not isinstance(key, str) or len(key) > 220:
            raise SessionError("Choose a valid game to veto.")
        person["vetoes"] = list(set(person["vetoes"]) | {key})[:200]
        person["vote"] = None
    elif operation == "clear-veto":
        person["vetoes"] = [key for key in person["vetoes"] if key != values.get("key")]
    elif operation == "vote":
        key = values.get("key")
        eligible = {game["key"] for game in evaluate(room, now=now)["eligible"]}
        if key not in {game["key"] for game in room["shortlist"]} or key not in eligible:
            raise SessionError("Vote for a currently eligible shortlisted game.")
        person["vote"] = key
    elif operation == "roll":
        pool = evaluate(room, now=now)["eligible"]
        if not pool:
            raise SessionError("No game meets everyone's rules. Review the exclusion reasons together.")
        if values.get("reroll") is True and room["selected"] and len(pool) > 1:
            pool = [game for game in pool if game["key"] != room["selected"]["key"]]
        chosen = []
        while pool and len(chosen) < 3:
            # Weighted without replacement, preferences affect rank but never hard eligibility.
            weights = [max(1, game["score"]) for game in pool]
            ticket = secrets.randbelow(sum(weights))
            index = 0
            while ticket >= weights[index]:
                ticket -= weights[index]
                index += 1
            chosen.append(pool.pop(index))
        room["shortlist"], room["selected"], room["phase"] = chosen, None, "voting"
        room["round"] += 1
        for member in participants.values():
            member["vote"] = None
        room["history"].append({"round": room["round"], "event": "shortlisted", "at": now,
                                 "titles": [game["title"] for game in chosen]})
    elif operation == "finalize":
        eligible = {game["key"]: game for game in evaluate(room, now=now)["eligible"]}
        finalists = [game for game in room["shortlist"] if game["key"] in eligible]
        if not finalists:
            raise SessionError("The shortlist is no longer eligible; start another round.")
        tally = {game["key"]: sum(1 for member in participants.values()
                                  if member["active"] and member["vote"] == game["key"])
                 for game in finalists}
        best = max(tally.values())
        winners = [game for game in finalists if tally[game["key"]] == best]
        winner = secrets.choice(winners)
        room["selected"], room["phase"] = eligible[winner["key"]], "selected"
        room["history"].append({"round": room["round"], "event": "selected", "at": now,
                                 "title": winner["title"], "votes": best, "tie_count": len(winners)})
    elif operation == "leave":
        person["active"] = False
        person["library"], person["manual"], person["vetoes"], person["vote"] = [], [], [], None
    elif operation == "transfer":
        target = values.get("participant_id")
        if values.get("confirmed") is not True:
            raise SessionError("Confirm the participant before transferring host control.")
        if target not in participants or not participants[target]["active"]:
            raise SessionError("Transfer to an active participant.")
        room["host_id"] = target
    elif operation != "snapshot":
        raise SessionError("Unsupported game-night action.")
    room["revision"] += 1
    room["history"] = room["history"][-20:]
    return room, _public(room, actor_id, now)
