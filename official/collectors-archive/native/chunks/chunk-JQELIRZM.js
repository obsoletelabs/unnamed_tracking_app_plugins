import {
  archiveAction
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/services/games.ts
function mapGame(raw) {
  const assets = raw.assets;
  const total = Number(raw.achievement_total ?? 0);
  return {
    id: String(raw.id),
    title: String(raw.title),
    status: String(raw.status).toLowerCase().replaceAll("_", " "),
    coverImageUrl: assets.key_art,
    bannerImageUrl: assets.banner,
    coverColor: "var(--ui-surface-2)",
    ratingOverall: raw.rating_overall == null ? null : Number(raw.rating_overall),
    ratingStory: raw.rating_story == null ? null : Number(raw.rating_story),
    ratingGameplay: raw.rating_gameplay == null ? null : Number(raw.rating_gameplay),
    ratingSound: raw.rating_soundtrack == null ? null : Number(raw.rating_soundtrack),
    achievementTotal: total,
    achievementPercent: total ? Number(raw.achievement_unlocked) / total * 100 : 0,
    achievements: [],
    description: raw.description,
    developer: raw.developer,
    publisher: raw.publisher,
    series: raw.series,
    tags: raw.tags,
    features: raw.features,
    source: raw.source,
    platform: raw.platform,
    collections: raw.collections ?? [],
    platforms: [{
      platform: String(raw.platform ?? raw.source ?? "PC"),
      source: String(raw.source ?? "manual"),
      playtimeMinutes: Number(raw.playtime_seconds ?? 0) / 60
    }],
    favorite: Boolean(raw.favorite),
    dateAdded: new Date(Number(raw.created_at) * 1e3).toISOString(),
    lastPlayedAt: raw.last_played_at ? new Date(Number(raw.last_played_at) * 1e3).toISOString() : null,
    timeToBeatHours: raw.time_to_beat_hours == null ? null : Number(raw.time_to_beat_hours),
    region: raw.region,
    language: raw.language,
    completionDate: raw.completion_date ? new Date(Number(raw.completion_date) * 1e3).toISOString() : null,
    releaseDate: raw.release_date
  };
}
async function fetchGames() {
  const games = [];
  let offset = 0;
  while (true) {
    const result = await archiveAction({ operation: "list", offset }, "games");
    games.push(...result.games.map(mapGame));
    if (result.complete) return games;
    offset = Number(result.next_offset);
  }
}
async function gameData(id) {
  const achievements = [];
  let offset = 0;
  while (true) {
    const result = await archiveAction({ operation: "get", game_id: id, offset }, "games");
    achievements.push(...result.achievements);
    if (result.complete) return { raw: result.game, achievements };
    offset = Number(result.next_offset);
  }
}
function mapAchievement(raw) {
  return {
    id: String(raw.id),
    name: String(raw.name),
    description: raw.description,
    unlockedAt: raw.unlocked ? new Date(Number(raw.unlocked_at ?? 0) * 1e3).toISOString() : null
  };
}
async function fetchGame(id) {
  const { raw, achievements } = await gameData(id);
  raw.achievement_total = achievements.length;
  raw.achievement_unlocked = achievements.filter((a) => a.unlocked).length;
  return { ...mapGame(raw), achievements: achievements.map(mapAchievement) };
}
async function fetchGameAchievements(id) {
  return (await gameData(id)).achievements.map(mapAchievement);
}

export {
  fetchGames,
  fetchGame,
  fetchGameAchievements
};
