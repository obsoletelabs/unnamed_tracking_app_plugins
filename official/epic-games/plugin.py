"""Personal Epic library imports through Plugin API 1.1.3."""

from __future__ import annotations

import json
import time
from contextlib import contextmanager
from functools import wraps
from uuid import UUID, uuid4

import epic
from sdk.plugin_protocol import GatewayRequestError, request


def safe_action(handler):
    @wraps(handler)
    def invoke(values):
        try:
            return handler(values)
        except GatewayRequestError:
            return {
                "ok": False,
                "error": "The host denied or could not complete this action. Check plugin permissions, then retry.",
            }
        except epic.EpicError as exc:
            return {"ok": False, "error": str(exc)}

    return invoke


def actor(values):
    context = values.get("_plugin_context")
    if not isinstance(context, dict):
        raise epic.EpicError("An authenticated action context is required.")
    try:
        return str(UUID(context["user_id"]))
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise epic.EpicError("An authenticated action context is required.") from exc


def load(key, default=None):
    raw = request("storage.get", "plugin.storage", {"key": key}).get("value")
    return json.loads(raw) if raw is not None else default


def store(key, value):
    request("storage.put", "plugin.storage", {"key": key, "value": json.dumps(value)})


@contextmanager
def lease(user):
    """Serialize rotating tokens and checkpoints without a background worker."""
    key = "leases/" + user
    original = request("storage.get", "plugin.storage", {"key": key}).get("value")
    if original and json.loads(original)["expires_at"] > time.time():
        raise epic.EpicError("Another Epic action is running. Wait briefly, then resume.")
    value = json.dumps({"id": uuid4().hex, "expires_at": time.time() + 75})
    if not request(
        "storage.compare_and_swap",
        "plugin.storage",
        {
            "key": key,
            "expected": original,
            "value": value,
        },
    ).get("swapped"):
        raise epic.EpicError("Another Epic action is running. Wait briefly, then resume.")
    try:
        yield
    finally:
        request(
            "storage.compare_and_swap",
            "plugin.storage",
            {
                "key": key,
                "expected": value,
                "value": None,
            },
        )


def session_for(user):
    key = "secrets/users/" + user
    session = load(key)
    if not session:
        raise epic.EpicError("Connect your Epic account first.")
    if session["expires_at"] <= time.time() + 30:
        replacement = epic.token_pair(
            {"grant_type": "refresh_token", "refresh_token": session["refresh_token"]}
        )
        if replacement["account_id"] != session["account_id"]:
            raise epic.EpicError("Epic returned a different account. Reconnect before importing.")
        # Persist the rotated refresh token before any inventory or host import work.
        store(key, replacement)
        session = replacement
    return session


def public_status(user):
    session = load("secrets/users/" + user)
    state = load("sync/users/" + user, {})
    return {
        "connected": bool(session),
        "display_name": session["display_name"] if session else None,
        "login_url": epic.LOGIN_URL,
        "phase": state.get("phase", "idle"),
        "inventory_count": len(state.get("records", {})),
        "imported": state.get("imported", 0),
        "conflicts": state.get("conflicts", 0),
        "skipped": state.get("skipped", 0),
        "warning": state.get("warning"),
        "updated_at": state.get("updated_at"),
    }


@safe_action
def status(values):
    return public_status(actor(values))


@safe_action
def signin(values):
    actor(values)
    return {"redirect_url": epic.LOGIN_URL}


@safe_action
def connect(values):
    user = actor(values)
    code = epic.code_from(values.get("authorization_code"))
    with lease(user):
        session = epic.token_pair({"grant_type": "authorization_code", "code": code})
        store("secrets/users/" + user, session)
        request("storage.delete", "plugin.storage", {"key": "sync/users/" + user})
        return public_status(user)


@safe_action
def disconnect(values):
    user = actor(values)
    if values.get("_plugin_context", {}).get("confirmed") is not True:
        raise epic.EpicError("Confirm disconnecting this Epic account.")
    with lease(user):
        for prefix in ("secrets/users/", "sync/users/"):
            request("storage.delete", "plugin.storage", {"key": prefix + user})
        return public_status(user)


@safe_action
def start(values):
    user = actor(values)
    with lease(user):
        session = session_for(user)
        store(
            "sync/users/" + user,
            {
                "account_id": session["account_id"],
                "phase": "inventory",
                "cursor": None,
                "cursors": [],
                "records": {},
                "imported": 0,
                "conflicts": 0,
                "skipped": 0,
                "updated_at": int(time.time()),
            },
        )
        return public_status(user)


def inventory_step(state, session):
    rows, cursor = epic.library_page(session, state["cursor"])
    for row in rows:
        identity = row["namespace"] + ":" + row["catalogItemId"]
        record = state["records"].setdefault(identity, {**row, "apps": []})
        if row["appName"] not in record["apps"]:
            record["apps"].append(row["appName"])
    if len(state["records"]) > 10000 or len(state["cursors"]) >= 200:
        raise epic.EpicError(
            "Epic's inventory exceeded the safety limit. Availability has not changed."
        )
    if cursor:
        if cursor in state["cursors"] or cursor == state["cursor"]:
            raise epic.EpicError("Epic repeated an inventory cursor. Availability has not changed.")
        state["cursors"].append(cursor)
    state["cursor"] = cursor
    if cursor is None:
        state["pending"] = list(state["records"])
        state["phase"] = "playtime"


def catalogue_step(state, session):
    pending = state["pending"]
    if not pending:
        state["phase"] = "missing"
        return
    first = state["records"][pending[0]]
    identities = [i for i in pending if state["records"][i]["namespace"] == first["namespace"]][:25]
    metadata = epic.catalog(
        session, first["namespace"], [state["records"][i]["catalogItemId"] for i in identities]
    )
    items = [
        epic.game_item(
            state["records"][i], metadata[state["records"][i]["catalogItemId"]], state["playtime"]
        )
        for i in identities
    ]
    state.update(batch=[i for i in items if i is not None], batch_ids=identities, phase="import")
    state["skipped"] += sum(i is None for i in items)


def import_step(user, state):
    known_key = f"libraries/{user}/{state['account_id']}"
    known = load(known_key, {})
    if state["batch"]:
        result = request(
            "games.import",
            "games.write",
            {
                "source_label": "Epic Games",
                "source_scope": state["account_id"],
                "items": state["batch"],
            },
        )
        games = result.get("games")
        if not isinstance(games, list) or len(games) != len(state["batch"]):
            raise epic.EpicError("The host did not confirm the batch. Resume to retry safely.")
        for item, game in zip(state["batch"], games):
            if game.get("external_id") != item["external_id"]:
                raise epic.EpicError("The host returned an unexpected game identity. Resume later.")
            if game.get("conflict"):
                state["conflicts"] += 1
            else:
                known[item["external_id"]] = {
                    "external_id": item["external_id"],
                    "title": item["title"],
                }
                state["imported"] += 1
        store(known_key, known)
    state["pending"] = [i for i in state["pending"] if i not in state["batch_ids"]]
    state.pop("batch", None)
    state.pop("batch_ids", None)
    state["phase"] = "catalogue"


def missing_step(user, state):
    known = load(f"libraries/{user}/{state['account_id']}", {})
    if "missing" not in state:
        state["missing"] = [i for i in known if i not in state["records"]]
    identities = state["missing"][:25]
    if identities:
        request(
            "games.import",
            "games.write",
            {
                "source_label": "Epic Games",
                "source_scope": state["account_id"],
                "items": [{**known[i], "available": False} for i in identities],
            },
        )
        state["missing"] = state["missing"][len(identities) :]
    if not state["missing"]:
        state["phase"] = "complete"


@safe_action
def step(values):
    user = actor(values)
    with lease(user):
        session = session_for(user)
        state = load("sync/users/" + user)
        if not state or state["account_id"] != session["account_id"]:
            raise epic.EpicError("Start a new import for this connected account.")
        phase = state["phase"]
        if phase == "inventory":
            inventory_step(state, session)
        elif phase == "playtime":
            try:
                state["playtime"] = epic.playtime(session)
            except epic.EpicError:
                state["playtime"] = None
                state["warning"] = "Epic playtime was unavailable. Existing playtime was retained."
            state["phase"] = "catalogue"
        elif phase == "catalogue":
            catalogue_step(state, session)
        elif phase == "import":
            import_step(user, state)
        elif phase == "missing":
            missing_step(user, state)
        state["updated_at"] = int(time.time())
        store("sync/users/" + user, state)
        return public_status(user)


def main():
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
