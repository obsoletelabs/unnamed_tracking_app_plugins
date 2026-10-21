export function canSaveCompatibility(source) {
  return source?.state === "connected" && source.credential_kind !== "legacy_api_key" && source.scopes?.includes("compatibility.write");
}
export function presetForGame(game, preset) {
  // A bulk save changes player limits and crossplay only; a known play time stays.
  return preset && { ...preset, duration_minutes: game.play_compatibility?.duration_minutes ?? null };
}
export function summarizeSaveResults(results) {
  const sources = new Map();
  for (const result of results) {
    const entry = sources.get(result.source_id) || { origin: result.origin, saved: 0, failed: [] };
    if (result.error) entry.failed.push(result); else entry.saved += 1;
    sources.set(result.source_id, entry);
  }
  return [...sources.values()];
}
export async function saveCompatibilityTargets(targets, preset, save) {
  const results = [];
  for (const game of targets) {
    const result = { id: game.id, source_id: game.source_id, title: game.title, origin: game.source?.origin };
    try {
      if (!canSaveCompatibility(game.source)) throw new Error("Reconnect and approve multiplayer settings access first.");
      await save(game, presetForGame(game, preset));
    } catch (error) { result.error = error.message || "Unable to save this game."; }
    results.push(result);
  }
  return results;
}
