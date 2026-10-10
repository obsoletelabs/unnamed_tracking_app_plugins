(() => {
  const $ = (id) => document.getElementById(id);
  function request(actionId, values = {}) {
    return new Promise((resolve, reject) => {
      const requestId = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `discord-${Date.now()}-${Math.random()}`;
      const timer = setTimeout(() => { window.removeEventListener("message", receive); reject(new Error("The host did not respond.")); }, 30000);
      function receive(event) {
        if (event.source !== window.parent || event.data?.type !== "plugin-api-response" || event.data.requestId !== requestId) return;
        clearTimeout(timer); window.removeEventListener("message", receive);
        if (event.data.error) reject(new Error(event.data.error)); else resolve(event.data.result || {});
      }
      window.addEventListener("message", receive);
      window.parent.postMessage({ type: "plugin-api-request", requestId, method: "plugin.run-action", payload: { actionId, values } }, "*");
    });
  }
  async function save() {
    const value = $("webhook").value.trim();
    if (!value) throw new Error("Enter a Discord webhook URL.");
    const result = await request("save-webhook", { url: value });
    $("webhook").value = "";
    $("status").textContent = result.message || "Discord webhook saved.";
  }
  async function test() {
    const result = await request("test");
    $("status").textContent = result.message || "Test notification sent.";
  }
  async function clear() {
    const result = await request("remove-webhook");
    $("status").textContent = result.message || "Discord webhook removed.";
  }
  async function run(operation) {
    $("error").hidden = true;
    try { await operation(); } catch (error) { $("error").textContent = error.message; $("error").hidden = false; }
  }
  $("save").onclick = () => run(save);
  $("test").onclick = () => run(test);
  $("clear").onclick = () => run(clear);
})();
