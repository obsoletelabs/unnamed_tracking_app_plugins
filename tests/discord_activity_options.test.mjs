import { test } from "node:test";
import assert from "node:assert/strict";
import { multiplayer, connectionScopes, trackingChange, gamePlatform, playerCountLabel } from "../official/discord-social-activity/ui/options.mjs";
import { canSaveCompatibility, saveCompatibilityTargets, summarizeSaveResults } from "../official/discord-social-activity/ui/library.mjs";
test("multiplayer detection uses available metadata without inventing unknown compatibility", () => {
  assert.equal(multiplayer({ features: ["Single-player", "Online Co-op"] }), true);
  assert.equal(multiplayer({ features: ["Multi-player"] }), true);
  assert.equal(multiplayer({ tags: ["MMORPG"] }), true);
  assert.equal(multiplayer({ features: ["Single-player"] }), false);
  assert.equal(multiplayer({ features: ["Full controller support"] }), null);
});

test("player-count labels preserve a known bound without inventing the other", () => {
  assert.equal(playerCountLabel({min_players: 2, max_players: 4}), "2–4 players");
  assert.equal(playerCountLabel({min_players: null, max_players: 4}), "Up to 4 players · minimum unknown");
  assert.equal(playerCountLabel({min_players: 2, max_players: null}), "At least 2 players · maximum unknown");
  assert.equal(playerCountLabel({min_players: null, max_players: null}), "Exact player limits unknown");
});

test("library consent stays minimal until the participant chooses progress features", () => {
  assert.deepEqual(connectionScopes(), ["profile.read", "games.read"]);
  assert.deepEqual(connectionScopes(false), ["profile.read", "games.read"]);
  assert.deepEqual(connectionScopes(true), ["profile.read", "games.read", "achievements.read", "tracking.write", "achievements.write"]);
});

test("a status update cannot clear a completion date without explicit date editing", () => {
  assert.deepEqual(trackingChange({status: "PLAYING", completion_date: ""}), {status: "PLAYING"});
  assert.deepEqual(trackingChange({status: "BEATEN", completion_date: "2026-10-14", edit_completion_date: true}), {status: "BEATEN", completion_date: 1791936000});
  assert.deepEqual(trackingChange({status: "BACKLOG", completion_date: "", edit_completion_date: true}), {status: "BACKLOG", completion_date: null});
});

test("Steam platform inference preserves an explicit platform and can be disabled", () => {
  assert.equal(gamePlatform({provider_ids: {steam: "264710"}}), "PC");
  assert.equal(gamePlatform({provider_ids: {steam: "264710"}}, false), "");
  assert.equal(gamePlatform({platform: "PS5", provider_ids: {steam: "264710"}}), "PS5");
  assert.equal(gamePlatform({provider_ids: {steam: "invalid"}}), "");
});

test("multiplayer writes need a separate opt-in scope and never use legacy keys", () => {
  assert.deepEqual(connectionScopes(false, true), ["profile.read", "games.read", "compatibility.write"]);
  assert.equal(canSaveCompatibility({state: "connected", scopes: ["tracking.write"]}), false);
  assert.equal(canSaveCompatibility({state: "connected", credential_kind: "legacy_api_key", scopes: ["compatibility.write"]}), false);
  assert.equal(canSaveCompatibility({state: "offline", scopes: ["compatibility.write"]}), false);
});

test("bulk settings preserve per-instance failures and cannot change an unapproved source", async () => {
  const sources = [
    {state: "connected", scopes: ["compatibility.write"], origin: "https://one.example"},
    {state: "connected", scopes: ["compatibility.write"], origin: "https://two.example"},
    {state: "connected", scopes: ["games.read"], origin: "https://three.example"},
  ];
  const targets = sources.map((source, index) => ({id: "g" + index, source_id: "s" + index, title: "Game", source}));
  const calls = [];
  const result = await saveCompatibilityTargets(targets, {min_players: null, max_players: null}, async (game, value) => {
    calls.push([game.id, value]);
    if (game.source_id === "s1") throw new Error("Instance unavailable");
  });
  assert.equal(calls.length, 2);
  assert.equal(result[0].error, undefined);
  assert.equal(result[1].error, "Instance unavailable");
  assert.match(result[2].error, /approve multiplayer/);
  assert.equal(result[1].origin, "https://two.example");
});

test("bulk presets keep a known play time and summarize each instance", async () => {
  const source = {state: "connected", scopes: ["compatibility.write"], origin: "https://one.example"};
  const saved = [];
  const results = await saveCompatibilityTargets([
    {id: "a", source_id: "s0", title: "A", source, play_compatibility: {min_players: 1, max_players: 2, duration_minutes: 45, source: "provider"}},
    {id: "b", source_id: "s0", title: "B", source},
  ], {min_players: 2, max_players: 4, duration_minutes: null, crossplay: true}, async (game, value) => { saved.push(value); });
  assert.equal(saved[0].duration_minutes, 45);
  assert.equal(saved[1].duration_minutes, null);
  assert.equal(saved[0].min_players, 2);
  const failing = [...results, {id: "c", source_id: "s1", origin: "https://two.example", error: "offline"}];
  assert.deepEqual(summarizeSaveResults(failing).map(e => [e.origin, e.saved, e.failed.length]), [["https://one.example", 2, 0], ["https://two.example", 0, 1]]);
});
