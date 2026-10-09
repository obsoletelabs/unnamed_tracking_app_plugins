// Public appearance and keyboard bridge. Sandboxed plugins remain opaque origins.
(() => {
  let navigationKeys = new Set();
  let globalKeys = new Set();
  let bindings = null;
  function apply(appearance) {
    if (!appearance || !["1.1.0", "1.1.1", "1.1.2"].includes(appearance.api_contract_version) ||
        !["light", "dark"].includes(appearance.mode) || !appearance.tokens) return;
    const root = document.documentElement;
    navigationKeys = new Set(Array.isArray(appearance.navigation_shortcuts)
      ? appearance.navigation_shortcuts.filter(key => typeof key === "string" && /^[a-z]$/.test(key)) : []);
    globalKeys = new Set(Array.isArray(appearance.global_shortcuts)
      ? appearance.global_shortcuts.filter(key => key === "help" || key === "search") : []);
    bindings = Array.isArray(appearance.keyboard_shortcuts) ? appearance.keyboard_shortcuts.filter(item =>
      item && typeof item.id === "string" && item.id.length <= 300 && typeof item.key === "string" && item.key.length <= 64) : null;
    root.style.colorScheme = appearance.mode;
    root.dataset.theme = appearance.mode;
    root.classList.toggle("high-contrast", appearance.high_contrast === true);
    root.classList.toggle("reduce-motion", appearance.reduce_motion === true);
    for (const [name, value] of Object.entries(appearance.tokens)) {
      if (/^--ui-[a-z-]+$/.test(name) && typeof value === "string" && value.length < 512)
        root.style.setProperty(name, value);
    }
  }
  // Correlation identifiers are not credentials; HTTP previews may lack randomUUID.
  const identifier = () => typeof crypto.randomUUID === "function"
    ? crypto.randomUUID() : `appearance-${Date.now()}-${Math.random().toString(36).slice(2)}`;
  const requestId = identifier();
  window.addEventListener("message", event => {
    if (event.source !== window.parent) return;
    if (event.data?.type === "plugin-appearance-changed") apply(event.data.appearance);
    if (event.data?.type === "plugin-api-response" && event.data.requestId === requestId)
      apply(event.data.result);
  });
  window.parent.postMessage({ type: "plugin-api-request", requestId,
    method: "plugin.theme", payload: {} }, "*");
  window.addEventListener("keydown", event => {
    if (event.isComposing || event.repeat || event.defaultPrevented || event.getModifierState("AltGraph")) return;
    if (event.target?.closest?.("input, textarea, select, [role=combobox]") || event.target?.isContentEditable) return;
    const letter = /^[a-z]$/i.test(event.key) ? event.key.toLowerCase()
      : /^Key[A-Z]$/.test(event.code) ? event.code.slice(3).toLowerCase() : "";
    if (bindings) {
      const binding = bindings.find(item => {
        const parts = item.key.split("+"), key = parts.pop(), portable = parts.includes("CtrlOrMeta");
        if (portable ? event.ctrlKey === event.metaKey
          : event.ctrlKey !== parts.includes("Ctrl") || event.metaKey !== parts.includes("Meta")) return false;
        if (event.altKey !== parts.includes("Alt") || (key !== "?" && event.shiftKey !== parts.includes("Shift"))) return false;
        const actual = event.key === " " ? "Space" : event.key === "+" ? "Plus" : event.key;
        return actual.toUpperCase() === key.toUpperCase() || (event.altKey && /^[A-Z]$/.test(key) && event.code === `Key${key}`);
      });
      if (!binding) return;
      event.preventDefault();
      window.parent.postMessage({ type: "plugin-api-request", requestId: identifier(),
        method: "plugin.shortcut", payload: binding }, "*");
      return;
    }
    const key = event.altKey && !event.ctrlKey && !event.metaKey && !event.shiftKey && navigationKeys.has(letter) ? letter
      : !event.altKey && !event.ctrlKey && !event.metaKey && event.key === "?" && globalKeys.has("help") ? "help"
      : !event.altKey && !event.shiftKey && (event.ctrlKey || event.metaKey) && letter === "k" && globalKeys.has("search") ? "search" : "";
    if (!key) return;
    event.preventDefault();
    window.parent.postMessage({ type: "plugin-api-request", requestId: identifier(),
      method: "plugin.shortcut", payload: { key } }, "*");
  });
  if (typeof ResizeObserver === "function") {
    let previous = 0;
    const observe = () => new ResizeObserver(() => {
        const height = Math.ceil(document.body.getBoundingClientRect().height);
        if (height === previous) return;
        previous = height;
        window.parent.postMessage({ type: "plugin-api-request", requestId: identifier(),
          method: "plugin.resize", payload: { height } }, "*");
      }).observe(document.body);
    if (document.body) observe();
    else window.addEventListener("DOMContentLoaded", observe, { once: true });
  }
})();
