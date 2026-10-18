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


def test_saved_group_details_are_used_without_changing_live_access_checks():
    library = [{"id": "g1", "title": "Together", "owned": True, "source_id": "source",
                "platform": "Windows", "tags": ["Co-op"], "source_state": "connected",
                "play_compatibility": {"min_players": 1, "max_players": 4,
                                       "duration_minutes": 45, "crossplay": False}}]
    ctx = context(library=library, source_states={"source": "connected"}, connected=True)
    state, result = engine.transition(None, {}, ctx, now=1000)
    assert result["pool"]["eligible"][0]["access"][0]["compatibility"] == "self_reported"
    state, result = engine.transition(state, {}, context(connected=True, library=library,
        source_states={"source": "revoked"}), now=1001)
    assert not result["pool"]["eligible"]


def test_owned_multiplayer_is_automatic_but_unknown_player_limits_are_not_invented():
    library = [{"id": "g1", "title": "Together", "owned": True, "source_id": "source",
                "platform": "PC", "tags": [], "features": ["Online Co-op"],
                "source_state": "connected"}]
    ctx = context(library=library, source_states={"source": "connected"}, connected=True)
    state, result = engine.transition(None, {"operation": "matching", "matching": {
        **engine.MATCHING_DEFAULTS, "small_multiplayer": False}}, ctx, now=1000)
    assert len(result["pool"]["excluded"]) == 1
    assert "player count" in result["pool"]["excluded"][0]["excluded_reasons"][0]
    assert not result["participants"][0]["spectating"]
    assert not result["me"]["manual"]
    state, result = engine.transition(state, {"operation": "manual", "game": game()}, ctx, now=1001)
    assert result["pool"]["eligible"]


def multiplayer_context(actor="one", **changes):
    library = [{"id": "g1", "title": "Together", "owned": True, "source_id": "source",
                "platform": "PC", "features": ["Online Co-op"], "tags": [],
                "source_state": "connected", "provider_ids": {"steam": "123"}}]
    return context(actor, library=library, source_states={"source": "connected"},
                   connected=True, **changes)


def test_one_participant_can_confirm_player_limits_for_every_owner():
    state, _ = engine.transition(None, {}, multiplayer_context(), now=1000)
    state, before = engine.transition(state, {}, multiplayer_context("two"), now=1001)
    assert before["pool"]["eligible"][0]["needs_player_limits"]
    state, result = engine.transition(state, {"operation": "player-limits", "key": "title:together",
        "min_players": 2, "max_players": 4}, multiplayer_context("two"), now=1002)
    candidate = result["pool"]["eligible"][0]
    assert candidate["player_limits"]["confirmed_by"] == "two"
    assert len(candidate["access"]) == 2
    assert not state["participants"]["one"]["manual"]
    state, result = engine.transition(state, {}, multiplayer_context(), now=1003)
    assert result["pool"]["eligible"]
    state, result = engine.transition(state, {"operation": "veto", "key": "title:together"},
                                      multiplayer_context(), now=1004)
    assert not result["pool"]["eligible"]


def test_existing_manual_confirmation_supplies_missing_limits_but_not_personal_rules():
    state, _ = add()
    state, result = engine.transition(state, {}, multiplayer_context("two"), now=1001)
    assert result["pool"]["eligible"]
    state, result = engine.transition(state, {"operation": "preferences", "preferences": {
        "max_minutes": 30}}, multiplayer_context("two"), now=1002)
    assert not result["pool"]["eligible"]
    assert "session length" in " ".join(result["pool"]["excluded"][0]["excluded_reasons"])


@pytest.mark.parametrize("minimum,maximum", [(True, 4), (0, 4), (4, 2), (1, 33), (1, None)])
def test_shared_limits_validate_counts(minimum, maximum):
    state, _ = engine.transition(None, {}, multiplayer_context(), now=1000)
    with pytest.raises(engine.SessionError, match="player range"):
        engine.transition(state, {"operation": "player-limits", "key": "title:together",
            "min_players": minimum, "max_players": maximum}, multiplayer_context(), now=1001)


def test_shared_limits_cannot_invent_games_or_restore_revoked_ownership():
    state, _ = engine.transition(None, {}, multiplayer_context(), now=1000)
    with pytest.raises(engine.SessionError, match="room"):
        engine.transition(state, {"operation": "player-limits", "key": "title:absent",
            "min_players": 1, "max_players": 4}, multiplayer_context(), now=1001)
    state, _ = engine.transition(state, {"operation": "player-limits", "key": "title:together",
        "min_players": 1, "max_players": 4}, multiplayer_context(), now=1002)
    ctx = multiplayer_context()
    ctx["source_states"] = {"source": "revoked"}
    _, result = engine.transition(state, {}, ctx, now=1003)
    assert not result["pool"]["eligible"]
    assert "access unavailable" in " ".join(result["pool"]["excluded"][0]["excluded_reasons"])


def test_shared_limits_survive_matching_changes_and_still_check_platforms():
    state, _ = engine.transition(None, {}, multiplayer_context(), now=1000)
    state, _ = engine.transition(state, {"operation": "player-limits", "key": "title:together",
        "min_players": 1, "max_players": 4}, multiplayer_context(), now=1001)
    state, result = engine.transition(state, {"operation": "matching", "matching": {
        "title_fallback": False, "platform_aliases": True, "skip_empty": True}},
        multiplayer_context(), now=1002)
    assert result["pool"]["eligible"][0]["key"] == "steam:123"
    other = multiplayer_context("two")
    other["library"][0]["platform"] = "PlayStation 5"
    _, result = engine.transition(state, {}, other, now=1003)
    assert not result["pool"]["eligible"]
    assert "Cross-platform" in " ".join(result["pool"]["excluded"][0]["excluded_reasons"])


def test_shared_counts_still_exclude_large_groups_and_nonowners():
    state, _ = engine.transition(None, {}, multiplayer_context(), now=1000)
    state, _ = engine.transition(state, {}, multiplayer_context("two"), now=1001)
    state, result = engine.transition(state, {"operation": "player-limits", "key": "title:together",
        "min_players": 1, "max_players": 1}, multiplayer_context(), now=1002)
    assert not result["pool"]["eligible"]
    assert "player-count rule" in " ".join(result["pool"]["excluded"][0]["excluded_reasons"])
    other = multiplayer_context("two")
    other["library"][0]["owned"] = False
    other["library"].append({**other["library"][0], "id": "other", "title": "Other", "owned": True})
    state, result = engine.transition(state, {"operation": "player-limits", "key": "title:together",
        "min_players": 1, "max_players": 4}, other, now=1003)
    assert not result["pool"]["eligible"]
    together = next(game for game in result["pool"]["excluded"] if game["key"] == "title:together")
    assert "access unavailable" in " ".join(together["excluded_reasons"])


def test_missing_platform_can_be_confirmed_inline_for_only_the_current_participant():
    first, second = multiplayer_context(), multiplayer_context("two")
    first["library"][0]["platform"] = None
    second["library"][0]["platform"] = None
    first["library"][0]["provider_ids"] = {}
    second["library"][0]["provider_ids"] = {}
    state, _ = engine.transition(None, {}, first, now=1000)
    state, _ = engine.transition(state, {}, second, now=1001)
    state, result = engine.transition(state, {"operation": "player-limits", "key": "title:together",
        "min_players": 2, "max_players": 4, "platform": "PC", "participant_id": "two"}, first, now=1002)
    candidate = result["pool"]["excluded"][0]
    assert candidate["missing_platforms"] == ["two"]
    assert candidate["player_limits"]["confirmed_by"] == "one"
    assert not state["participants"]["two"].get("platform_overrides")
    state, result = engine.transition(state, {"operation": "player-limits", "key": "title:together",
        "min_players": 2, "max_players": 4, "platform": "Windows"}, second, now=1003)
    assert len(result["pool"]["eligible"][0]["access"]) == 2
    assert result["pool"]["eligible"][0]["player_limits"]["confirmed_by"] == "one"
    state, result = engine.transition(state, {}, first, now=1004)
    assert result["pool"]["eligible"]
    state, _ = engine.transition(state, {"operation": "leave"}, first, now=1005)
    assert state["participants"]["one"]["platform_overrides"] == []
    assert first["library"][0]["platform"] is None


def test_saved_player_counts_do_not_need_reentry_when_only_the_platform_is_missing():
    ctx = multiplayer_context()
    ctx["library"][0]["provider_ids"] = {}
    ctx["library"][0].update(platform=None, play_compatibility={
        "min_players": 1, "max_players": 4, "duration_minutes": 45, "crossplay": False})
    state, result = engine.transition(None, {}, ctx, now=1000)
    candidate = result["pool"]["excluded"][0]
    assert not candidate["needs_player_limits"]
    assert candidate["missing_platforms"] == ["one"]
    _, result = engine.transition(state, {"operation": "player-limits", "key": "title:together",
        "min_players": 1, "max_players": 4, "platform": "PC"}, ctx, now=1001)
    assert result["pool"]["eligible"]


@pytest.mark.parametrize("platform", ["", " ", "x" * 81, True, []])
def test_invalid_inline_platform_is_rejected(platform):
    state, _ = engine.transition(None, {}, multiplayer_context(), now=1000)
    with pytest.raises(engine.SessionError, match="platform"):
        engine.transition(state, {"operation": "player-limits", "key": "title:together",
            "min_players": 1, "max_players": 4, "platform": platform}, multiplayer_context(), now=1001)


def test_only_singleplayer_or_wishlist_imports_do_not_block_the_group():
    state, _ = add()
    library = [{"id": "g1", "title": "Single", "owned": True, "source_id": "source",
                "features": ["Single-player"], "tags": [], "source_state": "connected"},
               {"id": "g2", "title": "Wishlist", "owned": False, "source_id": "source",
                "features": ["Multi-player"], "tags": [], "source_state": "connected"}]
    _, result = engine.transition(state, {}, context("two", library=library,
        source_states={"source": "connected"}, connected=True), now=1001)
    assert len(result["pool"]["eligible"]) == 1
    assert next(person for person in result["participants"] if person["id"] == "two")["spectating"]


def test_source_titles_and_missing_metadata_do_not_break_automatic_imports():
    library = [{"id": "g1", "title": "Long title " * 30, "owned": True,
                "source_id": "source", "platform": "PC", "tags": None,
                "features": ["Online Co-op"], "source_state": "connected"}]
    _, result = engine.transition(None, {}, context(library=library,
        source_states={"source": "connected"}, connected=True), now=1000)
    assert len(result["pool"]["eligible"]) == 1
    assert result["pool"]["eligible"][0]["player_limits"] is None
    assert not result["participants"][0]["spectating"]
    with pytest.raises(engine.SessionError, match="200 characters"):
        engine.manual_game(game(title="x" * 201))


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


def test_two_player_multiplayer_is_eligible_without_inventing_limits():
    first, second = multiplayer_context(), multiplayer_context("two")
    first["library"][0]["platform"] = None
    second["library"][0]["platform"] = None
    state, _ = engine.transition(None, {}, first, now=1000)
    state, result = engine.transition(state, {}, second, now=1001)
    candidate = result["pool"]["eligible"][0]
    assert candidate["player_limits"] is None
    assert candidate["needs_player_limits"] and not candidate["requires_player_limits"]
    assert all(person["platform"] == "PC" for person in candidate["access"])
    assert all(person["platform_provenance"] == "inferred_steam" for person in candidate["access"])
    assert all(person["compatibility"] == "detected_multiplayer" for person in candidate["access"])
    assert "unknown" in " ".join(candidate["reasons"])
    state, result = engine.transition(state, {}, multiplayer_context("three"), now=1002)
    assert not result["pool"]["eligible"]
    assert result["pool"]["excluded"][0]["requires_player_limits"]


def test_small_group_policy_never_overrides_known_limits_or_platforms():
    state, _ = add(max_players=1)
    state, result = engine.transition(state, {}, multiplayer_context("two"), now=1001)
    assert not result["pool"]["eligible"]
    first = multiplayer_context()
    first["library"][0]["platform"] = "PlayStation 5"
    _, result = engine.transition(None, {}, first, now=1000)
    assert result["pool"]["eligible"][0]["access"][0]["platform"] == "PlayStation 5"


def test_host_can_disable_both_inferences():
    ctx = multiplayer_context()
    ctx["library"][0]["platform"] = None
    _, result = engine.transition(None, {"operation": "matching", "matching": {
        **engine.MATCHING_DEFAULTS, "small_multiplayer": False, "steam_platform": False}}, ctx, now=1000)
    assert not result["pool"]["eligible"]


def test_bulk_group_approval_needs_no_metadata_and_expires_when_party_size_changes():
    state, _ = engine.transition(None, {}, multiplayer_context(), now=1000)
    state, _ = engine.transition(state, {}, multiplayer_context("two"), now=1001)
    state, _ = engine.transition(state, {}, multiplayer_context("three"), now=1002)
    state, result = engine.transition(state, {"operation": "approve-group", "keys": ["title:together"]}, multiplayer_context("two"), now=1003)
    candidate = result["pool"]["eligible"][0]
    assert candidate["player_limits"] is None
    assert candidate["group_approval"] == {"players": 3, "confirmed_by": "two"}
    state, result = engine.transition(state, {}, multiplayer_context("four"), now=1004)
    assert not result["pool"]["eligible"]
    state, _ = add(max_players=1)
    state, _ = engine.transition(state, {}, multiplayer_context("two"), now=1001)
    _, result = engine.transition(state, {"operation": "approve-group", "keys": ["title:together"]}, multiplayer_context(), now=1002)
    assert not result["pool"]["eligible"]


@pytest.mark.parametrize("keys", [[], ["title:absent"], ["title:together", "title:together"], [True]])
def test_bulk_group_approval_rejects_invalid_targets(keys):
    state, _ = engine.transition(None, {}, multiplayer_context(), now=1000)
    with pytest.raises(engine.SessionError):
        engine.transition(state, {"operation": "approve-group", "keys": keys}, multiplayer_context(), now=1001)


def test_multiplayer_marker_without_limits_is_a_labeled_small_group_signal():
    ctx = multiplayer_context()
    ctx["library"][0].update(features=[], play_compatibility={"min_players": None, "max_players": None, "crossplay": False})
    _, result = engine.transition(None, {}, ctx, now=1000)
    assert result["pool"]["eligible"][0]["player_limits"] is None


def test_copies_grouped_on_an_instance_match_by_the_games_main_title():
    """Host #274: delegated libraries mark copies of one game with its main title."""
    windows = game(title="Minecraft for Windows",
                   identity={"group_id": "g1", "is_main": False, "main_title": "Minecraft"})
    assert engine.game_key(windows) == engine.game_key(game(title="Minecraft"))
    assert engine.game_key(game(title="Minecraft for Windows", identity={"main_title": " "})) == "title:minecraftforwindows"
    assert engine.game_key(game(title="Hades", identity="not-a-dict")) == "title:hades"
    # A participant's imported copy meets another participant's manual "Minecraft".
    state, _ = add(title="Minecraft")
    library = [{"id": "g2", "title": "Minecraft for Windows", "owned": True, "source_id": "source",
                "source_state": "connected", "ownership_provenance": "instance_library",
                "platforms": ["PC"], "min_players": 1, "max_players": 4, "genres": ["Co-op"],
                "identity": {"group_id": "g2", "is_main": False, "main_title": "Minecraft"}}]
    ctx = context("two", library=library, source_states={"source": "connected"}, connected=True)
    state, result = engine.transition(state, {}, ctx, now=1001)
    keys = {key for person in state["participants"].values()
            for key in [engine.game_key(g, state["matching"]) for g in person["library"] + person["manual"]]}
    assert keys == {"title:minecraft"}
