"""Public gateway failures remain classifiable without breaking RuntimeError callers."""

import json
from io import StringIO

import pytest

from sdk.plugin_protocol import GatewayRequestError, request


@pytest.mark.parametrize(
    "detail, code",
    [
        ({"code": "unavailable"}, "unavailable"),
        ({"code": "forbidden"}, "forbidden"),
        ({"code": 503}, None),
        (None, None),
    ],
)
def test_gateway_error_retains_message_and_optional_code(monkeypatch, capsys, detail, code):
    """Exercise real SDK serialization/response parsing, including older runtimes."""
    response = {"error": "The gateway refused this request.", "error_detail": detail}
    monkeypatch.setattr("sys.stdin", StringIO(json.dumps(response) + "\n"))
    with pytest.raises(RuntimeError, match="The gateway refused this request") as failure:
        request("games.list", "games.read", {})
    assert isinstance(failure.value, GatewayRequestError)
    assert failure.value.code == code
    sent = json.loads(capsys.readouterr().out)
    assert sent["method"] == "games.list"
    assert sent["api_version"] == "v1"


def test_success_payload_still_passes_through(monkeypatch, capsys):
    """Adding error detail does not alter successful gateway responses."""
    monkeypatch.setattr("sys.stdin", StringIO('{"payload":{"registered":true}}\n'))
    assert request("notification_providers.register", "notification_providers.register", {}) == {
        "registered": True
    }
    assert json.loads(capsys.readouterr().out)["payload"] == {}


def test_public_sdk_contract_release_is_1_1_4():
    from sdk.plugin_protocol import API_CONTRACT_VERSION
    assert API_CONTRACT_VERSION == "1.1.4"
