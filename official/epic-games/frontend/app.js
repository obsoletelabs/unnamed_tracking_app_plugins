(() => {
  const $ = (id) => document.getElementById(id);
  let snapshot = { connected: false, phase: "idle" };
  let busy = false;
  let paused = false;
  const phases = { idle: "No import started.", inventory: "Reading your Epic inventory…", playtime: "Reading recorded playtime…", catalogue: "Looking up game details…", import: "Saving games to your library…", missing: "Checking availability against the complete inventory…", complete: "Import complete." };
  function request(actionId, values = {}) {
    return new Promise((resolve, reject) => {
      const requestId = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `epic-${Date.now()}-${Math.random()}`;
      const timer = setTimeout(() => { window.removeEventListener("message", receive); reject(new Error("The host did not respond. Resume to retry the saved step.")); }, 35000);
      function receive(event) {
        if (event.source !== window.parent || event.data?.type !== "plugin-api-response" || event.data.requestId !== requestId) return;
        clearTimeout(timer); window.removeEventListener("message", receive);
        const result = event.data.result || {};
        if (event.data.error || result.ok === false) reject(new Error(event.data.error || result.error || "The action could not complete. Resume to retry."));
        else resolve(result);
      }
      window.addEventListener("message", receive);
      window.parent.postMessage({ type: "plugin-api-request", requestId, method: "plugin.run-action", payload: { actionId, values } }, "*");
    });
  }
  function render() {
    $("account").textContent = snapshot.connected ? `Connected as ${snapshot.display_name}.` : "Connect your Epic account to start.";
    $("connect-panel").hidden = snapshot.connected;
    $("disconnect").hidden = !snapshot.connected;
    $("import").textContent = ["idle", "complete"].includes(snapshot.phase) ? "Import games" : "Resume import";
    for (const id of ["signin", "connect", "disconnect", "restart", "import"]) $(id).disabled = busy || (!["signin", "connect"].includes(id) && !snapshot.connected);
    $("pause").hidden = !busy;
    $("pause").disabled = paused;
    $("progress").textContent = (paused ? "Paused. " : "") + (phases[snapshot.phase] || "Import saved.");
    $("inventory-count").textContent = snapshot.inventory_count || 0;
    for (const field of ["imported", "skipped", "conflicts"]) $(field).textContent = snapshot[field] || 0;
    $("warning").hidden = !snapshot.warning; $("warning").textContent = snapshot.warning || "";
  }
  async function perform(work) {
    if (busy) return;
    busy = true; paused = false; $("error").hidden = true; render();
    try { await work(); }
    catch (error) { $("error").textContent = error.message; $("error").hidden = false; }
    finally { busy = false; render(); }
  }
  async function importGames(restart) {
    if (restart || ["idle", "complete"].includes(snapshot.phase)) snapshot = await request("start");
    render();
    while (!paused && snapshot.phase !== "complete") {
      snapshot = await request("step"); render();
    }
  }
  function connect() {
    if (busy) return;
    const authorization_code = $("code").value; $("code").value = "";
    void perform(async () => { snapshot = await request("connect", { authorization_code }); });
  }
  function signIn() {
    // Do not call window.open() from inside the sandbox. The declared
    // external_navigation action is handled by the host after the action
    // returns its validated redirect_url, so browser popup blockers are not
    // involved and the plugin does not need popup/same-origin privileges.
    if (busy) return;
    void perform(async () => { await request("signin"); });
  }
  // The host's opaque sandbox blocks native forms; use the action bridge.
  $("connect").onclick = connect;
  $("code").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.isComposing) {
      event.preventDefault(); connect();
    }
  });
  $("disconnect").onclick = () => perform(async () => { const result = await request("disconnect"); if (!result.cancelled) snapshot = result; });
  $("signin").onclick = signIn;
  $("import").onclick = () => perform(async () => importGames(false));
  $("restart").onclick = () => perform(async () => importGames(true));
  $("pause").onclick = () => { paused = true; $("pause").disabled = true; };
  void perform(async () => { snapshot = await request("status"); });
})();
