"""Epic wire DTOs, actor scoping and resumable failure/retry behavior."""

import base64
import importlib.util
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import NAMESPACE_URL, uuid4, uuid5

import pytest

from sdk.plugin_protocol import GatewayRequestError

SOURCE = Path(__file__).parents[1] / "official/epic-games"
USER, OTHER = str(uuid4()), str(uuid4())
ACCOUNT = "a" * 32
CODE = "b" * 32


def context(user=USER, **values):
    return {"_plugin_context": {"user_id": user, "confirmed": True}, **values}


def row(item="item", namespace="store", app="game-app", **values):
    return {"namespace": namespace, "catalogItemId": item, "appName": app, **values}


@pytest.fixture
def service(monkeypatch):
    monkeypatch.syspath_prepend(str(SOURCE))
    modules = {}
    for name in ("epic", "plugin"):
        spec = importlib.util.spec_from_file_location(name, SOURCE / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        monkeypatch.setitem(sys.modules, name, module)
        spec.loader.exec_module(module)
        modules[name] = module
    storage, calls, imports, denied = {}, [], [], set()
    pages = {None: {"records": [row()], "responseMetadata": {"nextCursor": None}}}
    catalogue = {
        ("store", "item"): {
            "title": "Real-shaped game",
            "developer": "Studio",
            "categories": [{"path": "games"}],
        }
    }
    tokens = {
        "account_id": ACCOUNT,
        "access_token": "disposable-access",
        "refresh_token": "disposable-refresh",
        "displayName": "Fixture player",
        "expires_in": 3600,
    }
    failures = {}
    played = [{"artifactId": "game-app", "totalTime": 600}]

    def gateway(method, capability, payload):
        calls.append((method, capability, payload))
        if capability in denied:
            raise GatewayRequestError("SECRET provider diagnostics", {"code": "permission_denied"})
        key = payload.get("key")
        if method == "storage.get":
            return {"value": storage.get(key)}
        if method == "storage.put":
            storage[key] = payload["value"]
            return {}
        if method == "storage.delete":
            storage.pop(key, None)
            return {}
        if method == "storage.compare_and_swap":
            if storage.get(key) != payload["expected"]:
                return {"swapped": False}
            if payload["value"] is None:
                storage.pop(key, None)
            else:
                storage[key] = payload["value"]
            return {"swapped": True}
        if method == "games.import":
            imports.append(payload)
            return {
                "games": [
                    {
                        "external_id": item["external_id"],
                        "id": str(
                            uuid5(NAMESPACE_URL, payload["source_scope"] + item["external_id"])
                        ),
                        "created": True,
                    }
                    for item in payload["items"]
                ]
            }
        if method == "network.request":
            url = urlsplit(payload["url"])
            if url.path in failures:
                return failures[url.path]
            if url.path.endswith("/oauth/token"):
                form = parse_qs(payload["text_body"])
                assert form["token_type"] == ["eg1"]
                assert payload["headers"]["Authorization"].startswith("Basic ")
                if form["grant_type"] == ["refresh_token"]:
                    tokens["refresh_token"] = "rotated-refresh"
                    tokens["access_token"] = "rotated-access"
                return {"status": 200, "data": dict(tokens)}
            assert payload["headers"]["Authorization"] == "bearer " + tokens["access_token"]
            query = parse_qs(url.query)
            if url.path.endswith("/public/items"):
                return {"status": 200, "data": pages[query.get("cursor", [None])[0]]}
            if url.path.endswith("/all"):
                return {"status": 200, "data": played}
            if url.path.endswith("/bulk/items"):
                namespace = url.path.split("/")[-3]
                return {
                    "status": 200,
                    "data": {
                        identity: catalogue[(namespace, identity)]
                        for identity in query["id"]
                        if (namespace, identity) in catalogue
                    },
                }
            raise AssertionError("Unexpected Epic endpoint")
        raise AssertionError("Unexpected public gateway method: " + method)

    for module in modules.values():
        monkeypatch.setattr(module, "request", gateway)
    return type(
        "Service",
        (),
        {
            "plugin": modules["plugin"],
            "epic": modules["epic"],
            "storage": storage,
            "calls": calls,
            "imports": imports,
            "pages": pages,
            "catalogue": catalogue,
            "tokens": tokens,
            "failures": failures,
            "played": played,
            "denied": denied,
        },
    )()


def finish(service, user=USER):
    for _ in range(100):
        result = service.plugin.step(context(user))
        if result["phase"] == "complete":
            return result
    raise AssertionError("Import failed to finish")


def connected(service):
    service.plugin.connect(context(authorization_code=CODE))
    service.plugin.start(context())


def test_signin_uses_fixed_declared_destination_without_tokens(service):
    result = service.plugin.signin(context())
    assert urlsplit(result["redirect_url"]).hostname == "www.epicgames.com"
    assert "token" not in json.dumps(result)
    assert service.calls == []


def test_sandbox_assets_are_inlined_and_scripts_follow_the_form():
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    assert manifest["frontend"]["inline_assets"] is True
    html = (SOURCE / "frontend/index.html").read_text()
    assert html.index('id="connect-form"') < html.index('<script src="./app.js"')


def test_epic_is_a_connection_not_a_sidebar_page():
    manifest = json.loads((SOURCE / "manifest.json").read_text())
    document = json.loads((SOURCE / "ui.json").read_text())
    assert manifest["api_contract_version"] == document["api_contract_version"] == "1.1.11"
    capabilities = {item["name"] for item in manifest["capabilities"]}
    assert "frontend.connections" in capabilities
    assert "frontend.navigation.main" not in capabilities
    assert {item["capability"]["name"] for item in manifest["permissions"]} == capabilities
    assert all("navigation" not in page for page in document["pages"])
    (connection,) = document["connections"]
    assert connection["page_id"] in {page["id"] for page in document["pages"]}
    actions = {item["id"]: item for item in document["actions"]}
    # The status action is the one the host runs to show Connected / Not connected.
    assert connection["status_action_id"] == "status"
    assert actions["status"]["capability"]["name"] == "plugin.storage"
    assert connection["sync_action_id"] == "sync"
    assert manifest["scheduled_tasks"][0]["scope"] == "user"
    assert manifest["scheduled_tasks"][0]["action_id"] == "sync"


def test_menu_and_autosync_share_bounded_resumable_steps_and_do_not_touch_other_users(service):
    service.plugin.connect(context(authorization_code=CODE))
    assert service.plugin.sync(context())["phase"] == "playtime"
    assert service.plugin.sync(context())["phase"] == "catalogue"
    for _ in range(20):
        result = service.plugin.sync(context())
        if result["completed"]:
            break
        assert result["continue_after_seconds"] == 60
    assert result["completed"] and result["imported"] == 1
    assert "continue_after_seconds" not in result
    assert service.plugin.sync(context())["phase"] == "playtime"
    assert service.plugin.sync(context(OTHER))["ok"] is False
    assert not any(OTHER in key for key in service.storage)


def test_status_reports_only_connected_flag_and_account_name(service):
    assert service.plugin.status(context())["connected"] is False
    connected(service)
    status = service.plugin.status(context())
    assert status["connected"] is True
    assert status["display_name"] == "Fixture player"
    assert "token" not in json.dumps(status)


@pytest.mark.parametrize(
    "value",
    [
        CODE,
        json.dumps({"authorizationCode": CODE}),
        json.dumps({"redirectUrl": "https://www.epicgames.com/id/api/redirect?code=" + CODE}),
        "https://www.epicgames.com/id/api/redirect?code=" + CODE,
        # Partial copies of Epic's JSON page still carry the code.
        f'"authorizationCode": "{CODE}",',
        f"authorizationCode\t{CODE}\nredirectUrl\thttps://localhost/launcher/authorized?code={CODE}",
        (
            f'{{"warning":"Do not share this code","redirectUrl":"https://localhost/?code={CODE}",'
            f'"authorizationCode":"{CODE}","sid":null'
        ),
    ],
)
def test_authorization_code_formats_are_validated(service, value):
    assert service.epic.code_from(value) == CODE


@pytest.mark.parametrize(
    "value",
    [
        # The sign-in link holds only the public client ID, never a code.
        lambda epic: epic.LOGIN_URL,
        # Two different candidates are ambiguous rather than guessed.
        lambda epic: f"{CODE} {'c' * 32}",
    ],
)
def test_ambiguous_or_codeless_pastes_are_rejected(service, value):
    with pytest.raises(service.epic.EpicError):
        service.epic.code_from(value(service.epic))


@pytest.mark.parametrize(
    "value",
    [
        None,
        "invalid",
        "x" * 8193,
        '{"authorizationCode":"arbitrary"}',
        '{"authorizationCode":42}',
        "https://www.epicgames.com/?code=invalid",
    ],
)
def test_invalid_codes_make_no_network_request(service, value):
    assert service.plugin.connect(context(authorization_code=value))["ok"] is False
    assert service.calls == []


def test_personal_credentials_context_and_disconnect(service):
    assert "authenticated" in service.plugin.status({"user_id": USER})["error"]
    result = service.plugin.connect(context(authorization_code=CODE, user_id=OTHER))
    assert result["connected"] and "token" not in json.dumps(result)
    assert CODE not in json.dumps(service.storage)
    assert not service.plugin.status(context(OTHER))["connected"]
    assert "Confirm" in service.plugin.disconnect({"_plugin_context": {"user_id": USER}})["error"]
    service.plugin.disconnect(context())
    assert not service.plugin.status(context())["connected"]
    assert not any(key.startswith("secrets/") for key in service.storage)


def test_rotated_refresh_is_saved_before_inventory_failure(service):
    connected(service)
    key = "secrets/users/" + USER
    session = json.loads(service.storage[key])
    session["expires_at"] = 0
    service.storage[key] = json.dumps(session)
    service.failures["/library/api/public/items"] = {"status": 503, "error": "SECRET"}
    failure = service.plugin.step(context())
    assert failure["ok"] is False and "saved import" in failure["error"]
    assert "SECRET" not in json.dumps(failure)
    assert json.loads(service.storage[key])["refresh_token"] == "rotated-refresh"
    assert service.plugin.status(context())["phase"] == "inventory"
    assert service.imports == []
    assert not any(key.startswith("leases/") for key in service.storage)


def test_large_launcher_tokens_connect_and_reach_inventory_without_public_disclosure(service):
    service.tokens["access_token"] = "eg1~" + "x" * 4269
    service.tokens["refresh_token"] = "r" * 1071
    service.tokens["expires_in"] = 2592000
    result = service.plugin.connect(context(authorization_code=CODE))
    assert result["connected"]
    assert service.tokens["access_token"] not in json.dumps(result)
    assert service.tokens["refresh_token"] not in json.dumps(result)
    service.plugin.start(context())
    assert service.plugin.step(context())["phase"] == "playtime"


@pytest.mark.parametrize("expiry", [15, 3600, 86400, 86401, 2592000, 10**100])
def test_provider_expiry_connects_with_bounded_local_refresh(service, monkeypatch, expiry):
    monkeypatch.setattr(service.plugin.epic.time, "time", lambda: 1000)
    service.tokens["expires_in"] = expiry
    result = service.plugin.connect(context(authorization_code=CODE))
    assert result["connected"]
    session = json.loads(service.storage["secrets/users/" + USER])
    assert session["expires_at"] == 1000 + min(expiry, 86400)
    assert service.tokens["access_token"] not in json.dumps(result)
    assert service.tokens["refresh_token"] not in json.dumps(result)


@pytest.mark.parametrize("expiry", [None, True, False, "3600", 0, -1, float("nan"), float("inf")])
def test_invalid_provider_expiry_retains_previous_connection(service, expiry):
    assert service.plugin.connect(context(authorization_code=CODE))["connected"]
    previous = service.storage["secrets/users/" + USER]
    service.tokens["expires_in"] = expiry
    result = service.plugin.connect(context(authorization_code=CODE))
    assert result == {"ok": False, "error": "Epic returned an invalid sign-in expiry."}
    assert service.storage["secrets/users/" + USER] == previous
    assert CODE not in json.dumps(result)


def test_long_provider_lifetime_still_rotates_before_import_after_a_day(service, monkeypatch):
    now = [1000]
    monkeypatch.setattr(service.epic.time, "time", lambda: now[0])
    service.tokens["expires_in"] = 2592000
    assert service.plugin.connect(context(authorization_code=CODE))["connected"]
    now[0] += 86400
    service.plugin.start(context())
    session = json.loads(service.storage["secrets/users/" + USER])
    assert session["refresh_token"] == "rotated-refresh"
    assert session["expires_at"] == now[0] + 86400
    assert service.plugin.step(context())["phase"] == "playtime"


@pytest.mark.parametrize("field", ["access_token", "refresh_token"])
@pytest.mark.parametrize("invalid", [None, "", "x" * 8193, "token\r\nInjected: value"])
def test_invalid_replacement_token_retains_previous_connection(service, field, invalid):
    assert service.plugin.connect(context(authorization_code=CODE))["connected"]
    previous = service.storage["secrets/users/" + USER]
    service.tokens[field] = invalid
    result = service.plugin.connect(context(authorization_code=CODE))
    assert result["ok"] is False
    assert "previous connection is retained" in result["error"]
    assert service.storage["secrets/users/" + USER] == previous
    assert CODE not in json.dumps(result)
    if invalid:
        assert invalid not in json.dumps(result)


def test_page_catalogue_batching_namespace_identity_and_addon_filter(service):
    rows = [row(str(i), "one", str(i)) for i in range(27)]
    rows += [row("0", "two", "other"), row("engine", "ue"), row("private", sandboxType="PRIVATE")]
    service.pages[None] = {"records": rows[:12], "responseMetadata": {"nextCursor": "next"}}
    service.pages["next"] = {"records": rows[12:], "responseMetadata": {"nextCursor": None}}
    for item in rows:
        service.catalogue[(item["namespace"], item["catalogItemId"])] = {
            "title": "Same title",
            "categories": [{"path": "games"}],
        }
    service.catalogue[("one", "1")]["mainGameItem"] = {"id": "base"}
    connected(service)
    assert service.plugin.step(context())["phase"] == "inventory"
    assert service.imports == []
    result = finish(service)
    assert result["inventory_count"] == 28 and result["imported"] == 27 and result["skipped"] == 1
    assert all(
        len(batch["items"]) <= 25 and batch["source_scope"] == ACCOUNT for batch in service.imports
    )
    assert {item["external_id"] for batch in service.imports for item in batch["items"]} >= {
        "one:0",
        "two:0",
    }
    catalogue_calls = [
        call
        for call in service.calls
        if call[0] == "network.request" and "/bulk/items" in call[2]["url"]
    ]
    assert len(catalogue_calls) == 3
    assert all(
        len(parse_qs(urlsplit(call[2]["url"]).query)["id"]) <= 25 for call in catalogue_calls
    )


@pytest.mark.parametrize("defect", ["repeated", "malformed", "missing_metadata", "missing_records"])
def test_incomplete_inventory_never_changes_availability(service, defect):
    connected(service)
    finish(service)
    service.imports.clear()
    service.plugin.start(context())
    if defect == "repeated":
        service.pages[None]["responseMetadata"]["nextCursor"] = "repeat"
        service.pages["repeat"] = service.pages[None]
        service.plugin.step(context())
    elif defect == "malformed":
        service.pages[None]["records"] = [{"namespace": "one"}]
    elif defect == "missing_metadata":
        service.pages[None].pop("responseMetadata")
    else:
        service.pages[None].pop("records")
    assert service.plugin.step(context())["ok"] is False
    assert service.imports == []
    assert service.plugin.status(context())["phase"] == "inventory"


def test_catalogue_failure_preserves_batch_and_optional_playtime_is_not_zero(service):
    connected(service)
    service.failures["/library/api/public/playtime/account/" + ACCOUNT + "/all"] = {"status": 503}
    service.plugin.step(context())
    service.plugin.step(context())
    path = "/catalog/api/shared/namespace/store/bulk/items"
    service.failures[path] = {"status": 503}
    assert "retained" in service.plugin.step(context())["error"]
    assert service.imports == [] and service.plugin.status(context())["phase"] == "catalogue"
    service.failures.pop(path)
    service.catalogue[("store", "item")] = {"title": "Recovered game"}
    result = finish(service)
    assert result["warning"] and "playtime_seconds" not in service.imports[0]["items"][0]


def test_complete_inventory_marks_known_missing_without_deleting(service):
    connected(service)
    finish(service)
    assert service.imports[0]["items"][0]["playtime_seconds"] == 600
    service.pages[None]["records"] = []
    service.plugin.start(context())
    service.imports.clear()
    finish(service)
    assert service.imports == [
        {
            "source_label": "Epic Games",
            "source_scope": ACCOUNT,
            "items": [
                {"external_id": "store:item", "title": "Real-shaped game", "available": False}
            ],
        }
    ]
    service.plugin.disconnect(context())
    assert any(key.startswith("libraries/") for key in service.storage)


def test_crash_after_host_commit_replays_same_identity_and_checkpoint(service, monkeypatch):
    connected(service)
    while service.plugin.status(context())["phase"] != "import":
        service.plugin.step(context())
    original = service.plugin.request
    crashed = [False]

    def gateway(method, capability, payload):
        if method == "storage.put" and payload["key"].startswith("libraries/") and not crashed[0]:
            crashed[0] = True
            raise GatewayRequestError("SECRET")
        return original(method, capability, payload)

    monkeypatch.setattr(service.plugin, "request", gateway)
    assert "host denied" in service.plugin.step(context())["error"]
    assert service.plugin.status(context())["phase"] == "import"
    finish(service)
    assert service.imports[0] == service.imports[1]
    assert service.plugin.status(context())["imported"] == 1


def test_live_permission_denial_is_sanitized_and_checkpoint_retained(service):
    connected(service)
    while service.plugin.status(context())["phase"] != "import":
        service.plugin.step(context())
    service.denied.add("games.write")
    failure = service.plugin.step(context())
    assert failure["ok"] is False and "Check plugin permissions" in failure["error"]
    assert "SECRET" not in json.dumps(failure)
    assert service.plugin.status(context())["phase"] == "import"
    service.denied.clear()
    assert finish(service)["imported"] == 1


def test_active_lease_prevents_rotating_token_or_checkpoint_races(service):
    service.storage["leases/" + USER] = json.dumps({"id": "other", "expires_at": time.time() + 50})
    assert (
        "Another Epic action" in service.plugin.connect(context(authorization_code=CODE))["error"]
    )
    assert not any(call[0] == "network.request" for call in service.calls)


def test_scheduled_sync_reports_rate_limits_with_a_retry_hint_and_keeps_the_checkpoint(service):
    connected(service)
    service.failures["/library/api/public/items"] = {"status": 429}
    before = service.plugin.status(context())
    result = service.plugin.sync(context())
    assert result["completed"] is False and result["retry_after_seconds"] == 300
    assert "Epic is busy" in result["summary"] and "disable_schedule" not in result
    assert service.plugin.status(context())["phase"] == before["phase"]


def test_scheduled_sync_asks_the_host_to_turn_off_after_disconnect_or_rejection(service):
    missing = service.plugin.sync(context())
    assert missing["disable_schedule"] is True and missing["completed"] is False
    connected(service)
    key = "secrets/users/" + USER
    session = json.loads(service.storage[key])
    session["expires_at"] = 0
    service.storage[key] = json.dumps(session)
    service.failures["/account/api/oauth/token"] = {"status": 400}
    rejected = service.plugin.sync(context())
    assert rejected["disable_schedule"] is True and "rejected" in rejected["summary"]
    assert service.plugin.status(context())["phase"] == "inventory"


def test_a_stale_checkpoint_restarts_so_availability_comes_from_one_complete_walk(service):
    connected(service)
    service.plugin.sync(context())
    state_key = "sync/users/" + USER
    state = json.loads(service.storage[state_key])
    state.update(phase="missing", updated_at=int(time.time()) - 7 * 3600)
    service.storage[state_key] = json.dumps(state)
    result = service.plugin.sync(context())
    assert result["phase"] == "playtime" or result["phase"] == "inventory"
    assert result["completed"] is False
    assert json.loads(service.storage[state_key]).get("missing") is None


def test_support_docs_name_the_unofficial_dependency_without_launcher_credentials(service):
    root = SOURCE.parents[1]
    readme = (SOURCE / "README.md").read_text(encoding="utf-8")
    pages = [
        readme,
        (root / "wiki/docs/examples/epic-games.md").read_text(encoding="utf-8"),
        (root / "official/README.md").read_text(encoding="utf-8"),
        (root / "README.md").read_text(encoding="utf-8"),
    ]
    secret = base64.b64encode(f"{service.epic.CLIENT_ID}:{service.epic.CLIENT_SECRET}".encode())
    for page in pages:
        assert "unofficial" in page.lower()
        for value in (service.epic.CLIENT_ID, service.epic.CLIENT_SECRET, secret.decode()):
            assert value.lower() not in page.lower()
    assert "## Experimental service dependency" in readme
    assert "## Imported fields" in readme
    # Fully quoted troubleshooting messages must be the plugin's actual wording.
    source = (SOURCE / "epic.py").read_text(encoding="utf-8") + (
        SOURCE / "plugin.py"
    ).read_text(encoding="utf-8")
    troubleshooting = readme.split("## Troubleshooting and support", 1)[1]
    quoted = [m for m in re.findall(r'"([^"]+)"', troubleshooting) if "…" not in m]
    assert len(quoted) >= 8
    for message in quoted:
        assert message in source, message


def test_missing_catalogue_entries_are_skipped_and_do_not_block_later_games(service):
    rows = [row(str(i), "one", str(i)) for i in range(30)] + [row("late", "two", "late-app")]
    service.pages[None] = {"records": rows, "responseMetadata": {"nextCursor": None}}
    for item in rows:
        service.catalogue[(item["namespace"], item["catalogItemId"])] = {
            "title": "Game " + item["catalogItemId"], "categories": [{"path": "games"}]}
    for delisted in ("3", "26"):  # one in each 25-item batch
        service.catalogue.pop(("one", delisted))
    connected(service)
    result = finish(service)
    assert result["catalogue_missing"] == 2 and result["skipped"] == 2
    assert set(result["skipped_entries"]) == {"one:3", "one:26"}
    imported = {item["external_id"] for batch in service.imports for item in batch["items"]}
    assert "two:late" in imported and "one:3" not in imported and len(imported) == 29
    assert result["imported"] == 29


def test_all_entries_missing_from_a_batch_still_lets_the_import_complete(service):
    connected(service)
    service.catalogue.clear()
    result = finish(service)
    assert result["catalogue_missing"] == 1 and result["imported"] == 0
    assert service.imports == []


def test_progress_is_kept_when_a_later_batch_hits_a_transport_failure(service):
    rows = [row(str(i), "one", str(i)) for i in range(5)] + [row("x", "two", "x-app")]
    service.pages[None] = {"records": rows, "responseMetadata": {"nextCursor": None}}
    for item in rows:
        service.catalogue[(item["namespace"], item["catalogItemId"])] = {
            "title": "Game " + item["catalogItemId"], "categories": [{"path": "games"}]}
    service.catalogue.pop(("one", "2"))
    connected(service)
    path = "/catalog/api/shared/namespace/two/bulk/items"
    service.failures[path] = {"status": 503}
    for _ in range(100):
        result = service.plugin.step(context())
        if result.get("ok") is False:
            break
    else:
        raise AssertionError("transport failure was hidden")
    assert "retained" in result["error"]
    state = service.storage["sync/users/" + USER]
    assert json.loads(state)["imported"] == 4  # the first namespace's games survived
    service.failures.pop(path)
    final = finish(service)
    assert final["imported"] == 5 and final["catalogue_missing"] == 1


# The host's games.import contract (ImportedGameInput) accepts only these fields and limits.
IMPORT_FIELDS = {"external_id", "title", "description", "developer", "publisher", "tags",
                 "provider_ids", "playtime_seconds", "available"}
IMPORT_LIMITS = {"external_id": 256, "title": 500, "description": 20000, "developer": 200, "publisher": 200}


def test_imported_items_use_only_fields_and_limits_the_host_import_contract_accepts(service):
    metadata = {
        "title": "T" * 900, "description": "D" * 30000, "developer": "V" * 400, "publisher": "P" * 400,
        "keyImages": [{"type": "DieselGameBoxTall", "url": "https://cdn.example/box.jpg"}],
        "releaseInfo": [{"appId": "game-app", "platform": ["Windows"]}], "creationDate": "2020-01-01T00:00:00Z",
        "categories": [{"path": "games"}], "tags": [{"id": "1"}], "longDescription": "x" * 50,
    }
    item = service.epic.game_item({**row(), "apps": ["game-app"]}, metadata, {"game-app": 600})
    assert set(item) <= IMPORT_FIELDS
    assert {"description", "developer", "publisher", "playtime_seconds"} <= set(item)
    for field, limit in IMPORT_LIMITS.items():
        assert len(item[field]) <= limit
    assert item["provider_ids"] == {"epic": item["external_id"]}
    # Artwork, release dates and genres are not accepted by games.import, so none are sent.
    assert not {"keyImages", "artwork", "poster_url", "release_date", "tags", "releaseInfo"} & set(item)


def test_import_batches_stay_within_the_host_contract(service):
    rows = [row(str(i), "one", str(i)) for i in range(60)]
    service.pages[None] = {"records": rows, "responseMetadata": {"nextCursor": None}}
    for entry in rows:
        service.catalogue[(entry["namespace"], entry["catalogItemId"])] = {
            "title": "Game " + entry["catalogItemId"], "categories": [{"path": "games"}], "developer": "Studio"}
    connected(service)
    finish(service)
    assert service.imports and all(len(batch["items"]) <= 25 for batch in service.imports)
    assert all(set(item) <= IMPORT_FIELDS for batch in service.imports for item in batch["items"])
