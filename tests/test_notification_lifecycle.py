"""Public lifecycle serialization and exported schema bounds, independent of host imports."""
import json
from io import StringIO
from pathlib import Path
from uuid import uuid4

import jsonschema
import pytest

from sdk.notifications import poll_lifecycle

ROOT = Path(__file__).resolve().parents[1]


def test_lifecycle_poll_uses_explicit_read_grant_without_scope_selection(monkeypatch, capsys):
    response = {"events": [{"id": str(uuid4()), "notification_id": str(uuid4()),
                            "delivery_id": None, "status": "created",
                            "occurred_at": "2026-10-10T00:00:00+00:00"}],
                "cursor": "opaque", "has_more": False, "resync_required": False}
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps({"payload": response}) + "\n"))
    assert poll_lifecycle("previous", limit=25) == response
    sent = json.loads(capsys.readouterr().out)
    assert sent == {"api_version": "v1", "method": "notifications.lifecycle.poll",
                    "capability": "notifications.lifecycle.read",
                    "payload": {"cursor": "previous", "limit": 25}}
    schema = json.loads((ROOT / "tools/schemas/notification-lifecycle-page-v1.schema.json").read_text())
    jsonschema.validate(response, schema)
    assert set(response["events"][0]) == {"id", "notification_id", "delivery_id", "status", "occurred_at"}


def test_expired_cursor_is_preserved_for_explicit_resynchronisation(monkeypatch, capsys):
    response = {"events": [], "cursor": "restart", "has_more": False, "resync_required": True}
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps({"payload": response}) + "\n"))
    assert poll_lifecycle() == response
    assert json.loads(capsys.readouterr().out)["payload"] == {"cursor": None, "limit": 100}


@pytest.mark.parametrize("arguments", [
    {"limit": True}, {"limit": "10"}, {"limit": 0}, {"limit": 201},
    {"cursor": ""}, {"cursor": "x" * 1025}, {"cursor": 12},
])
def test_invalid_pages_do_not_send_a_request(capsys, arguments):
    with pytest.raises(ValueError):
        poll_lifecycle(**arguments)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("extra", ["title", "body", "destination_id", "credentials", "source"])
def test_lifecycle_response_schema_rejects_unapproved_data(extra):
    item = {"id": str(uuid4()), "notification_id": str(uuid4()), "delivery_id": None,
            "status": "sent", "occurred_at": "2026-10-10T00:00:00+00:00", extra: "private"}
    schema = json.loads((ROOT / "tools/schemas/notification-lifecycle-page-v1.schema.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"events": [item], "cursor": "opaque", "has_more": False,
                             "resync_required": False}, schema)


def test_query_schema_rejects_caller_selected_owner():
    schema = json.loads((ROOT / "tools/schemas/notification-lifecycle-query-v1.schema.json").read_text())
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({"user_id": str(uuid4())}, schema)
    assert schema["x-api-contract-version"] == "1.1.4"