"""One bounded census page per worker tick, with durable accepted checkpoints."""

from __future__ import annotations

import hashlib
import json
import random
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from uuid import uuid4

import attention
from jellyfin import FIELDS, SyncError, api, integer, normalized, playback
from sdk.plugin_protocol import request
from plugin import account_token, delete, keys, load, server_by_id, server_secret, store

PAGE_SIZE = 100


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def item_key(user: str, account: str, external: str) -> str:
    if not isinstance(external, str) or not 1 <= len(external) <= 256:
        raise SyncError(
            "Jellyfin returned an invalid item identity.", code="remote_data"
        )
    return (
        "items/"
        + user
        + "/"
        + account
        + "/"
        + hashlib.sha256(external.encode()).hexdigest()
    )


def base(user: str, account: dict) -> str:
    return "sync/" + user + "/" + account["id"] + "/"


def library_index(user: str, account: dict, library: str) -> str:
    return (
        base(user, account)
        + "library-items/"
        + hashlib.sha256(library.encode()).hexdigest()
        + "/"
    )


def episode_override_key(user: str, account: dict, external: str) -> str:
    return (
        base(user, account)
        + "episode-overrides/"
        + hashlib.sha256(external.encode()).hexdigest()
    )


def host_sync(user: str, payload: dict) -> dict:
    return request(
        "tasks.request",
        "tasks.background",
        {
            "user_id": user,
            "method": "media.sync",
            "capability": "media.write",
            "payload": payload,
        },
    )


def apply_item(
    user: str,
    account: dict,
    server: dict,
    state: dict,
    *,
    episodes: list | None = None,
    episode_progress: dict | None = None,
    complete: bool = False,
    history: list | None = None,
    force: bool = False,
) -> bool:
    item = state["item"]
    key = item_key(user, account["id"], item["external_id"])
    if state.get("decision") == "skip":
        return False
    payload = {k: v for k, v in item.items() if k != "remote_type"}
    payload.update(
        source="jellyfin",
        source_scope=server.get("remote_server_id", server["id"])
        + ":"
        + account["remote_user_id"],
        sync_mode="enrich",
        auto_merge=account.get("auto_merge", True) and state.get("decision") != "new",
        merge_title_year=True,
        episodes=episodes or [],
        episode_progress=episode_progress or {},
        inventory_complete=complete,
        history=history or [],
        available=state.get("available", True),
    )
    if state.get("target_id"):
        payload["target_id"] = state["target_id"]
    if state.get("decision") == "use_remote":
        payload["force_watch"] = True
    digest = fingerprint(payload)
    channel = (
        "history:" + fingerprint({"ids": [event["external_id"] for event in history]})
        if history
        else "episodes:"
        + fingerprint({"ids": [episode["external_id"] for episode in episodes]})
        if episodes
        else "progress:" + fingerprint({"ids": sorted(episode_progress)})
        if episode_progress
        else "finalize"
        if complete
        else "root"
    )
    # The accepted digest changes only after the host transaction succeeds.
    if not force and state.get("digests", {}).get(channel) == digest:
        return True
    result = host_sync(user, payload)
    if result.get("conflict"):
        review = {
            "account_id": account["id"],
            "external_id": item["external_id"],
            "title": item["title"],
            "reason": result["conflict"],
            "candidates": result.get("candidates", []),
            "host_id": result.get("id"),
            "media_type": result.get("media_type"),
        }
        state["review"] = review
        store(key, state)
        store(
            "reviews/" + user + "/" + account["id"] + "/" + key.rsplit("/", 1)[-1],
            review,
        )
        return False
    state.update(
        host_id=result["id"],
        digest=digest,
        revision=result.get("revision"),
        review=None,
    )
    state["digests"] = {**state.get("digests", {}), channel: digest}
    state.pop("decision", None)
    store(key, state)
    delete("reviews/" + user + "/" + account["id"] + "/" + key.rsplit("/", 1)[-1])
    store(
        "watch/" + user + "/" + result["id"] + "/" + account["id"],
        {
            "external_id": item["external_id"],
            "available": state.get("available", True),
            "library_id": state["library_id"],
        },
    )
    return True


def page(
    server: dict, token: str, account: dict, library: str, kind: str, offset: int
) -> tuple[list, int]:
    data = api(
        server,
        token,
        "/Items",
        query={
            "UserId": account["remote_user_id"],
            "ParentId": library,
            "Recursive": "true",
            "IncludeItemTypes": kind,
            "Fields": FIELDS,
            "EnableUserData": "true",
            "SortBy": "SortName",
            "CollapseBoxSetItems": "false",
            "SortOrder": "Ascending",
            "StartIndex": offset,
            "Limit": PAGE_SIZE,
        },
    )
    if not isinstance(data, dict) or not isinstance(data.get("Items"), list):
        raise SyncError(
            "Jellyfin returned an invalid library page.", code="remote_data"
        )
    total = integer(data.get("TotalRecordCount"), maximum=10**9)
    rows = data["Items"]
    if (
        len(rows) > PAGE_SIZE
        or (not rows and offset < total)
        or offset + len(rows) > total
    ):
        raise SyncError(
            "The library changed during pagination. Resume with a rescan.",
            code="remote_data",
        )
    return rows, total


def _root_page(
    user: str, account: dict, server: dict, token: str, cursor: dict
) -> None:
    library = cursor["libraries"][cursor["library"]]
    rows, total = page(
        server, token, account, library, "Movie,Series", cursor["offset"]
    )
    # Validate the whole page before checkpointing or treating its census as complete.
    items = [normalized(row, server, server["mappings"][library]) for row in rows]
    if cursor.get("total") not in {None, total}:
        raise SyncError(
            "The library changed during pagination. Resume with a rescan.",
            code="remote_data",
        )
    cursor["total"] = total
    for item in items:
        key = item_key(user, account["id"], item["external_id"])
        state = load(key, {})
        if state.get("category_override"):
            item["media_type"] = state["category_override"]
        state.update(
            item=item,
            library_id=library,
            generation=cursor["generation"],
            available=True,
            missing=0,
        )
        # Keep staged metadata until accepted; it is not an imported baseline.
        store(key, state)
        store(library_index(user, account, library) + key.rsplit("/", 1)[-1], True)
        episodes = None
        if item["remote_type"] == "Movie" and item["media_type"] == "anime":
            episodes = [
                {
                    "external_id": "film:" + item["external_id"],
                    "season": 1,
                    "number": 1,
                    "title": item["title"],
                    "watched": item["played"],
                }
            ]
        if apply_item(
            user,
            account,
            server,
            state,
            episodes=episodes,
            complete=item["remote_type"] == "Movie",
            force=cursor.get("rescan", False),
        ):
            cursor["processed"] += 1
        else:
            cursor["reviews"] += 1
    cursor["offset"] += len(rows)
    if cursor["offset"] >= total:
        cursor.update(phase="episodes", offset=0, total=None)


def _episode_page(
    user: str, account: dict, server: dict, token: str, cursor: dict
) -> None:
    library = cursor["libraries"][cursor["library"]]
    rows, total = page(server, token, account, library, "Episode", cursor["offset"])
    if cursor.get("total") not in {None, total}:
        raise SyncError(
            "The library changed during pagination. Resume with a rescan.",
            code="remote_data",
        )
    cursor["total"] = total
    groups: dict[str, list] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("Type") != "Episode":
            raise SyncError(
                "Jellyfin returned an invalid episode page.", code="remote_data"
            )
        root = row.get("SeriesId")
        root_key = item_key(user, account["id"], root)
        state = load(root_key, {})
        if not state or state.get("generation") != cursor["generation"]:
            # Jellyfin can omit a Series from recursive roots while still
            # returning its episodes in the approved library. Fetch only the
            # referenced parent through this remote user's authenticated API.
            parent = api(
                server,
                token,
                "/Users/"
                + account["remote_user_id"]
                + "/Items/"
                + quote(root, safe=""),
                query={"Fields": FIELDS},
            )
            if (
                not isinstance(parent, dict)
                or parent.get("Id") != root
                or parent.get("Type") != "Series"
            ):
                raise SyncError(
                    "Jellyfin returned an invalid referenced series.",
                    code="remote_data",
                )
            item = normalized(parent, server, server["mappings"][library])
            if state.get("category_override"):
                item["media_type"] = state["category_override"]
            state.update(
                item=item,
                library_id=library,
                generation=cursor["generation"],
                available=True,
                missing=0,
            )
            store(root_key, state)
            store(
                library_index(user, account, library) + root_key.rsplit("/", 1)[-1],
                True,
            )
            apply_item(user, account, server, state, force=cursor.get("rescan", False))
            cursor["processed"] += 1
        external = row.get("Id")
        remote_key = item_key(user, account["id"], external)
        override = load(episode_override_key(user, account, external), {})
        season = override.get("season", row.get("ParentIndexNumber"))
        number = override.get("number", row.get("IndexNumber"))
        progress = playback(row)
        if season is None or number is None or number == 0:
            review_key = (
                "reviews/"
                + user
                + "/"
                + account["id"]
                + "/"
                + remote_key.rsplit("/", 1)[-1]
            )
            state["unmapped_generation"] = cursor["generation"]
            store(item_key(user, account["id"], root), state)
            if not override.get("skip"):
                store(
                    review_key,
                    {
                        "account_id": account["id"],
                        "external_id": external,
                        "title": str(row.get("Name", "Unnumbered episode"))[:500],
                        "reason": "missing_episode_number",
                        "host_id": state.get("host_id"),
                        "series_external_id": root,
                        "candidates": [],
                    },
                )
                cursor["reviews"] += 1
        else:
            season = integer(season, maximum=10000)
            number = integer(number, maximum=100000)
        episode = {
            "external_id": row.get("Id"),
            "season": season,
            "number": number,
            "title": str(row.get("Name", ""))[:500],
            "watched": row.get("UserData", {}).get("Played"),
        }
        item_key(user, account["id"], episode["external_id"])
        groups.setdefault(root, []).append((episode, progress))
    for root, group in groups.items():
        state = load(item_key(user, account["id"], root))
        changed = []
        progress = {}
        for episode, details in group:
            ekey = (
                base(user, account)
                + "episodes/"
                + hashlib.sha256(episode["external_id"].encode()).hexdigest()
            )
            old = load(ekey, {})
            digest = fingerprint({"episode": episode, "progress": details})
            if old.get("digest") != digest or cursor.get("rescan"):
                if episode["season"] is not None and episode["number"]:
                    changed.append(episode)
                progress[episode["external_id"]] = details
        if changed or progress:
            accepted = apply_item(
                user,
                account,
                server,
                state,
                episodes=changed,
                episode_progress=progress,
            )
            if not accepted:
                cursor["reviews"] += 1
                continue
        for episode, details in group:
            ekey = (
                base(user, account)
                + "episodes/"
                + hashlib.sha256(episode["external_id"].encode()).hexdigest()
            )
            store(
                ekey,
                {
                    "root": root,
                    "digest": fingerprint({"episode": episode, "progress": details}),
                    "external_id": episode["external_id"],
                    "generation": cursor["generation"],
                },
            )
            cursor["processed"] += 1
            if episode["season"] is not None and episode["number"]:
                remote_path = item_key(user, account["id"], episode["external_id"])
                delete(
                    "reviews/"
                    + user
                    + "/"
                    + account["id"]
                    + "/"
                    + remote_path.rsplit("/", 1)[-1]
                )
    cursor["offset"] += len(rows)
    if cursor["offset"] >= total:
        cursor.update(phase="finalize", offset=0, total=None)


def _finalize(user: str, account: dict, server: dict, cursor: dict) -> None:
    library = cursor["libraries"][cursor["library"]]
    prefix = "items/" + user + "/" + account["id"] + "/"
    candidates = [
        prefix + key.rsplit("/", 1)[-1]
        for key in keys(library_index(user, account, library))
    ]
    batch = candidates[cursor["offset"] : cursor["offset"] + 10]
    for key in batch:
        state = load(key)
        if state["library_id"] != library:
            continue
        present = state.get("generation") == cursor["generation"]
        if not present:
            if state.get("missing_generation") != cursor["generation"]:
                state["missing"] = state.get("missing", 0) + 1
                state["missing_generation"] = cursor["generation"]
            # Require absence in two successful censuses, never remove personal records.
            state["available"] = state["missing"] < 2
            store(key, state)
            if not state["available"] and state.get("host_id"):
                payload = {k: v for k, v in state["item"].items() if k != "remote_type"}
                payload.update(
                    sync_mode="enrich",
                    availability_only=True,
                    available=False,
                    source="jellyfin",
                    source_scope=server.get("remote_server_id", server["id"])
                    + ":"
                    + account["remote_user_id"],
                )
                host_sync(user, payload)
                store(
                    "watch/" + user + "/" + state["host_id"] + "/" + account["id"],
                    {
                        "external_id": state["item"]["external_id"],
                        "available": False,
                        "library_id": library,
                    },
                )
        if state.get("review") or state.get("decision") == "skip":
            continue
        apply_item(
            user,
            account,
            server,
            state,
            complete=present
            and state.get("unmapped_generation") != cursor["generation"],
            force=not present and not state["available"],
        )
    cursor["offset"] += len(batch)
    if cursor["offset"] >= len(candidates):
        cursor["library"] += 1
        cursor.update(phase="roots", offset=0, total=None)
        if cursor["library"] >= len(cursor["libraries"]):
            cursor.update(
                phase="history" if account.get("history_enabled") else "done", offset=0
            )


def _history(user: str, account: dict, server: dict, token: str, cursor: dict) -> None:
    history_key = base(user, account) + "history_cursor"
    start = datetime.now(timezone.utc).date() - timedelta(
        days=server.get("history_days", 30) - 1
    )
    previous = load(history_key, {})
    # Re-fetch the previous completed day so late durations/events are reconciled.
    day = max(start.isoformat(), previous.get("day", start.isoformat()))
    today = datetime.now(timezone.utc).date().isoformat()
    if day > today:
        cursor["phase"] = "done"
        return
    history_token = server_secret(server) or token
    try:
        rows = api(
            server,
            history_token,
            "/user_usage_stats/" + account["remote_user_id"] + "/" + day + "/GetItems",
            query={"timezoneOffset": 0},
        )
    except SyncError as exc:
        if exc.code in {"configuration", "authentication"}:
            cursor.update(
                phase="done",
                history_warning="Playback Reporting is unavailable or needs an administrator discovery credential. Counts and last played still sync; no past sessions are invented.",
            )
            return
        raise
    if not isinstance(rows, list) or len(rows) > 10000:
        raise SyncError(
            "Playback Reporting returned an invalid or excessive daily report.",
            code="remote_data",
        )
    grouped: dict[str, list] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("Type") not in {"Movie", "Episode"}:
            continue
        external = row.get("Id")
        state = load(item_key(user, account["id"], external), {})
        episode_id = None
        if row["Type"] == "Episode":
            ekey = (
                base(user, account)
                + "episodes/"
                + hashlib.sha256(str(external).encode()).hexdigest()
            )
            episode = load(ekey, {})
            state = (
                load(item_key(user, account["id"], episode["root"]), {})
                if episode
                else {}
            )
            episode_id = external
        if not state or state["library_id"] not in cursor["libraries"]:
            continue
        try:
            played = int(
                datetime.fromisoformat(day + "T" + row["Time"])
                .replace(tzinfo=timezone.utc)
                .timestamp()
            )
            duration = int(row["Duration"])
            event_id = str(row["RowId"])
            if not event_id or len(event_id) > 240 or duration < 0:
                raise ValueError
        except (KeyError, ValueError, TypeError):
            raise SyncError(
                "Playback Reporting returned an invalid session.", code="remote_data"
            ) from None
        grouped.setdefault(state["item"]["external_id"], []).append(
            {
                "external_id": "report:" + event_id,
                "episode_external_id": episode_id,
                "played_at": played,
                "duration_seconds": duration,
                "provenance": "reported_session",
            }
        )
    for root, events in grouped.items():
        for offset in range(0, len(events), 100):
            state = load(item_key(user, account["id"], root))
            apply_item(
                user,
                account,
                server,
                state,
                complete=state.get("unmapped_generation") != cursor["generation"],
                history=events[offset : offset + 100],
            )
    next_day = (datetime.fromisoformat(day).date() + timedelta(days=1)).isoformat()
    store(history_key, {"day": next_day if day < today else day})
    if day == today:
        cursor["phase"] = "done"


def run_account(user: str, account: dict) -> None:
    now = int(time.time())
    status_key = "status/" + user + "/" + account["id"]
    state = load(status_key, {})
    queued = keys("requests/" + user + "/" + account["id"] + "/")
    cursor_key = base(user, account) + "cursor"
    cursor = load(cursor_key, {})
    server = server_by_id(account["server_id"])
    interval = server.get("interval_minutes", 15) * 60
    revision = [server.get("revision", 0), account.get("revision", 0)]
    paused = (
        state.get("phase") == "error"
        and state.get("error_code")
        in {"authentication", "configuration", "certificate"}
        and state.get("revision") == revision
    )
    automatic = (
        account.get("background_sync")
        and not paused
        and now >= state.get("next_auto_at", 0)
    )
    resumed = (
        cursor and cursor.get("phase") != "done" and state.get("phase") == "syncing"
    )
    retry = (
        state.get("phase") == "error"
        and state.get("failures", 0) <= server.get("max_retries", 4)
        and state.get("retry_at", 0) <= now
        and state.get("error_code")
        not in {"authentication", "configuration", "certificate"}
    )
    changed = state.get("revision") != revision and state.get("phase") == "error"
    if (
        not server.get("enabled", True)
        or not account.get("enabled", True)
        or not (queued or automatic or resumed or retry or changed)
    ):
        return
    if queued or automatic or changed:
        state.update(failures=0, next_auto_at=now + interval)
        rescan = False
        for key in queued:
            if load(key, {}).get("rescan"):
                rescan = True
                cursor = {}
            delete(key)
    decisions = keys("decisions/" + user + "/" + account["id"] + "/")
    for key in decisions:
        decision = load(key)
        item_path = item_key(user, account["id"], decision["external_id"])
        if decision.get("episode_review"):
            store(
                episode_override_key(user, account, decision["external_id"]),
                decision["override"],
            )
            if decision["override"].get("skip"):
                delete(
                    "reviews/"
                    + user
                    + "/"
                    + account["id"]
                    + "/"
                    + item_path.rsplit("/", 1)[-1]
                )
            delete(key)
            cursor = {}
            continue
        item_state = load(item_path, {})
        if item_state:
            item_state.update(decision=decision["decision"], digest=None, digests={})
            for name in ("target_id", "category_override"):
                if decision.get(name):
                    item_state[name] = decision[name]
            store(item_path, item_state)
            delete(
                "reviews/"
                + user
                + "/"
                + account["id"]
                + "/"
                + item_path.rsplit("/", 1)[-1]
            )
        delete(key)
        cursor = {}
    try:
        token = account_token(user, account, server)
        libraries = [
            v
            for v in (account.get("libraries") or list(server.get("mappings", {})))
            if server.get("mappings", {}).get(v, "ignore") != "ignore"
        ]
        if not libraries:
            raise SyncError("No administrator-approved libraries are selected.")
        mapping_revision = fingerprint({v: server["mappings"][v] for v in libraries})
        scope = [
            server.get("remote_server_id", server["id"]),
            account["remote_user_id"],
        ]
        if (
            not cursor
            or cursor.get("phase") == "done"
            or cursor.get("libraries") != libraries
            or cursor.get("mapping_revision") != mapping_revision
            or cursor.get("scope") != scope
        ):
            cursor = {
                "generation": uuid4().hex,
                "phase": "roots",
                "library": 0,
                "libraries": libraries,
                "revision": revision,
                "mapping_revision": mapping_revision,
                "scope": scope,
                "offset": 0,
                "processed": 0,
                "reviews": 0,
                "rescan": rescan if queued or automatic or changed else False,
            }
        state.update(phase="syncing", revision=revision, error=None, error_code=None)
        store(status_key, state)
        phase = cursor["phase"]
        if phase == "roots":
            _root_page(user, account, server, token, cursor)
        elif phase == "episodes":
            _episode_page(user, account, server, token, cursor)
        elif phase == "finalize":
            _finalize(user, account, server, cursor)
        elif phase == "history":
            _history(user, account, server, token, cursor)
        store(cursor_key, cursor)
        done = cursor["phase"] == "done"
        state.update(
            phase="idle" if done else "syncing",
            processed=cursor["processed"],
            reviews=len(keys("reviews/" + user + "/" + account["id"] + "/")),
            library_index=cursor["library"],
            library_total=len(libraries),
            stage=cursor["phase"],
            offset=cursor["offset"],
            page_total=cursor.get("total"),
            history_warning=cursor.get("history_warning"),
            failures=0,
            retry_at=None,
        )
        if done:
            state["finished_at"] = now
            if state.get("notified_error"):
                try:
                    attention.report_recovered(user, account, str(server.get("name", "")))
                except (RuntimeError, ValueError, OSError):
                    # The earlier alert may be a plain message; there is no story to resolve.
                    pass
            state["notified_error"] = None
        store(status_key, state)
    except (ValueError, RuntimeError, OSError, TypeError, KeyError) as exc:
        failures = state.get("failures", 0) + 1
        safe = (
            str(exc)
            if isinstance(exc, SyncError)
            else "A host or permission operation failed. Review plugin grants; saved progress will resume."
        )
        code = exc.code if isinstance(exc, SyncError) else "transient"
        delay = max(
            exc.retry_after if isinstance(exc, SyncError) else 0,
            min(3600, 15 * 2 ** min(failures, 7)) + random.randint(0, 15),
        )
        state.update(
            phase="error",
            error=safe,
            error_code=code,
            failures=failures,
            retry_at=now + delay,
            revision=revision,
        )
        store(status_key, state)
        if account.get("notifications") and state.get("notified_error") != safe:
            try:
                attention.report_problem(user, account, str(server.get("name", "")), safe)
                state["notified_error"] = safe
                store(status_key, state)
            except (RuntimeError, ValueError, OSError):
                # An optional grant cannot prevent sync recovery or status reporting.
                pass
