"""One supervised worker; HTTP, import and durable state stay at public boundaries."""

from __future__ import annotations

import json
import re
import time
from typing import Any
from urllib.parse import quote, urlencode, urlsplit
from uuid import uuid4

from sdk.plugin_protocol import request

PAGE_SIZE = 100


class SyncError(ValueError):
    """Safe, actionable error; never contains response bodies, URLs or tokens."""


def load(key: str, default: Any = None) -> Any:
    raw = request("storage.get", "plugin.storage", {"key": key}).get("value")
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        raise SyncError(
            "Plugin state is damaged. Disable the plugin and restore its storage backup."
        ) from None


def store(key: str, value: Any) -> None:
    request("storage.put", "plugin.storage", {"key": key, "value": json.dumps(value)})


def server_url(value: Any) -> str:
    if not isinstance(value, str):
        raise SyncError("Configure a Jellyfin server URL.")
    try:
        parts = urlsplit(value.strip())
        _ = parts.port
    except ValueError:
        raise SyncError("The Jellyfin server port is invalid.") from None
    if (
        parts.scheme not in {"http", "https"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or any(c.isspace() for c in value)
        or '"' in value
        or "\\" in value
    ):
        raise SyncError(
            "Use an HTTP(S) server URL without credentials, query or fragment."
        )
    return value.strip().rstrip("/")


def actor(values: dict[str, Any], *, admin: bool = False) -> str:
    context = values.get("_plugin_context", {})
    user = context.get("user_id")
    if not isinstance(user, str) or (admin and context.get("is_admin") is not True):
        raise SyncError(
            "Administrator access is required."
            if admin
            else "Sign in to link your account."
        )
    from uuid import UUID

    return str(UUID(user))


def configuration() -> dict[str, Any]:
    config = load("master/config.json", {})
    config["server_url"] = server_url(config.get("server_url", ""))
    if not config.get("libraries"):
        raise SyncError("Test the server and map at least one Jellyfin library.")
    return config


def save_master(values: dict[str, Any]) -> dict[str, Any]:
    actor(values, admin=True)
    server = server_url(values.get("server_url", ""))
    interval = values.get("sync_interval_minutes", 15)
    if (
        isinstance(interval, bool)
        or not isinstance(interval, int)
        or not 5 <= interval <= 1440
    ):
        raise SyncError("The sync interval must be between 5 and 1440 minutes.")
    old = load("master/config.json", {})
    config = {**old, "server_url": server, "sync_interval_minutes": interval}
    if old.get("server_url") != server:
        config.update(
            libraries=[],
            users=[],
            mappings={},
            identity_access={},
            connection="untested",
        )
    store("master/config.json", config)
    if values.get("api_key"):
        save_token(values)
    return {
        "ok": True,
        "message": "Installation server saved. Test connection to discover libraries and users.",
    }


def save_token(values: dict[str, Any]) -> dict[str, Any]:
    actor(values, admin=True)
    token = values.get("api_key")
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._-]{8,512}", token):
        raise SyncError("Enter a valid Jellyfin server API key.")
    server = server_url(load("master/config.json", {}).get("server_url", ""))
    store("secrets/master_token", {"token": token, "server": server})
    request("storage.delete", "plugin.storage", {"key": "secrets/api_key"})
    return {
        "ok": True,
        "message": "Server credential saved securely. It will never be returned.",
    }


def stored_token(config: dict[str, Any]) -> str:
    secret = load("secrets/master_token", {})
    if secret.get("server") != config["server_url"]:
        raise SyncError(
            "Server changed or no master credential exists. An administrator must save a server credential."
        )
    token = secret.get("token")
    if not isinstance(token, str) or not re.fullmatch(r"[A-Za-z0-9._-]{8,512}", token):
        raise SyncError("Save a valid server credential.")
    return token


def jf(config: dict[str, Any], path: str, token: str) -> Any:
    # The public host broker enforces grants, timeout, response bounds and redirects.
    result = request(
        "network.request",
        "network.outbound",
        {
            "url": config["server_url"] + path,
            "headers": {
                "Authorization": 'MediaBrowser Client="Unnamed Tracking", Device="Plugin", '
                f'DeviceId="example.jellyfin-media-sync", Version="3", Token="{token}"'
            },
        },
    )
    code = result.get("status")
    if code != 200:
        if code in {401, 403}:
            raise SyncError(
                "Jellyfin rejected the server credential. Ask the administrator to replace it."
            )
        if code == 429:
            raise SyncError("Jellyfin rate limited this request. A retry is scheduled.")
        raise SyncError(
            f"Jellyfin request failed (HTTP {code or 0}). Check connection and server health."
        )
    return result.get("data")


def test_connection(values: dict[str, Any]) -> dict[str, Any]:
    actor(values, admin=True)
    config = load("master/config.json", {})
    config["server_url"] = server_url(config.get("server_url", ""))
    token = stored_token(config)
    try:
        info = jf(config, "/System/Info", token)
        users = jf(config, "/Users", token)
        folders = jf(config, "/Library/VirtualFolders", token)
        if (
            not isinstance(info, dict)
            or not isinstance(users, list)
            or not isinstance(folders, list)
        ):
            raise SyncError("Jellyfin returned invalid discovery data.")
        if len(users) > 1000 or len(folders) > 1000:
            raise SyncError("Discovery exceeded the 1000-entry limit.")
        config.update(
            connection="connected",
            tested_at=int(time.time()),
            users=[
                {"id": x["Id"], "name": str(x.get("Name", ""))[:200]}
                for x in users
                if isinstance(x, dict) and valid_id(x.get("Id"))
            ],
            libraries=[
                {
                    "id": x["ItemId"],
                    "name": str(x.get("Name", ""))[:200],
                    "kind": str(x.get("CollectionType", ""))[:50],
                }
                for x in folders
                if isinstance(x, dict) and valid_id(x.get("ItemId"))
            ],
        )
        config.pop("error", None)
    except SyncError as exc:
        config.update(connection="error", error=str(exc), tested_at=int(time.time()))
        store("master/config.json", config)
        raise
    store("master/config.json", config)
    return {"ok": True, "message": "Connected. Users and libraries discovered."}


def valid_id(value: Any) -> bool:
    return (
        isinstance(value, str) and re.fullmatch(r"[a-fA-F0-9]{32}", value) is not None
    )


def save_mappings(values: dict[str, Any]) -> dict[str, Any]:
    actor(values, admin=True)
    config = configuration()
    mappings = values.get("mappings")
    libraries = {x["id"] for x in config["libraries"]}
    if (
        not isinstance(mappings, dict)
        or not mappings
        or any(
            k not in libraries
            or v not in {"movie", "tv_show", "anime", "auto", "ignore"}
            for k, v in mappings.items()
        )
    ):
        raise SyncError(
            "Map discovered libraries to Movies, TV, Anime, Automatic or Ignore."
        )
    config["mappings"] = mappings
    config["mapping_revision"] = config.get("mapping_revision", 0) + 1
    store("master/config.json", config)
    return {
        "ok": True,
        "message": "Library mappings saved. Existing category changes are reported for review.",
    }


def authorize_identity(values: dict[str, Any]) -> dict[str, Any]:
    actor(values, admin=True)
    from uuid import UUID

    host_user = str(UUID(str(values.get("host_user_id", ""))))
    config = configuration()
    jellyfin_id = values.get("user_id")
    if jellyfin_id not in {x["id"] for x in config.get("users", [])}:
        raise SyncError("Select a discovered Jellyfin identity.")
    access = config.setdefault("identity_access", {})
    access[host_user] = [jellyfin_id]
    store("master/config.json", config)
    return {"ok": True, "message": "Identity approved for this host user."}


def get_config(values: dict[str, Any]) -> dict[str, Any]:
    user = actor(values)
    config = load("master/config.json", {})
    admin = values.get("_plugin_context", {}).get("is_admin") is True
    allowed = config.get("identity_access", {}).get(user, [])
    result = {
        "host_user_id": user,
        "is_admin": admin,
        "profile": load("profiles/" + user, {}),
        "users": [x for x in config.get("users", []) if x["id"] in allowed],
        "connection": config.get("connection", "untested"),
    }
    if admin:
        result["master"] = {
            k: config.get(k)
            for k in (
                "server_url",
                "sync_interval_minutes",
                "connection",
                "libraries",
                "users",
                "mappings",
                "error",
                "tested_at",
            )
        }
    if result["profile"]:
        try:
            base = namespace(user, configuration(), result["profile"])
            # Stop reading items once 50 conflicts are found instead of loading the whole library.
            reviews = []
            for key in keys(base + "items/"):
                r = load(key, {})
                if r.get("conflict"):
                    reviews.append({
                        "title": r["media"]["title"],
                        "external_id": r["media"]["external_id"],
                        "reason": r["conflict"],
                    })
                    if len(reviews) == 50:
                        break
            result["reviews"] = reviews
        except SyncError:
            result["reviews"] = []
    return result


def resolve_conflict(values: dict[str, Any]) -> dict[str, Any]:
    user = actor(values)
    config = configuration()
    profile = load("profiles/" + user, {})
    if not profile or profile.get("user_id") not in config.get(
        "identity_access", {}
    ).get(user, []):
        raise SyncError("Link your approved Jellyfin identity first.")
    base = namespace(user, config, profile)
    external_id = values.get("external_id")
    if not valid_id(external_id):
        raise SyncError("Choose a media item from the conflict list.")
    key = base + "items/" + external_id
    record = load(key, {})
    if record.get("conflict") != "local_watch_state_changed" or not record.get(
        "conflict_revision"
    ):
        raise SyncError(
            "This conflict requires manual category or deleted-media review."
        )
    record.update(revision=record.pop("conflict_revision"), needs_sync=True)
    record.pop("conflict", None)
    store(key, record)
    sync_now(values)
    return {
        "ok": True,
        "message": "Explicitly accepted Jellyfin watch state for this item. Synchronization queued.",
    }


def save_user(values: dict[str, Any]) -> dict[str, Any]:
    user = actor(values)
    config = configuration()
    jellyfin_id = values.get("user_id")
    if jellyfin_id not in config.get("identity_access", {}).get(user, []):
        raise SyncError(
            "Ask the administrator to approve your Jellyfin identity for your host user ID."
        )
    request("tasks.subscribe", "tasks.background", {})
    store(
        "profiles/" + user,
        {
            "user_id": jellyfin_id,
            "server": config["server_url"],
            "background_sync": values.get("background_sync") is True,
        },
    )
    return {
        "ok": True,
        "message": "Your Jellyfin identity is linked. No personal server credential is needed.",
    }


def unlink_user(values: dict[str, Any]) -> dict[str, Any]:
    user = actor(values)
    request("tasks.unsubscribe", "tasks.background", {})
    request("storage.delete", "plugin.storage", {"key": "profiles/" + user})
    return {"ok": True, "message": "Account unlinked; imported media is retained."}


def normalize(
    item: dict[str, Any], server: str, category: str = "auto"
) -> dict[str, Any] | None:
    external_id, title = item.get("Id"), item.get("Name")
    if (
        not isinstance(external_id, str)
        or not external_id
        or not isinstance(title, str)
        or not title.strip()
    ):
        return None
    # Older Jellyfin-compatible fixtures may omit Type; GetItems Movie payloads
    # are treated as movies for backwards compatibility.
    item_type = item.get("Type", "Movie")
    if item_type not in {"Movie", "Series"}:
        return None
    genres = item.get("Genres")
    genres = genres if isinstance(genres, list) else []
    tags = item.get("Tags")
    tags = tags if isinstance(tags, list) else []
    anime_markers = {
        str(x).strip().casefold() for x in (*genres, *tags) if isinstance(x, str)
    }
    is_anime = "anime" in anime_markers or any("anime" in x for x in anime_markers)
    media_type = (
        "anime" if is_anime else ("tv_show" if item_type == "Series" else "movie")
    )
    if category in {"movie", "tv_show", "anime"}:
        media_type = category
    ticks = item.get("RunTimeTicks")
    ticks = (
        ticks
        if isinstance(ticks, int) and not isinstance(ticks, bool) and ticks >= 0
        else 0
    )
    user_data = item.get("UserData") or {}
    if not isinstance(user_data, dict):
        user_data = {}
    count = user_data.get("PlayCount", 0)
    images = item.get("ImageTags")
    images = images if isinstance(images, dict) else {}
    return {
        "external_id": external_id,
        "media_type": media_type,
        "title": title.strip()[:500],
        "runtime_minutes": round(ticks / 600000000) if ticks else None,
        "release_year": item.get("ProductionYear"),
        "genres": [x[:128] for x in genres if isinstance(x, str)][:50],
        # No credential-bearing artwork URL is ever persisted in host media.
        "poster_url": server
        + "/Items/"
        + quote(external_id, safe="")
        + "/Images/Primary"
        if images.get("Primary")
        else None,
        "played": user_data.get("Played") is True if item_type == "Movie" else False,
        "in_progress": isinstance(user_data.get("PlaybackPositionTicks"), int)
        and user_data.get("PlaybackPositionTicks", 0) > 0,
        "play_count": count
        if isinstance(count, int) and not isinstance(count, bool) and count >= 0
        else 0,
        "last_played_at": user_data.get("LastPlayedDate"),
    }


def namespace(user: str, config: dict[str, Any], profile: dict[str, Any]) -> str:
    import hashlib

    digest = hashlib.sha256(
        (config["server_url"] + ":" + profile["user_id"]).encode()
    ).hexdigest()[:24]
    return "sync/" + user + "/" + digest + "/"


def status(values: dict[str, Any]) -> dict[str, Any]:
    user = actor(values)
    return load("status/" + user, {"phase": "idle"})


def sync_now(values: dict[str, Any]) -> dict[str, Any]:
    user = actor(values)
    if not load("profiles/" + user):
        raise SyncError("Link your Jellyfin identity first.")
    request("capabilities.check", "tasks.background", {})
    store(
        "sync/requests/" + user + "/" + str(uuid4()), {"requested_at": int(time.time())}
    )
    return {
        "queued": True,
        "message": "Synchronization queued for your linked Jellyfin identity.",
    }


def watch_now(values: dict[str, Any]) -> dict[str, Any]:
    user = actor(values)
    context = values.get("_plugin_context", {})
    media_id = context.get("resource_id")
    try:
        config = configuration()
    except SyncError:
        return {
            "ok": False,
            "error": "Configure the Jellyfin server and link your account first.",
        }
    mapping = load("watch/" + user + "/" + str(media_id), {})
    profile = load("profiles/" + user, {})
    if (
        not mapping
        or mapping.get("removed")
        or mapping.get("server") != config["server_url"]
        or mapping.get("user_id") != profile.get("user_id")
        or profile.get("user_id") not in config.get("identity_access", {}).get(user, [])
    ):
        return {
            "ok": False,
            "error": "This media has no available Jellyfin mapping for your linked account.",
        }
    url = (
        config["server_url"]
        + "/web/index.html#!/details?id="
        + quote(mapping["external_id"], safe="")
    )
    return {"ok": True, "url": url, "redirect_url": url}


def keys(prefix: str) -> list[str]:
    return request("storage.keys", "plugin.storage", {"prefix": prefix}).get("keys", [])


def host_sync(
    user: str,
    config: dict[str, Any],
    profile: dict[str, Any],
    record: dict[str, Any],
    *,
    episodes: list[dict[str, Any]] | None = None,
    complete: bool = False,
) -> bool:
    media = record["media"]
    fields = {
        k: media.get(k)
        for k in (
            "external_id",
            "media_type",
            "title",
            "genres",
            "runtime_minutes",
            "poster_url",
            "played",
            "in_progress",
        )
    }
    fields["in_progress"] = fields["in_progress"] or any(
        episode.get("in_progress") for episode in record.get("episodes", {}).values()
    )
    result = request(
        "tasks.request",
        "tasks.background",
        {
            "user_id": user,
            "method": "media.sync",
            "capability": "media.write",
            "payload": {
                **fields,
                "source": "jellyfin",
                "source_scope": config["server_url"] + ":" + profile["user_id"],
                "expected_revision": record.get("revision"),
                "episodes": episodes or [],
                "inventory_complete": complete,
            },
        },
    )
    if result.get("conflict"):
        record["conflict"] = result["conflict"]
        if result.get("revision"):
            record["conflict_revision"] = result["revision"]
        return False
    record.update(host_id=result["id"], revision=result["revision"])
    record.pop("conflict", None)
    record.pop("needs_sync", None)
    store(
        "watch/" + user + "/" + result["id"],
        {
            "server": config["server_url"],
            "user_id": profile["user_id"],
            "external_id": media["external_id"],
            "removed": False,
        },
    )
    return True


MAX_PAGES_PER_TICK = 4
MAX_FINALIZE_PER_TICK = 25


def sync_library(user: str) -> dict[str, Any]:
    config = configuration()
    profile = load("profiles/" + user, {})
    if profile.get("server") != config["server_url"] or profile.get(
        "user_id"
    ) not in config.get("identity_access", {}).get(user, []):
        raise SyncError(
            "Your server or approved identity changed. Relink your account."
        )
    token = stored_token(config)
    base = namespace(user, config, profile)
    cursor = load(base + "cursor", {})
    libraries = sorted(
        k for k, v in config.get("mappings", {}).items() if v != "ignore"
    )
    if not libraries:
        raise SyncError("Ask the administrator to map a Jellyfin library first.")
    revision = config.get("mapping_revision", 0)
    if not cursor or cursor.get("mapping_revision") != revision:
        cursor = {
            "library": 0,
            "phase": "roots",
            "offset": 0,
            "generation": str(uuid4()),
            "mapping_revision": revision,
            "processed": 0,
            "conflicts": 0,
            "skipped": 0,
            "started_at": int(time.time()),
        }
    state = {
        "phase": "syncing",
        "processed": cursor["processed"],
        "conflicts": cursor["conflicts"],
        "skipped": cursor["skipped"],
        "started_at": cursor["started_at"],
    }
    for _ in range(MAX_PAGES_PER_TICK):
        if cursor["library"] >= len(libraries):
            cursor["phase"] = "finalize"
        if cursor["phase"] == "finalize":
            records = sorted(keys(base + "items/"))
            batch = records[cursor["offset"] : cursor["offset"] + MAX_FINALIZE_PER_TICK]
            for key in batch:
                record = load(key)
                removed = record.get("seen") != cursor["generation"]
                if removed:
                    record["removed"] = True
                    if record.get("host_id"):
                        store(
                            "watch/" + user + "/" + record["host_id"],
                            {
                                "removed": True,
                                "external_id": record["media"]["external_id"],
                            },
                        )
                elif record["media"]["media_type"] != "movie":
                    missing = []
                    for eid, episode in list(record.get("episodes", {}).items()):
                        if episode.get("seen") != cursor["generation"]:
                            missing.append({**episode["data"], "removed": True})
                    incomplete = record.get("library") in cursor.get(
                        "incomplete_libraries", []
                    )
                    pending_removals = missing[:PAGE_SIZE] if not incomplete else []
                    if pending_removals:
                        if host_sync(
                            user, config, profile, record, episodes=pending_removals
                        ):
                            for episode in pending_removals:
                                record["episodes"].pop(episode["external_id"], None)
                            record["dirty"] = True
                        else:
                            cursor["conflicts"] += 1
                    if (
                        len(missing) > PAGE_SIZE
                        and not incomplete
                        and not record.get("conflict")
                    ):
                        # Resume this root next tick; a remote mass deletion stays bounded.
                        store(key, record)
                        store(base + "cursor", cursor)
                        state.update(
                            processed=cursor["processed"], conflicts=cursor["conflicts"]
                        )
                        store("status/" + user, state)
                        return state
                    if (
                        missing
                        or record.get("dirty")
                        or not record.get("complete")
                        or incomplete
                    ):
                        if not host_sync(
                            user, config, profile, record, complete=not incomplete
                        ):
                            cursor["conflicts"] += 1
                        else:
                            record.update(complete=not incomplete, dirty=False)
                store(key, record)
                cursor["offset"] += 1
            if cursor["offset"] >= len(records):
                state.update(
                    phase="complete",
                    finished_at=int(time.time()),
                    conflicts=cursor["conflicts"],
                    processed=cursor["processed"],
                    skipped=cursor["skipped"],
                )
                store("status/" + user, state)
                request("storage.delete", "plugin.storage", {"key": base + "cursor"})
                return state
            break
        library = libraries[cursor["library"]]
        query = urlencode(
            {
                "UserId": profile["user_id"],
                "ParentId": library,
                "Recursive": "true",
                "IncludeItemTypes": "Movie,Series"
                if cursor["phase"] == "roots"
                else "Episode",
                "EnableUserData": "true",
                "Fields": "Genres,Tags,DateCreated",
                "SortBy": "SortName",
                "SortOrder": "Ascending",
                "StartIndex": cursor["offset"],
                "Limit": PAGE_SIZE,
            }
        )
        page = jf(config, "/Items?" + query, token)
        items, total = (
            (page.get("Items"), page.get("TotalRecordCount"))
            if isinstance(page, dict)
            else (None, None)
        )
        if (
            not isinstance(items, list)
            or len(items) > PAGE_SIZE
            or isinstance(total, bool)
            or not isinstance(total, int)
            or total < 0
        ):
            raise SyncError("Jellyfin returned invalid page metadata.")
        state["total"] = total
        for item in items:
            if not isinstance(item, dict):
                cursor["skipped"] += 1
                continue
            if cursor["phase"] == "roots":
                media = normalize(
                    item, config["server_url"], config["mappings"][library]
                )
                if media is None:
                    cursor["skipped"] += 1
                    continue
                key = base + "items/" + quote(media["external_id"], safe="")
                record = load(key, {})
                changed = (
                    record.get("media") != media
                    or record.get("removed")
                    or record.get("needs_sync")
                )
                record.update(
                    media=media,
                    library=library,
                    seen=cursor["generation"],
                    removed=False,
                )
                if changed or not record.get("host_id"):
                    if not host_sync(
                        user,
                        config,
                        profile,
                        record,
                        complete=record.get("complete", False),
                    ):
                        cursor["conflicts"] += 1
                # Anime films use one episode so their watched state has native semantics.
                if (
                    media["media_type"] != "movie"
                    and item.get("Type", "Movie") == "Movie"
                ):
                    episode = {
                        "external_id": media["external_id"],
                        "season": 1,
                        "number": 1,
                        "title": media["title"],
                        "watched": media["played"],
                    }
                    if host_sync(
                        user, config, profile, record, episodes=[episode], complete=True
                    ):
                        record["complete"] = True
                        record["episodes"] = {
                            media["external_id"]: {
                                "data": episode,
                                "seen": cursor["generation"],
                            }
                        }
                store(key, record)
            else:
                key = base + "items/" + quote(str(item.get("SeriesId", "")), safe="")
                record = load(key, {})
                season, number = item.get("ParentIndexNumber"), item.get("IndexNumber")
                if (
                    not record
                    or record["media"]["media_type"] == "movie"
                    or not valid_id(item.get("Id"))
                    or isinstance(season, bool)
                    or not isinstance(season, int)
                    or season < 0
                    or isinstance(number, bool)
                    or not isinstance(number, int)
                    or number < 1
                ):
                    cursor["skipped"] += 1
                    if library not in cursor.setdefault("incomplete_libraries", []):
                        cursor["incomplete_libraries"].append(library)
                    continue
                user_data = item.get("UserData") or {}
                if not isinstance(user_data, dict):
                    cursor["skipped"] += 1
                    if library not in cursor.setdefault("incomplete_libraries", []):
                        cursor["incomplete_libraries"].append(library)
                    continue
                episode = {
                    "external_id": item["Id"],
                    "season": season,
                    "number": number,
                    "title": str(item.get("Name", ""))[:500],
                    "watched": user_data.get("Played") is True,
                }
                position = user_data.get("PlaybackPositionTicks", 0)
                progressing = (
                    not episode["watched"]
                    and isinstance(position, int)
                    and not isinstance(position, bool)
                    and position > 0
                )
                previous = record.setdefault("episodes", {}).get(item["Id"], {})
                if (
                    previous.get("data") != episode
                    or previous.get("in_progress", False) != progressing
                ):
                    record["episodes"][item["Id"]] = {
                        "data": episode,
                        "seen": cursor["generation"],
                        "in_progress": progressing,
                    }
                    if host_sync(user, config, profile, record, episodes=[episode]):
                        record["dirty"] = True
                    else:
                        # Keep the import baseline so this update remains pending.
                        if previous:
                            record["episodes"][item["Id"]] = previous
                        else:
                            record["episodes"].pop(item["Id"], None)
                        cursor["conflicts"] += 1
                else:
                    previous["seen"] = cursor["generation"]
                store(key, record)
        cursor["offset"] += len(items)
        cursor["processed"] += len(items)
        if cursor["offset"] >= total:
            cursor["offset"] = 0
            if cursor["phase"] == "roots":
                cursor["phase"] = "episodes"
            else:
                cursor["phase"] = "roots"
                cursor["library"] += 1
        elif not items:
            raise SyncError(
                "Jellyfin pagination stopped before all items were returned."
            )
    store(base + "cursor", cursor)
    state.update(
        processed=cursor["processed"],
        skipped=cursor["skipped"],
        conflicts=cursor["conflicts"],
    )
    store("status/" + user, state)
    return state


def worker_tick() -> int:
    request("capabilities.check", "tasks.background", {})
    # Round-robin users, with bounded remote pages and finalization work per tick.
    position = load("worker/position", 0)
    subscribers = request(
        "tasks.subscribers", "tasks.background", {"offset": position, "limit": 1}
    )
    users = subscribers.get("users", [])
    store(
        "worker/position",
        position + 1 if position + 1 < subscribers.get("total", 0) else 0,
    )
    for user in users:
        profile = load("profiles/" + user, {})
        state = load("status/" + user, {})
        queued = keys("sync/requests/" + user + "/")
        now = int(time.time())
        interval = load("master/config.json", {}).get("sync_interval_minutes", 15) * 60
        if not queued and not (
            state.get("phase") in {"syncing", "error"}
            or profile.get("background_sync")
            and now >= state.get("finished_at", 0) + interval
        ):
            continue
        if state.get("retry_at", 0) > now and not queued:
            continue
        try:
            sync_library(user)
        except (RuntimeError, OSError, ValueError, TypeError):
            # The gateway's diagnostic text can include arbitrary secrets.
            import sys

            exc = sys.exc_info()[1]
            failures = state.get("failures", 0) + 1
            state.update(
                phase="error",
                error=str(exc)
                if isinstance(exc, SyncError)
                else "A permission or gateway operation failed. Review grants and runtime diagnostics.",
                failures=failures,
                retry_at=now + min(3600, 30 * 2 ** min(failures, 7)),
                finished_at=now,
            )
            store("status/" + user, state)
        finally:
            for key in queued:
                request("storage.delete", "plugin.storage", {"key": key})
    return 5


def main() -> None:
    request("lifecycle.ready", "lifecycle.ready", {})
    time.sleep(1)
    while True:
        try:
            delay = worker_tick()
        except (RuntimeError, OSError, ValueError, TypeError):
            delay = 30
        time.sleep(delay)


if __name__ == "__main__":
    main()
