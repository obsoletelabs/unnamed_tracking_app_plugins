import {
  configure,
  configureHost,
  defineAsyncComponent,
  defineComponent,
  h,
  host,
  onBeforeUnmount,
  onMounted,
  pluginRequest,
  provide,
  ref
} from "./chunks/chunk-2UKGPRFR.js";

// official/collectors-archive/ui/app.ts
var TABLES = ["sets", "bounties", "cards", "bounty_objectives", "bounty_evidence", "bounty_journal_entries", "bounty_point_transactions"];
async function activate(context) {
  configure(context);
  configure(context);
  configureHost(context);
  let stylesheet;
  let stylesReady;
  function ensureStyles() {
    if (stylesReady) return stylesReady;
    stylesReady = new Promise((resolve, reject) => {
      const link = document.createElement("link");
      stylesheet = link;
      link.rel = "stylesheet";
      link.href = new URL("./style.css", import.meta.url).href;
      link.onload = () => resolve();
      link.onerror = () => {
        link.remove();
        stylesheet = void 0;
        stylesReady = void 0;
        reject(new Error("Archive styles could not be loaded. Reopen this page to retry."));
      };
      document.head.appendChild(link);
    });
    return stylesReady;
  }
  context.onCleanup?.(() => stylesheet?.remove());
  context.host.registerSearchProvider?.(async (query) => {
    if (!(await host().runAction("migration-status")).imported) return [];
    const response = await pluginRequest("bounties");
    if (!response.ok) throw new Error("Archive search unavailable.");
    const body = await response.json();
    return body.bounties.filter((item) => item.title.toLowerCase().includes(query.toLowerCase())).slice(0, 6).map((item) => ({
      id: item.id,
      label: item.title,
      description: `Bounty \xB7 ${item.status}`,
      path: `/plugins/official.collectors-archive/bounties?record_id=${item.id}`
    }));
  });
  context.host.registerNotificationProvider?.(async () => {
    if (!(await host().runAction("migration-status")).imported) return [];
    const response = await pluginRequest("bounties?status=active");
    if (!response.ok) throw new Error("Archive reminders unavailable.");
    const body = await response.json(), now = Date.now() / 1e3;
    const reminders = [];
    for (const item of body.bounties) {
      const path = `/plugins/official.collectors-archive/bounties?record_id=${item.id}`;
      if (item.target_date !== null && item.target_date - now <= 7 * 86400) {
        const days = Math.ceil((item.target_date - now) / 86400);
        reminders.push({ id: `deadline:${item.id}`, label: item.title, path, description: days < 0 ? `Overdue by ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"}` : days === 0 ? "Due today" : `Due in ${days} day${days === 1 ? "" : "s"}` });
      }
      if (item.auto_generated && now - item.created_at <= 7 * 86400) reminders.push({ id: `suggested:${item.id}`, label: item.title, description: "Suggested for you", path });
    }
    return reminders;
  });
  const pages = {
    cards: () => import("./chunks/CardCollection-UHIER3E3.js"),
    "card-detail": () => import("./chunks/CardDetail-3KZFLNTH.js"),
    sets: () => import("./chunks/SetList-FDGFE3DC.js"),
    "set-detail": () => import("./chunks/SetDetail-6QLHTZCQ.js"),
    bounties: () => import("./chunks/Bounties-N3WAE764.js"),
    goals: () => import("./chunks/GoalsWidget-VKJ5CLJ2.js"),
    migration: null
  };
  for (const [id, loader] of Object.entries(pages)) {
    const View = loader ? defineAsyncComponent(async () => (await loader()).default) : null;
    context.registerComponent(id, defineComponent({
      props: ["context", "host"],
      setup(props) {
        provide("collector-route", { params: { cardId: props.context.record_id, setId: props.context.record_id, id: props.context.record_id }, query: props.context });
        const imported = ref(false), checking = ref(true), pending = ref(false), error = ref(""), progress = ref(""), generation = ref(0);
        let live = true;
        onBeforeUnmount(() => {
          live = false;
        });
        onMounted(async () => {
          try {
            const [result] = await Promise.all([host().runAction("migration-status"), ensureStyles()]);
            if (live) imported.value = Boolean(result.imported);
          } catch (err) {
            if (live) error.value = err instanceof Error ? err.message : "Could not check your archive.";
          } finally {
            if (live) checking.value = false;
          }
        });
        async function importLegacy() {
          pending.value = true;
          error.value = "";
          try {
            for (const table of TABLES) {
              let offset = 0, chunk_offset = 0, sha256;
              while (live) {
                progress.value = `Importing ${table.replaceAll("_", " ")}\u2026`;
                const result = await host().runAction("import-legacy", { table, offset, chunk_offset, sha256 });
                if (result.complete) break;
                offset = Number(result.next_offset);
                chunk_offset = Number(result.next_chunk_offset ?? 0);
                sha256 = result.sha256;
              }
              if (!live) return;
            }
            if (live) {
              imported.value = true;
              generation.value++;
              progress.value = "Your archive is imported. Server originals remain available.";
            }
          } catch (err) {
            if (live) error.value = err instanceof Error ? err.message : "Import interrupted. Retry safely; original records are retained.";
          } finally {
            if (live) pending.value = false;
          }
        }
        return () => checking.value ? h("p", { class: "ui-state", role: "status" }, "Loading archive\u2026") : h("section", { class: "collector-archive" }, [
          id === "migration" ? h("h1", "Collector's Archive") : null,
          !imported.value || id === "migration" ? h("section", { class: "collector-import ui-panel" }, [
            h("h2", "Bring your existing archive with you"),
            h("p", "Import Cards, Sets and Bounties from older host versions, including prestige, customization, evidence, journals and reward history. The server originals are retained. Retrying an interrupted import preserves records already imported."),
            h("button", { class: "ui-btn ui-btn-primary", disabled: checking.value || pending.value || imported.value, onClick: importLegacy }, checking.value ? "Checking archive\u2026" : imported.value ? "Archive imported" : pending.value ? "Importing\u2026" : "Import legacy records"),
            h("p", "For backups, use the plugin manager's storage backup and restore controls. Keep a database backup until you've verified the import.")
          ]) : null,
          progress.value ? h("p", { role: "status" }, progress.value) : null,
          error.value ? h("p", { role: "alert", class: "collector-error" }, error.value) : null,
          View && imported.value ? h(View, { key: generation.value }) : null
        ]);
      }
    }));
  }
}
export {
  activate
};
