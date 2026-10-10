(() => {
  const $ = (id) => document.getElementById(id);
  let context = {};
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
      window.parent.postMessage({ type: "plugin-api-request", requestId, method: "plugin.run-action", payload: { actionId, values: { ...values, _plugin_context: context } } }, "*");
    });
  }
  function api(method, payload = {}) {
    return new Promise((resolve, reject) => {
      const requestId = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `discord-api-${Date.now()}-${Math.random()}`;
      const timer = setTimeout(() => { window.removeEventListener("message", receive); reject(new Error("The host did not respond.")); }, 10000);
      function receive(event) {
        if (event.source !== window.parent || event.data?.type !== "plugin-api-response" || event.data.requestId !== requestId) return;
        clearTimeout(timer); window.removeEventListener("message", receive);
        if (event.data.error) reject(new Error(event.data.error)); else resolve(event.data.result || {});
      }
      window.addEventListener("message", receive);
      window.parent.postMessage({ type: "plugin-api-request", requestId, method, payload }, "*");
    });
  }
  async function save() {
    const value = $("webhook").value.trim();
    if (!value) throw new Error("Enter a Discord webhook URL.");
    await api("plugin.save-secret", { key: `webhooks/${context.user_id}`, value: JSON.stringify({ url: value }) });
    $("webhook").value = "";
    $("status").textContent = "Webhook saved.";
  }
  async function test() {
    const result = await request("test");
    $("status").textContent = result.message || "Test notification sent.";
  }
  async function clear() {
    await api("plugin.save-secret", { key: `webhooks/${context.user_id}`, value: "" });
    $("status").textContent = "Webhook removed.";
  }
  async function start() {
    try {
      const result = await api("plugin.context");
      context = { user_id: result.user_id };
      if (!context.user_id) throw new Error("The host did not provide a signed-in user context.");
    } catch (error) {
      $("error").textContent = error.message; $("error").hidden = false; return;
    }
    $("save").onclick = () => run(save);
    $("test").onclick = () => run(test);
    $("clear").onclick = () => run(clear);
  }
  async function run(operation) {
    $("error").hidden = true;
    try { await operation(); } catch (error) { $("error").textContent = error.message; $("error").hidden = false; }
  }
  void start();
})();
