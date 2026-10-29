import {
  mapBackendCard
} from "./chunk-AQDOIIHE.js";
import {
  pluginRequest
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/services/set.ts
function toIso(seconds) {
  return new Date(seconds * 1e3).toISOString();
}
function mapBackendSet(raw) {
  return {
    id: raw.id,
    name: raw.name,
    description: raw.description,
    targetTotal: raw.target_total,
    cardCount: raw.card_count,
    isComplete: raw.is_complete,
    createdAt: toIso(raw.created_at),
    updatedAt: toIso(raw.updated_at)
  };
}
function mapBackendSetDetail(raw) {
  return {
    ...mapBackendSet(raw),
    cards: raw.cards.map(mapBackendCard)
  };
}
async function handle(response, action) {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(`Failed to ${action}: ${response.status} ${message}`);
  }
  return response.json();
}
async function fetchSets() {
  const response = await pluginRequest("sets", { credentials: "include" });
  const raw = await handle(response, "fetch sets");
  return raw.map(mapBackendSet);
}
async function fetchSet(id) {
  const response = await pluginRequest(`sets/${id}`, { credentials: "include" });
  const raw = await handle(response, `fetch set ${id}`);
  return mapBackendSetDetail(raw);
}
async function createSet(input) {
  const response = await pluginRequest("sets", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: input.name,
      description: input.description ?? null,
      target_total: input.targetTotal ?? null
    })
  });
  const raw = await handle(response, "create set");
  return mapBackendSet(raw);
}
async function updateSet(id, input) {
  const body = {};
  if (input.name !== void 0) body.name = input.name;
  if (input.description !== void 0) body.description = input.description;
  if (input.targetTotal !== void 0) body.target_total = input.targetTotal;
  const response = await pluginRequest(`sets/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body)
  });
  const raw = await handle(response, `update set ${id}`);
  return mapBackendSet(raw);
}
async function deleteSet(id) {
  const response = await pluginRequest(`sets/${id}`, {
    method: "DELETE",
    credentials: "include"
  });
  if (!response.ok && response.status !== 204) {
    throw new Error(`Failed to delete set ${id}: ${response.status}`);
  }
}

export {
  fetchSets,
  fetchSet,
  createSet,
  updateSet,
  deleteSet
};
