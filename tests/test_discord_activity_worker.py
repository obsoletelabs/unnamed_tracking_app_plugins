"""The Activity stays available across transient host-gateway outages."""

import importlib.util
import json
from pathlib import Path

import pytest

from sdk.plugin_protocol import GatewayRequestError

ROOT = Path(__file__).parents[1]


class WorkerStopped(Exception):
    """End an otherwise persistent worker after the observed cleanup cycle."""


@pytest.fixture
def worker(monkeypatch):
    source = ROOT / "official/discord-social-activity"
    monkeypatch.syspath_prepend(str(source))
    spec = importlib.util.spec_from_file_location("discord_activity_worker", source / "plugin.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.time, "time", lambda: 100)
    return module


@pytest.mark.parametrize("failed_method", ["storage.keys", "storage.get", "storage.compare_and_swap"])
def test_cleanup_recovers_after_gateway_outage_without_removing_live_rooms(
    worker, monkeypatch, capsys, failed_method
):
    rooms = {
        "rooms/expired": json.dumps({"expires_at": 90}),
        "rooms/live": json.dumps({"expires_at": 200}),
    }
    failures, delays = [], []

    def request(method, capability, payload):
        assert capability == "plugin.storage"
        if method == failed_method and not failures:
            failures.append(method)
            raise GatewayRequestError("private upstream response", {"code": "unavailable"})
        if method == "storage.keys":
            assert payload == {"prefix": "rooms/"}
            return {"keys": list(rooms)}
        if method == "storage.get":
            return {"value": rooms.get(payload["key"])}
        assert method == "storage.compare_and_swap"
        assert rooms[payload["key"]] == payload["expected"]
        assert payload["value"] is None
        del rooms[payload["key"]]
        return {"swapped": True}

    def sleep(seconds):
        delays.append(seconds)
        if seconds == 60:
            raise WorkerStopped

    monkeypatch.setattr(worker, "request", request)
    monkeypatch.setattr(worker.time, "sleep", sleep)
    with pytest.raises(WorkerStopped):
        worker.main()

    assert failures == [failed_method]
    assert delays == [1, 60]
    assert rooms == {"rooms/live": json.dumps({"expires_at": 200})}
    output = capsys.readouterr()
    assert output.out == ""
    assert "Waiting for the host gateway" in output.err
    assert "private upstream response" not in output.err


def test_repeated_outages_back_off_and_recovery_resets_the_delay(worker, monkeypatch):
    calls, delays = [], []

    def request(method, capability, payload):
        calls.append(method)
        if len(calls) <= 7 or len(calls) == 9:
            raise GatewayRequestError("Starting", {"code": "unavailable"})
        return {"keys": []}

    def sleep(seconds):
        delays.append(seconds)
        if delays.count(60) == 2:
            raise WorkerStopped

    monkeypatch.setattr(worker, "request", request)
    monkeypatch.setattr(worker.time, "sleep", sleep)
    with pytest.raises(WorkerStopped):
        worker.main()

    assert delays == [1, 2, 4, 8, 16, 30, 30, 60, 1, 60]


@pytest.mark.parametrize("code", ["forbidden", "invalid_request", "conflict", "internal", None])
def test_cleanup_does_not_hide_permanent_gateway_failures(worker, monkeypatch, code):
    def rejected(*args):
        raise GatewayRequestError("Rejected", {"code": code})

    monkeypatch.setattr(worker, "request", rejected)
    monkeypatch.setattr(worker.time, "sleep", lambda _: pytest.fail("Permanent denial must not retry"))
    with pytest.raises(GatewayRequestError, match="Rejected"):
        worker.main()
