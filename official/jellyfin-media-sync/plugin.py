"""Official Jellyfin preview: broker-only storage and user-scoped background sync."""

from __future__ import annotations

import json
import time
from typing import Any
from uuid import UUID, uuid4

from sdk.plugin_protocol import request
from jellyfin import SyncError, api, server_url, token_value


def load(key: str, default: Any = None) -> Any:
    raw = request("storage.get", "plugin.storage", {"key": key}).get("value")
    if raw is None:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        raise SyncError(
            "Saved plugin state is damaged. Restore its storage backup."
        ) from None


def store(key: str, value: Any) -> None:
    request("storage.put", "plugin.storage", {"key": key, "value": json.dumps(value)})
    _invalidate_for(key)


def delete(key: str) -> None:
    request("storage.delete", "plugin.storage", {"key": key})
    _invalidate_for(key)


# Watch Now lookups are cached per user in one bounded storage record so a repeat open
# costs one read. Servers, accounts, ordering and credentials feed the lookup, so any
# write to them drops the affected cache; the TTL bounds staleness from item syncs.
WATCH_CACHE_PREFIX = "watchcache/"
WATCH_CACHE_TTL = 60
WATCH_MISS_TTL = 15
WATCH_CACHE_MAX = 64


def invalidate_watch_cache(user: str | None = None) -> None:
    """Drop one user's cached lookups, or every user's when the change is shared."""
    if user is not None:
        request("storage.delete", "plugin.storage", {"key": WATCH_CACHE_PREFIX + user})
        return
    for key in request("storage.keys", "plugin.storage", {"prefix": WATCH_CACHE_PREFIX}).get("keys", []):
        request("storage.delete", "plugin.storage", {"key": key})


def _invalidate_for(key: str) -> None:
    kind, _, rest = key.partition("/")
    if kind in {"servers", "secrets"}:
        invalidate_watch_cache()
    elif kind in {"accounts", "profiles"} and rest:
        invalidate_watch_cache(rest.split("/", 1)[0])


def keys(prefix: str) -> list[str]:
    return request("storage.keys", "plugin.storage", {"prefix": prefix}).get("keys", [])


def identifier(value: Any) -> str:
    try:
        return UUID(str(value)).hex
    except (TypeError, ValueError, AttributeError):
        raise SyncError("Choose a valid saved server or account.") from None


def actor(values: dict, *, admin: bool = False) -> str:
    context = values.get("_plugin_context", {})
    if (
        not isinstance(context, dict)
        or not context.get("user_id")
        or (admin and context.get("is_admin") is not True)
    ):
        raise SyncError(
            "Administrator access is required."
            if admin
            else "Sign in to manage your account."
        )
    return str(UUID(context["user_id"]))


def server_by_id(value: Any) -> dict:
    saved = load("servers/" + identifier(value))
    if not saved:
        raise SyncError("The installation server is no longer available.")
    return saved


def account_by_id(user: str, value: Any) -> dict:
    account = load("accounts/" + user + "/" + identifier(value))
    if not account:
        raise SyncError("This account does not belong to you.")
    return account


def server_secret(server: dict) -> str | None:
    secret = load("secrets/servers/" + server["id"], {})
    return secret.get("token") if secret.get("url") == server["url"] else None


def account_token(user: str, account: dict, server: dict) -> str:
    if not server.get("enabled", True) or not account.get("enabled", True):
        raise SyncError("The server or account is disabled.")
    if account.get("auth") == "approved":
        access = server.get("identity_access", {}).get(user, [])
        if account["remote_user_id"] not in access:
            raise SyncError("An administrator must approve this Jellyfin identity.")
        value = server_secret(server)
    else:
        secret = load("secrets/accounts/" + user + "/" + account["id"], {})
        value = secret.get("token") if secret.get("url") == server["url"] else None
    if not value:
        raise SyncError(
            "Reconnect this account. Configuration and mappings have been retained.",
            code="authentication",
        )
    return token_value(value)


def save_server(values: dict) -> dict:
    actor(values, admin=True)
    identity = (
        identifier(values["server_id"]) if values.get("server_id") else uuid4().hex
    )
    old = load("servers/" + identity, {})
    url = server_url(values.get("url"))
    interval = values.get("interval_minutes", 15)
    retries = values.get("max_retries", 4)
    history_days = values.get("history_days", 30)
    if (
        any(
            isinstance(v, bool) or not isinstance(v, int)
            for v in (interval, retries, history_days)
        )
        or not 5 <= interval <= 1440
        or not 0 <= retries <= 10
        or not 1 <= history_days <= 3650
    ):
        raise SyncError(
            "Use an interval of 5–1440 minutes, 0–10 retries and 1–3650 history days."
        )
    name = values.get("name", "Jellyfin")
    if not isinstance(name, str) or not name.strip() or len(name) > 100:
        raise SyncError("Enter a server name of up to 100 characters.")
    config = {
        **old,
        "id": identity,
        "name": name.strip(),
        "url": url,
        "interval_minutes": interval,
        "max_retries": retries,
        "history_days": history_days,
        "enabled": values.get("enabled", True) is True,
        "revision": old.get("revision", 0) + 1,
    }
    if old.get("url") != url:
        config.update(
            libraries=[],
            mappings={},
            users=[],
            identity_access={},
            connection="untested",
        )
    replacement = values.get("api_key")
    if replacement:
        replacement = token_value(replacement)
        api(config, replacement, "/System/Info")
        store("secrets/servers/" + identity, {"token": replacement, "url": url})
    store("servers/" + identity, config)
    return {
        "ok": True,
        "server_id": identity,
        "message": "Server saved. Test it to approve libraries.",
    }


def clear_server_credential(values: dict) -> dict:
    actor(values, admin=True)
    server = server_by_id(values.get("server_id"))
    delete("secrets/servers/" + server["id"])
    server["revision"] = server.get("revision", 0) + 1
    store("servers/" + server["id"], server)
    return {
        "ok": True,
        "message": "Server credential removed. Library and account configuration retained.",
    }


def test_connection(values: dict) -> dict:
    actor(values, admin=True)
    server = server_by_id(values.get("server_id"))
    warnings = (
        ["HTTP sends credentials without transport encryption."]
        if server["url"].startswith("http:")
        else []
    )
    try:
        public = api(server, None, "/System/Info/Public")
        remote_server_id = str(public.get("Id", ""))[:256]
        if (
            server.get("remote_server_id")
            and server["remote_server_id"] != remote_server_id
        ):
            raise SyncError(
                "This URL points to a different Jellyfin server. Add it as a new server."
            )
        server["remote_server_id"] = remote_server_id or server["id"]
        token = server_secret(server)
        if not token:
            return {
                "ok": True,
                "warnings": warnings,
                "message": "Server reachable. Add a discovery key to approve libraries.",
                "version": public.get("Version"),
            }
        api(server, token, "/System/Info")
        libraries = api(server, token, "/Library/VirtualFolders")
        users = api(server, token, "/Users")
        if (
            not isinstance(libraries, list)
            or not isinstance(users, list)
            or len(libraries) > 2000
            or len(users) > 2000
        ):
            raise SyncError(
                "Server discovery returned an invalid or excessive response.",
                code="remote_data",
            )
        server["libraries"] = [
            {
                "id": str(v["ItemId"])[:256],
                "name": str(v.get("Name", "Library"))[:200],
                "type": str(v.get("CollectionType", ""))[:50],
            }
            for v in libraries
            if isinstance(v, dict) and v.get("ItemId")
        ]
        server["users"] = [
            {"id": identifier(v["Id"]), "name": str(v.get("Name", "User"))[:200]}
            for v in users
            if isinstance(v, dict) and v.get("Id")
        ]
        mappings = server.setdefault("mappings", {})
        for library in server["libraries"]:
            mappings.setdefault(
                library["id"],
                "auto" if library["type"] in {"movies", "tvshows"} else "ignore",
            )
        server.update(connection="connected", version=public.get("Version"))
        store("servers/" + server["id"], server)
        return {
            "ok": True,
            "warnings": warnings,
            "message": "Connected. Review library approval before syncing.",
        }
    except SyncError as exc:
        if exc.code == "certificate":
            return {
                "ok": False,
                "warnings": [str(exc)],
                "message": "Host CA trust is required before connection.",
            }
        raise


def save_mappings(values: dict) -> dict:
    actor(values, admin=True)
    server = server_by_id(values.get("server_id"))
    mappings = values.get("mappings")
    approved = {v["id"] for v in server.get("libraries", [])}
    if not isinstance(mappings, dict) or any(
        k not in approved or v not in {"ignore", "auto", "movie", "tv_show", "anime"}
        for k, v in mappings.items()
    ):
        raise SyncError("Map only discovered libraries to a supported media category.")
    server["mappings"] = {
        library: mappings.get(library, "ignore") for library in approved
    }
    server["revision"] = server.get("revision", 0) + 1
    store("servers/" + server["id"], server)
    return {
        "ok": True,
        "message": "Approved libraries saved. Music, books and Live TV remain excluded.",
    }


def authorize_identity(values: dict) -> dict:
    actor(values, admin=True)
    server = server_by_id(values.get("server_id"))
    host = str(UUID(str(values.get("host_user_id"))))
    remote = identifier(values.get("remote_user_id"))
    if remote not in {v["id"] for v in server.get("users", [])}:
        raise SyncError("Choose a discovered Jellyfin user.")
    access = server.setdefault("identity_access", {}).setdefault(host, [])
    if values.get("approved", True) is True and remote not in access:
        access.append(remote)
    elif values.get("approved") is False and remote in access:
        access.remove(remote)
    server["revision"] = server.get("revision", 0) + 1
    store("servers/" + server["id"], server)
    return {"ok": True, "message": "Identity approval updated."}


def _link(
    user: str, server: dict, values: dict, remote: dict, token: str | None
) -> dict:
    remote_id = identifier(remote.get("Id"))
    identity = (
        identifier(values["account_id"]) if values.get("account_id") else uuid4().hex
    )
    old = account_by_id(user, identity) if values.get("account_id") else {}
    if old and (old["remote_user_id"] != remote_id or old["server_id"] != server["id"]):
        raise SyncError(
            "This login belongs to another identity. Add a separate account."
        )
    request("tasks.subscribe", "tasks.background", {})
    account = {
        "enabled": True,
        "background_sync": False,
        "auto_merge": True,
        "notifications": False,
        "history_enabled": False,
        "libraries": [],
        **old,
        "id": identity,
        "server_id": server["id"],
        "remote_user_id": remote_id,
        "name": str(remote.get("Name", "Jellyfin account"))[:200],
        "auth": "login" if token else "approved",
        "revision": old.get("revision", 0) + 1,
    }
    if token:
        store(
            "secrets/accounts/" + user + "/" + identity,
            {"token": token_value(token), "url": server["url"]},
        )
    else:
        delete("secrets/accounts/" + user + "/" + identity)
    store("accounts/" + user + "/" + identity, account)
    return {
        "ok": True,
        "account_id": identity,
        "message": "Account connected. Configuration and mappings retained.",
    }


def login(values: dict) -> dict:
    user = actor(values)
    server = server_by_id(values.get("server_id"))
    username, password = values.get("username"), values.get("password")
    if (
        not isinstance(username, str)
        or not 1 <= len(username) <= 256
        or not isinstance(password, str)
        or len(password) > 2048
    ):
        raise SyncError("Enter your Jellyfin username and password.")
    auth = api(
        server,
        None,
        "/Users/AuthenticateByName",
        method="POST",
        body={"Username": username, "Pw": password},
    )
    return _link(
        user, server, values, auth.get("User", {}), token_value(auth.get("AccessToken"))
    )


def quick_connect_start(values: dict) -> dict:
    user = actor(values)
    server = server_by_id(values.get("server_id"))
    if api(server, None, "/QuickConnect/Enabled") is not True:
        raise SyncError("Quick Connect is disabled on this Jellyfin server.")
    state = api(server, None, "/QuickConnect/Initiate", method="POST")
    secret = token_value(state.get("Secret"))
    code = state.get("Code")
    if not isinstance(code, str) or not code.isdecimal() or len(code) > 12:
        raise SyncError(
            "Jellyfin returned an invalid Quick Connect code.", code="remote_data"
        )
    pending = uuid4().hex
    store(
        "secrets/quick/" + user + "/" + pending,
        {
            "secret": secret,
            "server_id": server["id"],
            "url": server["url"],
            "account_id": values.get("account_id"),
            "expires_at": int(time.time()) + 300,
        },
    )
    return {
        "ok": True,
        "pending_id": pending,
        "code": code,
        "expires_in": 300,
        "message": "Approve this code in Jellyfin, then check approval.",
    }


def quick_connect_finish(values: dict) -> dict:
    user = actor(values)
    key = "secrets/quick/" + user + "/" + identifier(values.get("pending_id"))
    pending = load(key, {})
    if not pending or pending.get("expires_at", 0) <= time.time():
        delete(key)
        raise SyncError("Quick Connect expired. Start a new connection.")
    server = server_by_id(pending["server_id"])
    if server["url"] != pending["url"]:
        delete(key)
        raise SyncError("The server changed. Start a new Quick Connect request.")
    state = api(
        server, None, "/QuickConnect/Connect", query={"secret": pending["secret"]}
    )
    if state.get("Authenticated") is not True:
        return {
            "ok": False,
            "pending": True,
            "message": "Waiting for approval in Jellyfin.",
        }
    auth = api(
        server,
        None,
        "/Users/AuthenticateWithQuickConnect",
        method="POST",
        body={"Secret": pending["secret"]},
    )
    result = _link(
        user,
        server,
        pending,
        auth.get("User", {}),
        token_value(auth.get("AccessToken")),
    )
    delete(key)
    return result


def link_approved(values: dict) -> dict:
    user = actor(values)
    server = server_by_id(values.get("server_id"))
    remote = identifier(values.get("remote_user_id"))
    if remote not in server.get("identity_access", {}).get(user, []):
        raise SyncError("An administrator must approve this identity first.")
    token = server_secret(server)
    if not token:
        raise SyncError("The server discovery credential has been removed.")
    identity = api(server, token, "/Users/" + remote)
    return _link(user, server, values, identity, None)


def save_account(values: dict) -> dict:
    user = actor(values)
    account = account_by_id(user, values.get("account_id"))
    server = server_by_id(account["server_id"])
    libraries = values.get("libraries", [])
    if (
        not isinstance(libraries, list)
        or len(libraries) > 2000
        or any(
            not isinstance(v, str)
            or server.get("mappings", {}).get(v, "ignore") == "ignore"
            for v in libraries
        )
    ):
        raise SyncError("Choose only administrator-approved libraries.")
    for setting in (
        "enabled",
        "background_sync",
        "auto_merge",
        "notifications",
        "history_enabled",
    ):
        if setting in values:
            if not isinstance(values[setting], bool):
                raise SyncError("Account switches must be true or false.")
            account[setting] = values[setting]
    account["libraries"] = list(dict.fromkeys(libraries))
    account["revision"] += 1
    store("accounts/" + user + "/" + account["id"], account)
    return {
        "ok": True,
        "message": "Account preferences saved. Disabling automatic sync affects future runs.",
    }


def clear_account_credential(values: dict) -> dict:
    user = actor(values)
    account = account_by_id(user, values.get("account_id"))
    delete("secrets/accounts/" + user + "/" + account["id"])
    account["auth"] = "login"
    account["revision"] += 1
    store("accounts/" + user + "/" + account["id"], account)
    return {
        "ok": True,
        "message": "Credential removed. Your preferences and mappings are retained.",
    }


def order_accounts(values: dict) -> dict:
    user = actor(values)
    accounts = [load(k) for k in keys("accounts/" + user + "/")]
    order = values.get("account_ids")
    if (
        not isinstance(order, list)
        or len(order) != len(accounts)
        or set(order) != {a["id"] for a in accounts}
    ):
        raise SyncError("Order every account exactly once.")
    store("profiles/" + user, {"order": order})
    return {
        "ok": True,
        "message": "Watch Now priority saved. Sync still uses all enabled accounts.",
    }


def ordered_accounts(user: str) -> list:
    accounts = [load(k) for k in keys("accounts/" + user + "/")]
    order = load("profiles/" + user, {}).get("order", [])
    rank: dict = {}
    for index, account_id in enumerate(order):
        rank.setdefault(account_id, index)
    accounts.sort(key=lambda a: rank.get(a["id"], len(order)))
    return accounts


def get_config(values: dict) -> dict:
    user = actor(values)
    admin = values["_plugin_context"].get("is_admin") is True
    servers = [load(k) for k in keys("servers/")]
    servers_by_id = {s["id"]: s for s in servers}
    secrets: dict = {}

    def secret_for(server: dict) -> str | None:
        if server["id"] not in secrets:
            secrets[server["id"]] = server_secret(server)
        return secrets[server["id"]]

    accounts = ordered_accounts(user)
    for account in accounts:
        server = servers_by_id.get(account["server_id"], {})
        account["credential_configured"] = (
            bool(
                secret_for(server)
                if account.get("auth") == "approved"
                else load("secrets/accounts/" + user + "/" + account["id"])
            )
            if server
            else False
        )
    visible_servers = []
    for server in servers:
        if admin:
            visible_servers.append(
                {**server, "credential_configured": bool(secret_for(server))}
            )
        else:
            visible_servers.append(
                {
                    "id": server["id"],
                    "name": server["name"],
                    "url": server["url"],
                    "enabled": server.get("enabled", True),
                    "libraries": [
                        v
                        for v in server.get("libraries", [])
                        if server.get("mappings", {}).get(v["id"], "ignore") != "ignore"
                    ],
                    "approved_users": [
                        v
                        for v in server.get("users", [])
                        if v["id"] in server.get("identity_access", {}).get(user, [])
                    ],
                }
            )
    review_keys = keys("reviews/" + user + "/")
    reviews = [load(k) for k in review_keys[:50]]
    return {
        "ok": True,
        "is_admin": admin,
        "host_user_id": user,
        "servers": visible_servers,
        "accounts": accounts,
        "reviews": reviews,
        "review_total": len(review_keys),
    }


def sync_now(values: dict) -> dict:
    user = actor(values)
    account = account_by_id(user, values.get("account_id"))
    request("tasks.subscribe", "tasks.background", {})
    store(
        "requests/" + user + "/" + account["id"] + "/" + uuid4().hex,
        {"rescan": values.get("rescan") is True},
    )
    return {
        "ok": True,
        "message": "Sync queued. One worker resumes this account's saved checkpoint.",
    }


def status(values: dict) -> dict:
    user = actor(values)
    return {
        "ok": True,
        "accounts": {
            k.rsplit("/", 1)[-1]: load(k) for k in keys("status/" + user + "/")
        },
    }


def resolve_review(values: dict) -> dict:
    user = actor(values)
    if values.get("_plugin_context", {}).get("confirmed") is not True:
        raise SyncError("Confirm the review decision in the host dialog.")
    account = account_by_id(user, values.get("account_id"))
    remote = str(values.get("external_id", ""))
    from sync import item_key

    key = item_key(user, account["id"], remote)
    episode_review = load(
        "reviews/" + user + "/" + account["id"] + "/" + key.rsplit("/", 1)[-1], {}
    )
    if episode_review.get("reason") == "missing_episode_number":
        decision = values.get("decision")
        if decision == "skip":
            override = {"skip": True}
        elif decision == "map_episode":
            from jellyfin import integer

            override = {
                "season": integer(values.get("season"), maximum=10000),
                "number": integer(values.get("number"), maximum=100000),
            }
            if not override["number"]:
                raise SyncError("Use an episode number greater than zero.")
        else:
            raise SyncError(
                "Assign an episode number or leave this episode unnumbered."
            )
        store(
            "decisions/" + user + "/" + account["id"] + "/" + uuid4().hex,
            {"external_id": remote, "episode_review": True, "override": override},
        )
        return sync_now({**values, "account_id": account["id"]})
    state = load(key, {})
    if not state.get("review"):
        raise SyncError("This item no longer needs review.")
    decision = values.get("decision")
    if decision not in {"skip", "new", "merge", "use_remote", "keep_category"}:
        raise SyncError("Choose a review decision.")
    if decision == "merge":
        target = str(UUID(str(values.get("target_id"))))
        if target not in {v["id"] for v in state["review"].get("candidates", [])}:
            raise SyncError("Choose one of the owned review candidates.")
        state["target_id"] = target
    if decision == "keep_category":
        category = state["review"].get("media_type")
        if category not in {"movie", "tv_show", "anime"}:
            raise SyncError("This review has no retained media category.")
        state["category_override"] = category
        state["item"]["media_type"] = category
    # Actions enqueue immutable decisions; only the supervised worker owns item
    # checkpoints, so polling/sync cannot overwrite a simultaneous review choice.
    store(
        "decisions/" + user + "/" + account["id"] + "/" + uuid4().hex,
        {
            "external_id": remote,
            "decision": decision,
            "target_id": state.get("target_id"),
            "category_override": state.get("category_override"),
        },
    )
    return sync_now({**values, "account_id": account["id"]})


def watch_now(values: dict) -> dict:
    """Resolve the Watch in Jellyfin target, serving a short-lived per-user cache.

    ``cached_only`` returns ``{"ok": False, "pending": True}`` on a miss without doing the
    lookup, so the host can render at once and call again to fill the cache. ``refresh``
    (for example after a failed open) evicts the entry and looks it up again.
    """
    user = actor(values)
    context = values.get("_plugin_context", {})
    media_id = context.get("resource_id")
    if not media_id:
        raise SyncError("Open a synced media item to watch it in Jellyfin.")
    media_id = str(UUID(str(media_id)))
    cache_key = WATCH_CACHE_PREFIX + user
    entries = load(cache_key, {}).get("entries")
    entries = entries if isinstance(entries, dict) else {}
    now = time.time()
    refresh = values.get("refresh") is True or context.get("refresh") is True
    hit = entries.get(media_id)
    if (
        not refresh
        and isinstance(hit, dict)
        and isinstance(hit.get("result"), dict)
        and isinstance(hit.get("expires_at"), (int, float))
        and now < hit["expires_at"]
    ):
        return {**hit["result"], "cached": True}
    if values.get("cached_only") is True and not refresh:
        return {"ok": False, "pending": True, "message": "Looking up your Jellyfin libraries."}
    result = _watch_lookup(user, media_id)
    ttl = WATCH_CACHE_TTL if result.get("ok") else WATCH_MISS_TTL
    entries = {k: v for k, v in entries.items() if isinstance(v, dict) and v.get("expires_at", 0) > now}
    entries[media_id] = {"result": result, "expires_at": now + ttl}
    while len(entries) > WATCH_CACHE_MAX:
        del entries[min(entries, key=lambda k: entries[k]["expires_at"])]
    # Written directly: caching a lookup is not a configuration change.
    request("storage.put", "plugin.storage", {"key": cache_key, "value": json.dumps({"entries": entries})})
    return result


def _watch_lookup(user: str, media_id: str) -> dict:
    # Only accounts and their servers are needed; the full settings payload
    # (secrets, reviews) would add storage reads for every account.
    servers: dict = {}
    for account in ordered_accounts(user):
        mapped = load(
            "watch/" + user + "/" + media_id + "/" + account["id"], {}
        )
        if not mapped.get("available"):
            continue  # skip the server read for accounts that never synced this item
        if account["server_id"] not in servers:
            servers[account["server_id"]] = load(
                "servers/" + identifier(account["server_id"]), {}
            ) or {}
        server = private = servers[account["server_id"]]
        approved = (
            private.get("mappings", {}).get(mapped.get("library_id"), "ignore")
            != "ignore"
        )
        selected = (
            not account.get("libraries")
            or mapped.get("library_id") in account["libraries"]
        )
        access = account.get("auth") != "approved" or account[
            "remote_user_id"
        ] in private.get("identity_access", {}).get(user, [])
        if (
            server
            and server.get("enabled", True)
            and account.get("enabled", True)
            and mapped.get("available")
            and approved
            and selected
            and access
        ):
            # Neither credentials nor server filesystem paths belong in navigation URLs.
            from urllib.parse import quote

            url = (
                server["url"]
                + "/web/index.html#!/details?id="
                + quote(mapped["external_id"], safe="")
            )
            return {
                "ok": True,
                "url": url,
                "redirect_url": url,
                "account": account["name"],
                "server": server["name"],
            }
    return {
        "ok": False,
        "message": "No available mapped Jellyfin item in your enabled accounts.",
    }


def worker_tick() -> int:
    from sync import run_account

    request("capabilities.check", "tasks.background", {})
    position = load("worker/position", 0)
    subscribers = request(
        "tasks.subscribers", "tasks.background", {"offset": position, "limit": 1}
    )
    store(
        "worker/position",
        position + 1 if position + 1 < subscribers.get("total", 0) else 0,
    )
    for user in subscribers.get("users", []):
        accounts = keys("accounts/" + user + "/")
        offset = load("worker/accounts/" + user, 0)
        if accounts:
            run_account(user, load(accounts[offset % len(accounts)]))
            store("worker/accounts/" + user, (offset + 1) % len(accounts))
    return 1


def main() -> None:
    request("lifecycle.ready", "lifecycle.ready", {})
    # Anything cached before this start may predate a disable or reconfiguration.
    invalidate_watch_cache()
    while True:
        try:
            delay = worker_tick()
        except (ValueError, RuntimeError, OSError, TypeError, KeyError):
            delay = 10
        time.sleep(delay)
