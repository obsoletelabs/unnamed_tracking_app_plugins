import { test } from "node:test";
import assert from "node:assert/strict";
import { multiplayer, connectionScopes, trackingChange } from "../official/discord-social-activity/ui/options.mjs";
test("multiplayer detection uses available metadata without inventing unknown compatibility", () => {
  assert.equal(multiplayer({ features: ["Single-player", "Online Co-op"] }), true);
  assert.equal(multiplayer({ features: ["Multi-player"] }), true);
  assert.equal(multiplayer({ tags: ["MMORPG"] }), true);
  assert.equal(multiplayer({ features: ["Single-player"] }), false);
  assert.equal(multiplayer({ features: ["Full controller support"] }), null);
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
