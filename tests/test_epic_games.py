"""Epic wire DTOs, actor scoping and resumable failure/retry behavior."""

import importlib.util
import json
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


@pytest.mark.parametrize(
    "value",
    [
        CODE,
        json.dumps({"authorizationCode": CODE}),
        json.dumps({"redirectUrl": "https://www.epicgames.com/id/api/redirect?code=" + CODE}),
        "https://www.epicgames.com/id/api/redirect?code=" + CODE,
    ],
)
def test_authorization_code_formats_are_validated(service, value):
    assert service.epic.code_from(value) == CODE


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
    service.catalogue.clear()
    assert "catalogue" in service.plugin.step(context())["error"]
    assert service.imports == [] and service.plugin.status(context())["phase"] == "catalogue"
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
