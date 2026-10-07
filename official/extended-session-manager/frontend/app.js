const container = document.querySelector("#sessions");
const status = document.querySelector("#status");
function pluginRequest(method, payload = {}) {
  return new Promise((resolve, reject) => {
    const requestId = crypto.randomUUID();
    const timeout = setTimeout(() => {
      window.removeEventListener("message", onMessage);
      reject(new Error("The host did not respond."));
    }, 30000);
    function onMessage(event) {
      if (
        event.source !== window.parent ||
        event.data?.type !== "plugin-api-response" ||
        event.data.requestId !== requestId
      )
        return;
      clearTimeout(timeout);
      window.removeEventListener("message", onMessage);
      event.data.error
        ? reject(new Error(event.data.error))
        : resolve(event.data.result || {});
    }
    window.addEventListener("message", onMessage);
    window.parent.postMessage(
      { type: "plugin-api-request", requestId, method, payload },
      "*",
    );
  });
}
const when = (value) =>
  value == null ? "Unavailable" : new Date(value * 1000).toLocaleString();
function card(session) {
  const element = document.createElement("section");
  const title = document.createElement("h2");
  title.textContent = session.is_current
    ? "Current session"
    : session.state + " session";
  const details = document.createElement("p");
  details.textContent = [
    session.ip_address || "IP unavailable",
    session.user_agent || "Device unavailable",
    [
      session.location?.city,
      session.location?.region,
      session.location?.country,
    ]
      .filter(Boolean)
      .join(", "),
    session.location?.network_label,
    session.location?.network_number,
    session.location?.network_organization,
    "Created " + when(session.created_at),
    "Last activity " + when(session.last_seen_at),
    "Expires " + when(session.expires_at),
    session.anomaly?.reason,
  ]
    .filter(Boolean)
    .join(" | ");
  element.append(title, details);
  if (session.active && !session.is_current) {
    const button = document.createElement("button");
    button.textContent = "Revoke";
    button.onclick = async () => {
      button.disabled = true;
      try {
        const result = await pluginRequest("plugin.run-action", {
          actionId: "revoke-session",
          values: { session_id: session.id },
        });
        if (!result.cancelled) await refresh();
      } catch (error) {
        status.textContent = error.message;
      } finally {
        button.disabled = false;
      }
    };
    element.append(button);
  }
  return element;
}
async function refresh() {
  status.textContent = "Loading sessions...";
  try {
    const sessions = [];
    let cursor;
    do {
      const result = await pluginRequest("plugin.run-action", {
        actionId: "list-sessions",
        values: { limit: 200, ...(cursor ? { cursor } : {}) },
      });
      sessions.push(...result.sessions);
      cursor = result.next_cursor;
    } while (cursor);
    container.replaceChildren(...sessions.map(card));
    status.textContent = sessions.length + " browser sessions.";
  } catch (error) {
    status.textContent = error.message;
  }
}
document.querySelector("#refresh").onclick = refresh;
document.querySelector("#revoke-all").onclick = async () => {
  try {
    const result = await pluginRequest("plugin.run-action", {
      actionId: "revoke-all-sessions",
      values: {},
    });
    if (!result.cancelled) {
      container.replaceChildren();
      status.textContent = "All browser sessions revoked. Sign in again.";
    }
  } catch (error) {
    status.textContent = error.message;
  }
};
void refresh();
