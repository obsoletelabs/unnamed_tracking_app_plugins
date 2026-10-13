import { test } from "node:test";
import assert from "node:assert/strict";
import { multiplayer, connectionScopes } from "../official/discord-social-activity/ui/options.mjs";
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
