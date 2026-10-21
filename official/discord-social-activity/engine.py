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


MATCHING_DEFAULTS = {"title_fallback": True, "platform_aliases": True, "skip_empty": True,
                     "small_multiplayer": True, "steam_platform": True,
                     "verified_only": False}


def game_key(game: dict, matching: dict | None = None) -> str:
    matching = matching or {"title_fallback": True}
    providers = game.get("provider_ids") or {}
    steam = providers.get("steam") if isinstance(providers, dict) else None
    if steam and not matching.get("title_fallback", True):
        return "steam:" + str(steam)
    # Copies the owner grouped as one game on their instance (Minecraft for Windows under
    # Minecraft) are matched by that game's main title, so they meet other people's copies.
    identity = game.get("identity")
    main_title = identity.get("main_title") if isinstance(identity, dict) else None
    title = main_title if isinstance(main_title, str) and main_title.strip() else game.get("title", "")
    title = re.sub(r"\s+", " ", str(title).strip()).casefold()
    if not title or len(title) > 500:
        raise SessionError("Use a game title of at most 500 characters.")
    if matching.get("title_fallback", True):
        title = "".join(char for char in unicodedata.normalize("NFKC", title) if char.isalnum())
    if not title:
        raise SessionError("A title needs at least one letter or number.")
    return "title:" + title


PLATFORM_ALIASES = {"windows": "pc", "windows pc": "pc", "steam": "pc", "win": "pc",
                    "ps5": "playstation 5", "ps4": "playstation 4", "switch": "nintendo switch",
                    "macos": "mac", "os x": "mac", "web": "browser"}


def platform_key(value: str, *, aliases: bool = True) -> str:
    key = value.strip().casefold()
    if aliases:
        key = PLATFORM_ALIASES.get(key, key)
    return key


def fresh_room(context: dict, now: int) -> dict:
    return {"revision": 0, "host_id": context["actor_id"], "created_at": now,
            "expires_at": now + context["retention_hours"] * 3600,
            "mode": "strict", "participants": {}, "shortlist": [], "selected": None,
            "history": [], "round": 0, "phase": "lobby", "player_limits": [],
            "matching": dict(MATCHING_DEFAULTS)}


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


def has_games(person: dict, verified_only: bool = False) -> bool:
    """With the verified-only room policy, self-reported entries do not count as games."""
    return (bool(person["manual"]) and not verified_only) or any(automatic_game(game) for game in person["library"])


def _room_game_reference(game: dict) -> dict:
    """Keep the matching title with room confirmations, without instance-local group IDs."""
    reference = {"title": game["title"], "provider_ids": game.get("provider_ids", {})}
    identity = game.get("identity")
    if isinstance(identity, dict) and isinstance(identity.get("main_title"), str):
        reference["identity"] = {"main_title": identity["main_title"]}
    return reference


def _contributions(person: dict, matching: dict) -> dict[str, dict]:
    result = {}
    platforms = {game_key(item, matching): item["platform"]
                 for item in person.get("platform_overrides", [])}
    manual_keys = {game_key(game, matching) for game in person["manual"]}
    for game in person["library"]:
        key = game_key(game, matching)
        if not automatic_game(game) and key not in manual_keys:
            continue
        saved = game.get("play_compatibility")
        platform = platforms.get(key) or game.get("platform")
        inferred_platform = False
        steam = (game.get("provider_ids") or {}).get("steam")
        if not platform and matching.get("steam_platform", True) and re.fullmatch(r"[0-9]{1,12}", str(steam or "")):
            platform, inferred_platform = "PC", True
        compatibility = None
        if (isinstance(saved, dict)
                and type(saved.get("min_players")) is int and type(saved.get("max_players")) is int
                and 1 <= saved["min_players"] <= saved["max_players"] <= 32):
            compatibility = {**saved, "platform": platform, "genres": game.get("tags") or []}
        result[key] = {**game, "platform": platform,
                       "platform_provenance": "inferred_steam" if inferred_platform else "reported",
                       "key": key, "owned": game.get("owned") is True,
                       "compatibility": compatibility,
                       "available": game.get("source_state") == "connected"}
    for game in person["manual"]:
        key = game_key(game, matching)
        imported = result.get(key)
        if imported:
            # A manual compatibility annotation never upgrades a revoked imported claim.
            result[key] = {**imported, "compatibility": game,
                           "owned": imported["owned"] or (game["owned"] and not matching["verified_only"]),
                           "available": imported["available"]}
        elif not matching["verified_only"]:
            result[key] = {**game, "compatibility": game, "available": True}
    return result


def evaluate(room: dict, *, now: int) -> dict:
    matching = {**MATCHING_DEFAULTS, **room.get("matching", {})}
    people = {pid: person for pid, person in room["participants"].items() if person["active"]
              and (not matching["skip_empty"] or has_games(person, matching["verified_only"]))}
    count = len(people)
    contributions = {pid: _contributions(person, matching) for pid, person in people.items()}
    shared_limits = {game_key(item, matching): item for item in room.get("player_limits", [])}
    approvals = {game_key(item, matching): item for item in room.get("group_approvals", [])}
    keys = sorted({key for games in contributions.values() for key in games})
    eligible, excluded = [], []
    for key in keys:
        variants = [games[key] for games in contributions.values() if key in games]
        display = variants[0]
        approval = approvals.get(key)
        approved = approval is not None and approval["players"] == count
        small_group = matching["small_multiplayer"] and 0 < count <= 2 and any(
            detected_multiplayer(item) or isinstance(item.get("play_compatibility"), dict)
            for item in variants)
        limits = shared_limits.get(key)
        if limits is None:
            # Existing saved/manual knowledge can supply missing counts for other owners.
            # Ownership, platform/crossplay and personal rules remain participant-specific.
            limits = next(({"min_players": games[key]["compatibility"]["min_players"],
                            "max_players": games[key]["compatibility"]["max_players"],
                            "confirmed_by": pid}
                           for pid, games in contributions.items()
                           if key in games and games[key].get("compatibility")), None)
        limits_source = ("room" if shared_limits.get(key) is not None else
                         "unknown" if limits is None else
                         "provider" if (contributions[limits["confirmed_by"]][key]["compatibility"] or {}).get("source") == "provider"
                         else "saved")
        # Different providers or owners can report contradictory ranges. Each participant's own
        # range still applies (the narrowest wins), but the disagreement is surfaced, never hidden.
        ranges = {(games[key]["compatibility"]["min_players"], games[key]["compatibility"]["max_players"])
                  for games in contributions.values() if key in games and games[key].get("compatibility")}
        metadata_conflict = shared_limits.get(key) is None and len(ranges) > 1
        complete_limits = limits is not None and all(
            limits[field] is not None for field in ("min_players", "max_players"))
        # A partial confirmation is deliberately scoped to the approved party size.
        # Do not silently replace its unknown bound with the small-group inference.
        if limits is not None and not complete_limits:
            small_group = False
        reasons, access, owners, score = [], [], 0, 0
        if limits and ((limits["min_players"] is not None and count < limits["min_players"])
                       or (limits["max_players"] is not None and count > limits["max_players"])):
            reasons.append("Known room player-count rule")
        missing_platforms = [pid for pid, games in contributions.items()
                             if key in games and not games[key].get("platform")]
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
            method = "self_reported"
            if compatibility is None and (complete_limits or approved or small_group):
                saved = game.get("play_compatibility") or {}
                method = "self_reported" if limits else "current_group" if approved else "detected_multiplayer"
                compatibility = {"min_players": limits["min_players"] if limits else None,
                                 "max_players": limits["max_players"] if limits else None,
                                 "platform": game.get("platform"),
                                 "genres": game.get("tags") or [],
                                 "duration_minutes": saved.get("duration_minutes"),
                                 "crossplay": saved.get("crossplay", False)}
            if compatibility is None:
                reasons.append("Confirm supported player count once for this room")
                continue
            explicit = shared_limits.get(key)
            if explicit is not None and compatibility.get("source") == "provider":
                # A human-confirmed room range outranks automatic provider data.
                compatibility = {**compatibility, **{field: explicit[field] for field in (
                    "min_players", "max_players") if explicit[field] is not None}}
                method = "self_reported"
            elif compatibility.get("source") == "provider":
                method = "provider"
            platform = compatibility["platform"]
            if not platform:
                reasons.append(f"{label}: confirm your platform")
                continue
            normalized = platform_key(platform, aliases=matching["platform_aliases"])
            platforms.add(normalized)
            crossplay = crossplay and compatibility.get("crossplay", False)
            if pref["platform"] != "Any" and platform_key(pref["platform"], aliases=matching["platform_aliases"]) != normalized:
                reasons.append(f"{label}: platform rule")
            if ((compatibility["min_players"] is not None and count < compatibility["min_players"])
                    or (compatibility["max_players"] is not None and count > compatibility["max_players"])):
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
                           "platform": platform, "compatibility": method,
                           "min_players": compatibility["min_players"],
                           "max_players": compatibility["max_players"],
                           "platform_provenance": game.get("platform_provenance", "reported"),
                           "retrieved_at": game.get("retrieved_at"),
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
        candidate = {"key": key, **_room_game_reference(display), "access": access,
                     "needs_player_limits": not complete_limits,
                     "limits_source": limits_source, "metadata_conflict": metadata_conflict,
                     "requires_player_limits": not complete_limits and not approved and not small_group,
                     "group_approval": {"players": count, "confirmed_by": approval["confirmed_by"]} if approved else None,
                     "missing_platforms": missing_platforms,
                     "player_limits": {field: limits[field] for field in (
                         "min_players", "max_players", "confirmed_by")} if limits else None,
                     "score": score + owners, "reasons": ["Everyone owns it or consented to considering a purchase" if purchase_required else "Everyone has access",
                     "Price unknown; price filters are paused" if purchase_required else "No purchase required",
                     "Known player limits checked" if complete_limits else "Approved for this group; exact limits unknown" if approved else "Multiplayer accepted for 1–2 players; exact limits unknown" if small_group else "Player limits need confirmation",
                     "Personal hard rules satisfied"]
                     + (["Sources disagree on player limits; the narrowest range for each person applies"]
                        if metadata_conflict else []), "excluded_reasons": reasons,
                     "price_status": "unavailable" if purchase_required else "not_required", "evaluated_at": now,
                     "match_provenance": "provider_id" if key.startswith("steam:") else "title_match"}
        candidate["excluded_reasons"] = list(dict.fromkeys(reasons))
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
                              "last_seen_at": person["last_seen_at"], "ready": has_games(person, room["matching"]["verified_only"]),
                              "spectating": room["matching"]["skip_empty"] and not has_games(person, room["matching"]["verified_only"]),
                              "vote_cast": person["vote"] is not None}
                             for pid, person in room["participants"].items()],
            "me": {**room["participants"][actor_id], "id": actor_id},
            "pool": pool, "shortlist": shortlist,
            "selected": room["selected"] if room["selected"] and room["selected"]["key"] in valid else None,
            "history": room["history"][-20:]}


def _approve_current_group(room: dict, candidates: list[dict], count: int,
                           actor_id: str, now: int) -> None:
    keys = {candidate["key"] for candidate in candidates}
    approvals = [item for item in room.get("group_approvals", [])
                 if game_key(item, room["matching"]) not in keys]
    if len(approvals) + len(candidates) > 500:
        raise SessionError("This room has reached its group approval capacity.")
    for candidate in candidates:
        approvals.append({**_room_game_reference(candidate),
            "players": count, "confirmed_by": actor_id, "confirmed_at": now})
    room["group_approvals"] = approvals


def transition(saved: dict | None, values: dict, context: dict, *, now: int | None = None) -> tuple[dict, dict]:
    now = int(time.time()) if now is None else now
    actor_id = context["actor_id"]
    room = copy.deepcopy(saved) if saved and saved["expires_at"] > now else fresh_room(context, now)
    room["matching"] = {**MATCHING_DEFAULTS, **room.get("matching", {})}
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
    elif operation == "player-limits":
        minimum, maximum = values.get("min_players"), values.get("max_players")
        if ((minimum is None and maximum is None)
                or any(bound is not None and (type(bound) is not int or not 1 <= bound <= 32)
                       for bound in (minimum, maximum))
                or (minimum is not None and maximum is not None and minimum > maximum)):
            raise SessionError("Confirm a supported player range from 1 to 32; leave unknown limits blank.")
        pool = evaluate(room, now=now)
        candidate = next((game for game in pool["eligible"] + pool["excluded"]
                          if game["key"] == values.get("key")), None)
        if candidate is None:
            raise SessionError("Choose a game already present in this room.")
        platform = values.get("platform")
        if platform is not None:
            if not isinstance(platform, str) or not 1 <= len(platform.strip()) <= 80:
                raise SessionError("Choose a valid platform for your own game.")
            if candidate["key"] not in _contributions(person, room["matching"]):
                raise SessionError("Confirm a platform only for your own game.")
            platforms = [item for item in person.get("platform_overrides", [])
                         if game_key(item, room["matching"]) != candidate["key"]]
            if len(platforms) >= 500:
                raise SessionError("This room has reached your saved platform capacity.")
            platforms.append({**_room_game_reference(candidate),
                              "platform": platform.strip()})
            person["platform_overrides"] = platforms
        limits = [item for item in room.get("player_limits", [])
                  if game_key(item, room["matching"]) != candidate["key"]]
        if len(limits) >= 500:
            raise SessionError("This room has reached its saved player-limit capacity.")
        previous = candidate["player_limits"]
        same_counts = (previous is not None and previous["min_players"] == minimum
                       and previous["max_players"] == maximum)
        limits.append({**_room_game_reference(candidate),
                       "min_players": minimum, "max_players": maximum,
                       "confirmed_by": previous["confirmed_by"] if same_counts else actor_id,
                       "confirmed_at": now})
        room["player_limits"] = limits
        if minimum is None or maximum is None:
            _approve_current_group(room, [candidate], pool["player_count"], actor_id, now)
    elif operation == "approve-group":
        keys = values.get("keys")
        if (not isinstance(keys, list) or not 1 <= len(keys) <= 100
                or any(not isinstance(key, str) for key in keys) or len(set(keys)) != len(keys)):
            raise SessionError("Choose up to 100 different games to approve.")
        pool = evaluate(room, now=now)
        candidates = {game["key"]: game for game in pool["eligible"] + pool["excluded"]}
        if set(keys) - candidates.keys() or pool["player_count"] < 1:
            raise SessionError("Choose games already present in this active room.")
        if values.get("platform") is not None:
            platform = values["platform"]
            if len(keys) != 1 or not isinstance(platform, str) or not 1 <= len(platform.strip()) <= 80:
                raise SessionError("Choose a valid platform for one of your own games.")
            candidate = candidates[keys[0]]
            if keys[0] not in _contributions(person, room["matching"]):
                raise SessionError("Confirm a platform only for your own game.")
            overrides = [item for item in person.get("platform_overrides", [])
                         if game_key(item, room["matching"]) != keys[0]]
            if len(overrides) >= 500:
                raise SessionError("This room has reached your saved platform capacity.")
            person["platform_overrides"] = overrides + [{**_room_game_reference(candidate),
                "platform": platform.strip()}]
        _approve_current_group(room, [candidates[key] for key in keys],
                               pool["player_count"], actor_id, now)
    elif operation == "mode":
        if values.get("mode") not in {"strict", "balanced", "discovery"}:
            raise SessionError("Choose strict, balanced or discovery.")
        room["mode"], room["shortlist"], room["selected"] = values["mode"], [], None
        room["phase"] = "lobby"
    elif operation == "matching":
        options = values.get("matching")
        if (not isinstance(options, dict) or set(options) - MATCHING_DEFAULTS.keys()
                or not {"title_fallback", "platform_aliases", "skip_empty"}.issubset(options)
                or any(type(value) is not bool for value in options.values())):
            raise SessionError("Choose the supported room matching options.")
        options = {**room["matching"], **options}
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
    elif operation == "forget":
        if values.get("confirmed") is not True:
            raise SessionError("Confirm that you want to delete your saved Activity data.")
        del participants[actor_id]
        for field in ("player_limits", "group_approvals"):
            room[field] = [entry for entry in room.get(field, []) if entry.get("confirmed_by") != actor_id]
        # Cached results embed names, avatars and library contributions.
        room["shortlist"], room["selected"], room["history"], room["phase"] = [], None, [], "lobby"
        for member in participants.values():
            member["vote"] = None
        if room["host_id"] == actor_id:
            room["host_id"] = next((pid for pid, member in participants.items() if member["active"]),
                                   next(iter(participants), None))
        room["revision"] += 1
        return room, {"forgotten": True}
    elif operation == "leave":
        person["active"] = False
        person["library"], person["manual"], person["vetoes"], person["vote"] = [], [], [], None
        person["platform_overrides"] = []
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
