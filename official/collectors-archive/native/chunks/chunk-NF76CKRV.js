import {
  pluginRequest
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/services/bounties.ts
async function handle(response, action) {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      body?.detail || `Failed to ${action}: ${response.status} ${response.statusText}`
    );
  }
  return response.json();
}
async function fetchBounties(filters) {
  if (false) return [];
  const params = new URLSearchParams();
  if (filters?.status) params.set("status", filters.status);
  if (filters?.type) params.set("type", filters.type);
  const query = params.toString() ? `?${params.toString()}` : "";
  const response = await pluginRequest(`bounties${query}`, {
    credentials: "include"
  });
  const body = await handle(response, "fetch bounties");
  return body.bounties;
}
async function fetchBounty(id) {
  const response = await pluginRequest(`bounties/${id}`, {
    credentials: "include"
  });
  const body = await handle(response, "fetch bounty");
  return body.bounty;
}
async function createBounty(input) {
  const response = await pluginRequest("bounties", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
  const body = await handle(response, "create bounty");
  return body.bounty;
}
async function updateBounty(id, input) {
  const response = await pluginRequest(`bounties/${id}`, {
    method: "PATCH",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
  const body = await handle(response, "update bounty");
  return body.bounty;
}
async function completeBounty(id) {
  await handle(
    await pluginRequest(`bounties/${id}/complete`, {
      method: "POST",
      credentials: "include"
    }),
    "complete bounty"
  );
}
async function pauseBounty(id) {
  await handle(
    await pluginRequest(`bounties/${id}/pause`, {
      method: "POST",
      credentials: "include"
    }),
    "pause bounty"
  );
}
async function resumeBounty(id) {
  await handle(
    await pluginRequest(`bounties/${id}/resume`, {
      method: "POST",
      credentials: "include"
    }),
    "resume bounty"
  );
}
async function abandonBounty(id) {
  await handle(
    await pluginRequest(`bounties/${id}/abandon`, {
      method: "POST",
      credentials: "include"
    }),
    "abandon bounty"
  );
}
async function deleteBounty(id) {
  await handle(
    await pluginRequest(`bounties/${id}`, {
      method: "DELETE",
      credentials: "include"
    }),
    "delete bounty"
  );
}
async function fetchPointsTotal() {
  const response = await pluginRequest("bounties/points/total", {
    credentials: "include"
  });
  const body = await handle(response, "fetch points total");
  return body.total;
}
async function fetchPointsHistory() {
  const response = await pluginRequest("bounties/points/history", {
    credentials: "include"
  });
  const body = await handle(
    response,
    "fetch points history"
  );
  return body.transactions;
}
async function createObjective(bountyId, input) {
  const response = await pluginRequest(`bounties/${bountyId}/objectives`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
  const body = await handle(response, "create objective");
  return body.bounty;
}
async function updateObjective(bountyId, objectiveId, input) {
  const response = await pluginRequest(
    `bounties/${bountyId}/objectives/${objectiveId}`,
    {
      method: "PATCH",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    }
  );
  const body = await handle(response, "update objective");
  return body.bounty;
}
async function deleteObjective(bountyId, objectiveId) {
  await handle(
    await pluginRequest(`bounties/${bountyId}/objectives/${objectiveId}`, {
      method: "DELETE",
      credentials: "include"
    }),
    "delete objective"
  );
}
async function createEvidence(bountyId, input) {
  const response = await pluginRequest(`bounties/${bountyId}/evidence`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input)
  });
  const body = await handle(
    response,
    "create evidence"
  );
  return body.evidence;
}
async function deleteEvidence(bountyId, evidenceId) {
  await handle(
    await pluginRequest(`bounties/${bountyId}/evidence/${evidenceId}`, {
      method: "DELETE",
      credentials: "include"
    }),
    "delete evidence"
  );
}
async function createJournalEntry(bountyId, text) {
  const response = await pluginRequest(`bounties/${bountyId}/journal`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text })
  });
  const body = await handle(
    response,
    "add journal entry"
  );
  return body.entry;
}
async function deleteJournalEntry(bountyId, entryId) {
  await handle(
    await pluginRequest(`bounties/${bountyId}/journal/${entryId}`, {
      method: "DELETE",
      credentials: "include"
    }),
    "delete journal entry"
  );
}
async function fetchRandomBountyProposal() {
  const response = await pluginRequest("bounties/random", {
    credentials: "include"
  });
  const body = await handle(
    response,
    "fetch random bounty"
  );
  return body.proposal;
}

export {
  fetchBounties,
  fetchBounty,
  createBounty,
  updateBounty,
  completeBounty,
  pauseBounty,
  resumeBounty,
  abandonBounty,
  deleteBounty,
  fetchPointsTotal,
  fetchPointsHistory,
  createObjective,
  updateObjective,
  deleteObjective,
  createEvidence,
  deleteEvidence,
  createJournalEntry,
  deleteJournalEntry,
  fetchRandomBountyProposal
};
