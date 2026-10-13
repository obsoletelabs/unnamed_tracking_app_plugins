export const platforms = ["PC", "Mac", "Linux", "PlayStation 5", "PlayStation 4", "Xbox Series X/S", "Xbox One", "Nintendo Switch", "Android", "iOS", "Browser", "Tabletop"];
export const genres = ["Action", "Adventure", "Arcade", "Card", "Casual", "Co-op", "Fighting", "Horror", "Party", "Platformer", "Puzzle", "Racing", "Roguelike", "RPG", "Sandbox", "Shooter", "Simulation", "Sports", "Strategy", "Survival"];
export const currencies = typeof Intl.supportedValuesOf === "function" ? Intl.supportedValuesOf("currency") : ["AUD", "CAD", "EUR", "GBP", "JPY", "NZD", "USD"];
export function combinedChoices(base, values) {
  return [...new Map([...base, ...values].filter(Boolean).map(value => [value.toLowerCase(), value])).values()].sort((a, b) => a.localeCompare(b));
}
export function multiplayer(game) {
  const labels = [...(game.features || []), ...(game.tags || [])].map(value => value.toLowerCase().replace(/[^a-z0-9]/g, ""));
  if (labels.some(value => /multiplayer|coop|onlinepvp|lanpvp|mmo/.test(value))) return true;
  if (labels.some(value => value === "singleplayer")) return false;
  return null;
}
export function connectionScopes(includeProgress = false) {
  return ["profile.read", "games.read", ...(includeProgress ? ["achievements.read", "tracking.write", "achievements.write"] : [])];
}
