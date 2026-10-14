"""Activity-owned privacy cleanup preserves other participants' inputs."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location("activity_privacy", ROOT / "official/discord-social-activity/privacy.py")
privacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(privacy)


def room():
    return {"participants": {
        "one": {"library":[{"source_id":"a"},{"source_id":"b"}],"manual":[{"title":"mine"}],"vote":"x"},
        "two": {"library":[{"source_id":"c"}],"manual":[],"vote":"x","vetoes":["x"]}},
        "host_id":"one","shortlist":[{"name":"private"}],"selected":{"name":"private"},
        "history":[{"title":"private"}],"player_limits":[{"confirmed_by":"one"}],"group_approvals":[{"confirmed_by":"two"}]}


def test_unlink_clears_only_selected_source_and_shared_caches():
    saved=room()
    cleaned=privacy.scrub_room(saved,"one",purge=False,source_id="a")
    assert cleaned["participants"]["one"]["library"] == [{"source_id":"b"}]
    assert cleaned["participants"]["one"]["manual"] == [{"title":"mine"}]
    assert cleaned["participants"]["two"]["vetoes"] == ["x"]
    assert cleaned["shortlist"] == [] and cleaned["history"] == [] and cleaned["selected"] is None
    assert len(saved["participants"]["one"]["library"]) == 2


def test_purge_removes_identity_inputs_confirmations_and_reassigns_host():
    cleaned=privacy.scrub_room(room(),"one",purge=True)
    assert list(cleaned["participants"]) == ["two"] and cleaned["host_id"] == "two"
    assert cleaned["player_limits"] == [] and cleaned["group_approvals"] == [{"confirmed_by":"two"}]
    assert privacy.scrub_room(cleaned,"two",purge=True) is None
