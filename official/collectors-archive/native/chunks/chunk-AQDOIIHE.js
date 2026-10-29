import {
  pluginRequest
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/services/cards.ts
function toIso(seconds) {
  return new Date(seconds * 1e3).toISOString();
}
function mapBackendCard(raw) {
  return {
    id: raw.id,
    gameId: raw.game_id,
    archiveNumber: raw.archive_number,
    setId: raw.set_id,
    rarity: raw.rarity,
    bountyId: raw.bounty_id,
    cardCustomization: raw.card_customization,
    status: raw.status,
    createdAt: toIso(raw.created_at),
    updatedAt: toIso(raw.updated_at)
  };
}
async function handle(response, action) {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(`Failed to ${action}: ${response.status} ${message}`);
  }
  return response.json();
}
async function listCards(filters) {
  const params = new URLSearchParams();
  if (filters?.gameId) params.set("game_id", filters.gameId);
  if (filters?.setId) params.set("set_id", filters.setId);
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await pluginRequest(`cards${query}`, {
    credentials: "include"
  });
  const raw = await handle(response, "list cards");
  return raw.map(mapBackendCard);
}
async function getCard(id) {
  const response = await pluginRequest(`cards/${id}`, { credentials: "include" });
  const raw = await handle(response, `fetch card ${id}`);
  return mapBackendCard(raw);
}
async function createCard(input) {
  const response = await pluginRequest("cards", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      game_id: input.gameId,
      set_id: input.setId ?? null,
      rarity: input.rarity ?? null,
      card_customization: input.cardCustomization ?? null
    })
  });
  const raw = await handle(response, "create card");
  return mapBackendCard(raw);
}
async function updateCard(id, fields) {
  const body = {};
  if ("setId" in fields) body.set_id = fields.setId;
  if ("rarity" in fields) body.rarity = fields.rarity;
  if ("cardCustomization" in fields)
    body.card_customization = fields.cardCustomization;
  if ("status" in fields) body.status = fields.status;
  const response = await pluginRequest(`cards/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const raw = await handle(response, `update card ${id}`);
  return mapBackendCard(raw);
}
async function generatePrestigeChallenge(id) {
  const response = await pluginRequest(`cards/${id}/prestige-challenge`, {
    method: "POST",
    credentials: "include"
  });
  const raw = await handle(
    response,
    `generate prestige challenge for card ${id}`
  );
  return mapBackendCard(raw);
}

export {
  mapBackendCard,
  listCards,
  getCard,
  createCard,
  updateCard,
  generatePrestigeChallenge
};
