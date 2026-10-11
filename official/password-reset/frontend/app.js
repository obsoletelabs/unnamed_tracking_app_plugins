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
const MINIMUM = 600, MAXIMUM = 3600, LIFETIME_ERROR = "Choose a recovery lifetime between 10 and 60 minutes.";
function feedback(message, error = false) { el("feedback").textContent = message; el("feedback").className = error ? "error" : ""; }
async function refresh() {
 const state = await action("status"); registered = state.registered === true;
 el("status").textContent = registered ? "Recovery enabled" : "Recovery disabled";
 el("status").className = registered ? "pill enabled" : "pill";
 duration(state.token_lifetime_seconds); controls();
}
control("configuration", "save", () => action("save", {token_lifetime_seconds:lifetime()}), "Recovery settings saved.");
refresh().catch(error => { feedback(error.message, true); for (const id of ["enable", "disable", "save"]) el(id).disabled = true; });
