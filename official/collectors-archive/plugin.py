"""Official archive behavior; every host interaction uses the public gateway."""

from __future__ import annotations

import base64
import hashlib
import json
import time
from urllib.parse import parse_qs, urlsplit

from sdk.plugin_protocol import request
import archive_storage as store
import bounties
import cards
import transport

TABLES = {"sets": "sets", "bounties": "bounties", "cards": "cards", "bounty_objectives": "objectives",
    "bounty_evidence": "evidence", "bounty_journal_entries": "journal", "bounty_point_transactions": "points"}


def migration_status(values):
    user = store.actor(values)
    completed = store.decode(store.raw(store.prefix(user, "metadata") + "import-tables"), [])
    return {"imported": set(completed) == set(TABLES), "completed_tables": completed}


def import_legacy(values):
    user = store.actor(values)
    table = values.get("table")
    if table not in TABLES:
        raise store.ArchiveError("Choose a valid legacy record group.")
    page = request("library.legacy.export", "library.legacy.read", {
        "table": table, "offset": values.get("offset", 0), "limit": 25,
        "chunk_offset": values.get("chunk_offset", 0), "sha256": values.get("sha256")})
    if page.get("chunk"):
        chunk = page["chunk"]
        selected = store.prefix(user, "import-chunks") + chunk["sha256"] + "/"
        store.request("storage.compare_and_swap", "plugin.storage", {
            "key": selected + str(chunk["offset"]), "expected": None, "value": chunk["base64"],
        })
        if chunk["next_offset"] is not None:
            return {"complete": False, "next_offset": page["next_offset"], "count": 0,
                "next_chunk_offset": chunk["next_offset"], "sha256": chunk["sha256"]}
        encoded = b"".join(base64.b64decode(store.raw(selected + str(start)), validate=True)
            for start in range(0, chunk["total_bytes"], 32_000))
        if hashlib.sha256(encoded).hexdigest() != chunk["sha256"]:
            raise store.ArchiveError("Legacy import changed. Restart this record.", 409)
        page["records"] = [json.loads(encoded)]
        for start in range(0, chunk["total_bytes"], 32_000):
            store.request("storage.delete", "plugin.storage", {"key": selected + str(start)})
    for record in page["records"]:
        kind = TABLES[table]
        record_id = store.identifier(record["id"])
        if kind in {"objectives", "evidence", "journal"}:
            kind += "/" + store.identifier(record["bounty_id"])
        if kind == "points":
            record_id = store.identifier(record["bounty_id"])
        # Existing imported or edited records are never overwritten on retry.
        store.swap(store.prefix(user, kind) + record_id, None, record)
        if table == "cards":
            store.mutate(store.prefix(user, "metadata") + "archive-number",
                lambda current: max(int(current or 0), int(record.get("archive_number") or 0)), default=0)
    if page["complete"]:
        key = store.prefix(user, "metadata") + "import-tables"
        store.mutate(key, lambda completed: sorted(set(completed or []) | {table}), default=[])
    return {"complete": page["complete"], "next_offset": page["next_offset"], "count": len(page["records"])}


def games(values):
    store.actor(values)
    operation = values.get("operation", "list")
    method = "games.details.list" if operation == "list" else "games.get"
    return transport.outgoing(values, request(method, "games.read", {"offset": values.get("offset", 0), "limit": 50,
        **({"game_id": store.identifier(values.get("game_id"))} if operation != "list" else {})}))


def game_media(values):
    store.actor(values)
    return transport.outgoing(values, request("games.media.list", "media.read", {"game_id": store.identifier(values.get("game_id")), "offset": values.get("offset", 0), "limit": 50}))


def require_import(values):
    if not migration_status(values)["imported"]:
        raise store.ArchiveError("Import your legacy archive first. This also checks new accounts with no old records.", 409)


def create_game_card(values):
    require_import(values)
    user = store.actor(values)
    context = values.get("_plugin_context", {})
    card = cards.create(user, {"game_id": context.get("resource_id")})
    return {"ok": True, "redirect_url": "/plugins/official.collectors-archive/card-detail?record_id=" + card["id"]}


def paginate(records, query, *, key=None):
    offset = max(0, int(query.get("offset", [0])[0]))
    limit = min(50, max(1, int(query.get("limit", [25])[0])))
    selected, size = [], 0
    for record in records[offset:offset + limit]:
        length = len(json.dumps(record, ensure_ascii=False).encode())
        if selected and size + length > 200_000:
            break
        selected.append(record)
        size += length
    next_offset = offset + len(selected)
    return {"status_code": 200, "body": {key: selected} if key else selected,
        "next_offset": next_offset if next_offset < len(records) else None}


def api(values):
    try:
        values = transport.incoming(values)
        require_import(values)
        return transport.outgoing(values, dispatch(values))
    except store.ArchiveError as exc:
        return {"status_code": exc.status, "body": {"detail": str(exc)}}
    except (ValueError, TypeError, KeyError):
        return {"status_code": 400, "body": {"detail": "Check the archive fields and try again."}}


def dispatch(values):
    user = store.actor(values)
    path = urlsplit(str(values.get("path", "")))
    if path.scheme or path.netloc:
        raise store.ArchiveError("Archive operations must use a local record path.")
    segments = path.path.strip("/").split("/")
    method = values.get("method", "GET")
    body = values.get("body", {})
    if not isinstance(body, dict):
        raise store.ArchiveError("Archive fields must be an object.")
    query = parse_qs(path.query)
    resource = segments[0]
    value = store.identifier(segments[1]) if len(segments) > 1 and segments[1] not in {"points", "random"} else None
    result, status = None, 200
    if resource == "cards":
        if len(segments) == 1 and method == "GET":
            found = sorted(store.records(user, "cards"), key=lambda item: item.get("archive_number") or 0)
            for field in ("game_id", "set_id"):
                if query.get(field):
                    wanted = store.identifier(query[field][0])
                    found = [item for item in found if item.get(field) == wanted]
            return paginate(found, query)
        if len(segments) == 1 and method == "POST":
            result, status = cards.create(user, body), 201
        elif len(segments) == 2 and method == "GET":
            result = store.get(user, "cards", value)
        elif len(segments) == 2 and method == "PATCH":
            result = cards.edit(user, value, body)
        elif len(segments) == 2 and method == "DELETE":
            store.remove(user, "cards", value)
            status = 204
        elif len(segments) == 3 and segments[2] == "prestige-challenge" and method == "POST":
            result = cards.prestige(user, value)
        elif result is None:
            raise store.ArchiveError("Card operation not found.", 404)
    elif resource == "sets":
        if len(segments) == 1 and method == "GET":
            # Count cards once instead of re-reading every card for each set.
            counts: dict = {}
            for card in store.records(user, "cards"):
                counts[card.get("set_id")] = counts.get(card.get("set_id"), 0) + 1
            found = []
            for item in sorted(store.records(user, "sets"), key=lambda item: item["name"]):
                count, target = counts.get(item["id"], 0), item.get("target_total")
                found.append({**item, "card_count": count,
                              "is_complete": bool(target is not None and count >= target)})
            return paginate(found, query)
        if len(segments) == 1 and method == "POST":
            result, status = cards.set_save(user, body), 201
        elif len(segments) == 2 and method == "GET":
            result = cards.set_read(user, value, detail=True)
        elif len(segments) == 2 and method == "PATCH":
            result = cards.set_save(user, body, value)
        elif len(segments) == 2 and method == "DELETE":
            cards.set_delete(user, value)
            status = 204
        else:
            raise store.ArchiveError("Set operation not found.", 404)
    elif resource == "bounties":
        if len(segments) == 1 and method == "GET":
            all_games = store.games()
            bounties.maybe_propose(user, all_games)
            cache = {}
            found = [bounties.read(user, item["id"], game_cache=cache, all_games=all_games) for item in store.records(user, "bounties")]
            for field in ("status", "type"):
                if query.get(field):
                    found = [item for item in found if item[field] == query[field][0]]
            found.sort(key=lambda item: item["created_at"], reverse=True)
            return paginate(found, query, key="bounties")
        if segments[1:] == ["points", "total"] and method == "GET":
            result = {"total": sum(item["amount"] for item in store.records(user, "points"))}
        elif segments[1:] == ["points", "history"] and method == "GET":
            return paginate(sorted(store.records(user, "points"), key=lambda item: item["created_at"], reverse=True), query, key="transactions")
        elif segments[1:] == ["random"] and method == "GET":
            result = {"proposal": bounties.proposal(user)}
        elif len(segments) == 1 and method == "POST":
            created = bounties.create(user, body)
            result, status = {"bounty": bounties.read(user, created["id"])}, 201
        elif len(segments) == 2 and method == "GET":
            result = {"bounty": bounties.read(user, value)}
        elif len(segments) == 2 and method == "PATCH":
            result = {"bounty": bounties.edit(user, value, body)}
        elif len(segments) == 2 and method == "DELETE":
            saved = store.get(user, "bounties", value)
            if saved["status"] == "completed":
                raise store.ArchiveError("Completed bounties are kept for history — abandon it instead if you want it out of the way.")
            store.remove(user, "bounties", value)
            for card in store.records(user, "cards"):
                if card.get("bounty_id") == value:
                    store.update(user, "cards", card["id"], lambda item: {**item, "bounty_id": None})
            result = {"deleted": True}
        elif len(segments) == 3 and segments[2] in {"complete", "pause", "resume", "abandon"} and method == "POST":
            saved = bounties.change_status(user, value, segments[2])
            result = {"status": saved["status"], "id": saved["id"]}
        elif len(segments) == 3 and segments[2] in {"objectives", "evidence", "journal"} and method == "POST":
            child, bounty = bounties.add_child(user, value, segments[2], body)
            result = {"objective" if segments[2] == "objectives" else "entry" if segments[2] == "journal" else "evidence": child, "bounty": bounty}
        elif len(segments) == 4 and segments[2] == "objectives" and method == "PATCH":
            child, bounty = bounties.edit_objective(user, value, segments[3], body)
            result = {"objective": child, "bounty": bounty}
        elif len(segments) == 4 and segments[2] in {"objectives", "evidence", "journal"} and method == "DELETE":
            store.get(user, "bounties", value)
            store.remove(user, segments[2] + "/" + value, segments[3])
            result = {"deleted": True, "bounty": bounties.read(user, value)}
        else:
            raise store.ArchiveError("Bounty operation not found.", 404)
    else:
        raise store.ArchiveError("Archive record type not found.", 404)
    return {"status_code": status, "body": result}


def main():
    request("lifecycle.ready", "lifecycle.ready", {})
    while True:
        time.sleep(60)
