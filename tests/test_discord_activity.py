"""Hard-rule and multi-participant regression coverage for the game-night engine."""

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location("game_night_engine", ROOT / "official/discord-social-activity/engine.py")
engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(engine)


def context(actor="one", **changes):
    return {"actor_id": actor, "room": "verified-room", "display_name": actor,
            "connected": False, "library": [], "source_states": {},
            "allow_guests": True, "retention_hours": 48, **changes}


def game(title="Together", **changes):
    return {"title": title, "platform": "PC", "min_players": 1, "max_players": 4,
            "duration_minutes": 60, "genres": ["Co-op"], "owned": True, **changes}


def add(state=None, actor="one", **changes):
    return engine.transition(state, {"operation": "manual", "game": game(**changes)}, context(actor), now=1000)


def test_two_people_share_pool_but_cannot_replace_each_others_rules():
    state, _ = add()
    state, result = add(state, "two")
    assert result["pool"]["eligible"][0]["title"] == "Together"
    state, _ = engine.transition(state, {"operation": "preferences", "participant_id": "two",
        "preferences": {"max_minutes": 30}}, context(), now=1001)
    assert state["participants"]["one"]["preferences"]["max_minutes"] == 30
    assert state["participants"]["two"]["preferences"]["max_minutes"] is None
    assert not engine.evaluate(state, now=1001)["eligible"]


def test_host_cannot_ignore_veto_by_changing_mode_or_rerolling():
    state, _ = add()
    state, _ = add(state, "two")
    state, _ = engine.transition(state, {"operation": "veto", "key": "title:together"}, context("two"), now=1001)
    for mode in ("strict", "balanced", "discovery"):
        state, result = engine.transition(state, {"operation": "mode", "mode": mode}, context(), now=1002)
        assert not result["pool"]["eligible"]
        with pytest.raises(engine.SessionError, match="No game"):
            engine.transition(state, {"operation": "roll"}, context(), now=1003)


def test_only_current_host_can_roll_and_transfer_does_not_change_rules():
    state, _ = add()
    state, _ = add(state, "two")
    with pytest.raises(engine.SessionError, match="host"):
        engine.transition(state, {"operation": "roll"}, context("two"), now=1001)
    with pytest.raises(engine.SessionError, match="Confirm"):
        engine.transition(state, {"operation": "transfer", "participant_id": "two"}, context(), now=1001)
    state, _ = engine.transition(state, {"operation": "transfer", "participant_id": "two", "confirmed": True}, context(), now=1001)
    state, result = engine.transition(state, {"operation": "roll"}, context("two"), now=1002)
    assert result["host_id"] == "two" and len(result["shortlist"]) == 1


def test_no_owner_and_no_purchase_consent_still_exclude_unowned_games():
    state, _ = add(owned=False)
    state, _ = engine.transition(state, {"operation": "preferences", "preferences": {
        "allow_purchase": True, "owned_only": False, "budget": 10000}}, context(), now=1001)
    for mode in ("strict", "balanced", "discovery"):
        state["mode"] = mode
        pool = engine.evaluate(state, now=1002)
        assert not pool["eligible"]
    state, _ = add(owned=False)
    assert "purchase-consent rule" in " ".join(engine.evaluate(state, now=1002)["excluded"][0]["excluded_reasons"])


def test_price_filters_pause_but_unknown_cost_is_never_reported_as_free():
    state, _ = add()
    state, _ = add(state, "two", owned=False)
    state, _ = engine.transition(state, {"operation": "preferences", "preferences": {
        "allow_purchase": True, "owned_only": False, "budget": 0, "minimum_discount": 100}}, context("two"), now=1001)
    state, result = engine.transition(state, {"operation": "mode", "mode": "balanced"}, context(), now=1002)
    candidate = result["pool"]["eligible"][0]
    assert candidate["price_status"] == "unavailable"
    assert candidate["access"][1]["cost"] is None
    assert candidate["access"][1]["purchase_required"] is True


def test_imported_ownership_needs_compatibility_and_live_source():
    library = [{"id": "g1", "title": "Together", "owned": True, "source_id": "source",
                "source_state": "connected", "ownership_provenance": "instance_library"}]
    ctx = context(library=library, source_states={"source": "connected"}, connected=True)
    state, result = engine.transition(None, {}, ctx, now=1000)
    assert not result["pool"]["eligible"]
    state, result = engine.transition(state, {"operation": "manual", "game": game()}, ctx, now=1001)
    assert result["pool"]["eligible"]
    state, result = engine.transition(state, {}, context(connected=True, library=library,
        source_states={"source": "revoked"}), now=1002)
    assert not result["pool"]["eligible"]


@pytest.mark.parametrize("changes,rule", [({"max_players": 1}, "player-count"),
    ({"platform": "PlayStation"}, "Cross-platform"), ({"duration_minutes": None}, "session length")])
def test_player_platform_and_unknown_time_exclusions(changes, rule):
    state, _ = add()
    state, _ = add(state, "two", **changes)
    if rule == "session length":
        state, _ = engine.transition(state, {"operation": "preferences", "preferences": {"max_minutes": 60}}, context("two"), now=1001)
    reasons = " ".join(engine.evaluate(state, now=1002)["excluded"][0]["excluded_reasons"])
    assert rule in reasons


def test_votes_are_one_per_person_and_selection_rechecks_eligibility():
    state, _ = add()
    state, _ = add(state, "two")
    state, _ = engine.transition(state, {"operation": "roll"}, context(), now=1001)
    for _ in range(2):
        state, result = engine.transition(state, {"operation": "vote", "key": "title:together"}, context("two"), now=1002)
    assert result["shortlist"][0]["votes"] == 1
    state, result = engine.transition(state, {"operation": "finalize"}, context(), now=1003)
    assert result["selected"]["title"] == "Together"
    state, result = engine.transition(state, {"operation": "veto", "key": "title:together"}, context("two"), now=1004)
    assert result["selected"] is None
    with pytest.raises(engine.SessionError, match="no longer eligible"):
        engine.transition(state, {"operation": "finalize"}, context(), now=1005)


def test_reconnect_keeps_rules_and_votes_expiry_starts_fresh():
    state, _ = add()
    state, _ = engine.transition(state, {"operation": "preferences", "preferences": {"budget": 12}}, context(), now=1001)
    restored, result = engine.transition(state, {}, context(), now=1060)
    assert result["me"]["preferences"]["budget"] == 12
    _, result = engine.transition(restored, {}, context(), now=state["expires_at"] + 1)
    assert result["me"]["preferences"]["budget"] == 0


def test_owner_guest_policy_and_leave_clear_inputs():
    with pytest.raises(engine.SessionError, match="disabled guest"):
        engine.transition(None, {"operation": "manual", "game": game()}, context(allow_guests=False), now=1000)
    state, _ = add()
    state, result = engine.transition(state, {"operation": "leave"}, context(), now=1001)
    assert not state["participants"]["one"]["manual"]
    assert not result["me"]["active"]


def test_soft_titles_platform_aliases_and_different_provider_ids_match():
    state, _ = add(title="Subnautica 2", provider_ids={"steam": "123"})
    state, result = add(state, "two", title="SuBnA uTicA2", platform="Windows", provider_ids={"steam": "456"})
    assert len(result["pool"]["eligible"]) == 1
    assert result["pool"]["eligible"][0]["key"] == "title:subnautica2"
    assert engine.game_key(game(title="Subnautica")) != engine.game_key(game(title="Subnautica 2"))


def test_empty_participants_spectate_until_they_add_games():
    state, _ = add()
    state, result = engine.transition(state, {}, context("two"), now=1001)
    assert result["pool"]["eligible"]
    assert result["pool"]["player_count"] == 1
    assert result["participants"][1]["spectating"] is True
    state, result = add(state, "two", title="Different game")
    assert not result["pool"]["eligible"]
    assert result["pool"]["player_count"] == 2


def test_unveto_restores_game_without_removing_other_users_vetoes():
    state, _ = add()
    state, _ = add(state, "two")
    for actor in ("one", "two"):
        state, _ = engine.transition(state, {"operation": "veto", "key": "title:together"}, context(actor), now=1001)
    state, result = engine.transition(state, {"operation": "clear-veto", "key": "title:together"}, context(), now=1002)
    assert not result["pool"]["eligible"]
    state, result = engine.transition(state, {"operation": "clear-veto", "key": "title:together"}, context("two"), now=1003)
    assert result["pool"]["eligible"]


def test_only_host_changes_matching_and_veto_survives_key_change():
    state, _ = add(provider_ids={"steam": "123"})
    state, _ = add(state, "two", provider_ids={"steam": "123"})
    options = {"title_fallback": False, "platform_aliases": True, "skip_empty": True}
    with pytest.raises(engine.SessionError, match="host"):
        engine.transition(state, {"operation": "matching", "matching": options}, context("two"), now=1001)
    state, _ = engine.transition(state, {"operation": "veto", "key": "title:together"}, context("two"), now=1001)
    state, result = engine.transition(state, {"operation": "matching", "matching": options}, context(), now=1002)
    assert not result["pool"]["eligible"]
    assert state["participants"]["two"]["vetoes"] == ["steam:123"]
