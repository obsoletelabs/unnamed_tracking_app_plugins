export function canSaveCompatibility(source) {
  return source?.state === "connected" && source.credential_kind !== "legacy_api_key" && source.scopes?.includes("compatibility.write");
}
export async function saveCompatibilityTargets(targets, preset, save) {
  const results = [];
  for (const game of targets) {
    const result = { id: game.id, source_id: game.source_id, title: game.title, origin: game.source?.origin };
    try {
      if (!canSaveCompatibility(game.source)) throw new Error("Reconnect and approve multiplayer settings access first.");
      await save(game, preset);
    } catch (error) { result.error = error.message || "Unable to save this game."; }
    results.push(result);
  }
  return results;
}
