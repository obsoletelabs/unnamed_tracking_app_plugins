const el = id => document.getElementById(id);
let registered = false, busy = false;
function request(method, payload = {}) {
 return new Promise((resolve, reject) => {
  const requestId = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `auth-${Date.now()}-${Math.random()}`;
  const timeout = setTimeout(() => { window.removeEventListener("message", receive); reject(new Error("The host did not respond. Try again.")); }, 30000);
  function receive(event) {
   if (event.source !== window.parent || event.data?.type !== "plugin-api-response" || event.data.requestId !== requestId) return;
   clearTimeout(timeout); window.removeEventListener("message", receive);
   const result = event.data.result || {};
   event.data.error || result.ok === false ? reject(new Error(event.data.error || result.error || "The action failed.")) : resolve(result);
  }
  window.addEventListener("message", receive);
  window.parent.postMessage({type:"plugin-api-request", requestId, method, payload}, "*");
 });
}
const action = (actionId, values = {}) => request("plugin.run-action", {actionId, values});
function duration(seconds) {
 const choices = [...el("unit").options].map(o => Number(o.value)).reverse();
 const unit = choices.find(value => seconds % value === 0) || 60;
 el("unit").value = String(unit); el("lifetime").value = String(seconds / unit);
}
function lifetime() {
 const seconds = Number(el("lifetime").value) * Number(el("unit").value);
 if (!Number.isInteger(seconds) || seconds < MINIMUM || seconds > MAXIMUM) throw new Error(LIFETIME_ERROR);
 return seconds;
}
function controls() {
 el("enable").disabled = busy || registered;
 el("disable").disabled = busy || !registered;
 el("save").disabled = busy;
 if (el("issue")) el("issue").disabled = busy || !registered;
 if (el("refresh")) el("refresh").disabled = busy;
}
async function run(operation, success = "") {
 if (busy) return;
 busy = true; controls(); feedback("");
 try { const result = await operation(); if (result?.cancelled) return; await refresh(); feedback(success); }
 catch (error) { feedback(error.message, true); }
 finally { busy = false; controls(); }
}
function control(formId, buttonId, callback, success) {
 const form = el(formId), button = el(buttonId);
 button.onclick = () => { if (form.reportValidity()) void run(callback, success); };
 form.onkeydown = event => { if (event.key === "Enter" && !event.isComposing && event.target.tagName !== "TEXTAREA") { event.preventDefault(); button.click(); } };
}
el("enable").onclick = () => run(() => action("enable"), "Enabled.");
el("disable").onclick = () => run(() => action("disable"), "Disabled. Outstanding links are invalidated.");
const MINIMUM = 3600, MAXIMUM = 604800, LIFETIME_ERROR = "Choose an invitation lifetime between 1 hour and 1 week.";
const invitationPage = new URLSearchParams(window.location.search).get("page") === "invite";
el("configuration-panel").hidden = invitationPage; el("invite-panel").hidden = !invitationPage;
const fields = ["sender_name", "email_subject", "email_heading", "welcome_message", "greeting", "button_label", "email_layout", "accent_color", "footer_message"];
function feedback(message, error = false) { const target = el(invitationPage ? "invite-feedback" : "feedback"); target.textContent = message; target.className = error ? "error" : ""; }
function preview() {
 el("preview-sender").textContent = el("sender_name").value || "Your configured SMTP sender";
 el("preview-heading").textContent = el("email_heading").value;
 el("preview-greeting").textContent = el("greeting").value === "personal" ? "Hi Alex," : el("greeting").value === "generic" ? "Hello," : "";
 el("preview-welcome").textContent = el("welcome_message").value;
 el("preview-button").textContent = el("button_label").value;
 el("preview-button").style.backgroundColor = el("accent_color").value;
 el("preview-footer").textContent = el("footer_message").value;
 el("preview").style.borderWidth = el("email_layout").value === "simple" ? "0" : "1px";
}
async function refresh() {
 const state = await action("status"); registered = state.registered === true;
 el("status").textContent = registered ? "Invitations enabled" : "Invitations disabled";
 el("status").className = registered ? "pill enabled" : "pill";
 el("invite-status").textContent = registered ? "Invitations enabled" : "Invitations are disabled. Enable them on the Users page before sending.";
 duration(state.token_lifetime_seconds); for (const key of fields) el(key).value = state[key] ?? ""; preview(); controls();
 const rows = registered && invitationPage ? (await action("list-invites")).invitations : [];
 el("invitations").replaceChildren();
 if (!rows.length) el("invitations").textContent = "No recent invitations.";
 for (const row of rows) {
  const article = document.createElement("article"), detail = document.createElement("div"), address = document.createElement("strong"), info = document.createElement("p");
  address.textContent = row.email;
  info.textContent = `${row.status} · Delivery: ${row.delivery_status || "unavailable"} · Expires ${new Date(row.expires_at * 1000).toLocaleString()}`;
  detail.append(address, info); article.append(detail);
  if (row.status === "pending") {
   const button = document.createElement("button"); button.type = "button"; button.className = "ghost danger"; button.textContent = "Revoke invitation";
   button.onclick = () => run(() => action("revoke", {id:row.id}), "Invitation revoked."); article.append(button);
  }
  el("invitations").append(article);
 }
}
control("configuration", "save", () => action("save", {token_lifetime_seconds:lifetime(), ...Object.fromEntries(fields.map(key => [key, el(key).value]))}), "Invitation settings saved.");
control("send", "issue", async () => { await action("issue", {email:el("email").value.trim(), recipient_name:el("recipient_name").value.trim()}); el("email").value = ""; el("recipient_name").value = ""; }, "Invitation queued. Check delivery below.");
el("refresh").onclick = () => run(async () => {}, "Status refreshed.");
for (const key of fields) el(key).oninput = preview;
refresh().catch(error => { feedback(error.message, true); for (const id of ["enable", "disable", "save", "issue"]) el(id).disabled = true; });
