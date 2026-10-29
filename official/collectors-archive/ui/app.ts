import { defineAsyncComponent, defineComponent, h, provide, ref, onMounted, onBeforeUnmount } from "vue";
import { configure as configureVue } from "@unnamed/plugin-vue";
import { configure as configureUi } from "@unnamed/plugin-ui";
import { configureHost, host, pluginRequest, type NativeHost } from "./native/host";

const TABLES = ["sets", "bounties", "cards", "bounty_objectives", "bounty_evidence", "bounty_journal_entries", "bounty_point_transactions"];
export async function activate(context: NativeHost & {
  registerComponent(id: string, component: unknown): void;
  onCleanup?(callback: () => void): void;
}) {
  configureVue(context); configureUi(context); configureHost(context);
  let stylesheet: HTMLLinkElement | undefined;
  let stylesReady: Promise<void> | undefined;
  function ensureStyles(): Promise<void> {
    if (stylesReady) return stylesReady;
    stylesReady = new Promise<void>((resolve, reject) => {
      const link = document.createElement("link");
      stylesheet = link;
      link.rel = "stylesheet";
      link.href = new URL("./style.css", import.meta.url).href;
      link.onload = () => resolve();
      link.onerror = () => {
        link.remove();
        stylesheet = undefined;
        stylesReady = undefined;
        reject(new Error("Archive styles could not be loaded. Reopen this page to retry."));
      };
      document.head.appendChild(link);
    });
    return stylesReady;
  }
  context.onCleanup?.(() => stylesheet?.remove());
  context.host.registerSearchProvider?.(async query => {
    if (!(await host().runAction("migration-status")).imported) return [];
    const response = await pluginRequest("bounties");
    if (!response.ok) throw new Error("Archive search unavailable.");
    const body = await response.json();
    return body.bounties.filter((item: {title: string}) => item.title.toLowerCase().includes(query.toLowerCase())).slice(0, 6)
      .map((item: {id: string; title: string; status: string}) => ({ id: item.id, label: item.title,
        description: `Bounty · ${item.status}`, path: `/plugins/official.collectors-archive/bounties?record_id=${item.id}` }));
  });
  context.host.registerNotificationProvider?.(async () => {
    if (!(await host().runAction("migration-status")).imported) return [];
    const response = await pluginRequest("bounties?status=active");
    if (!response.ok) throw new Error("Archive reminders unavailable.");
    const body = await response.json(), now = Date.now() / 1000;
    const reminders: Array<{id: string; label: string; description: string; path: string}> = [];
    for (const item of body.bounties) {
      const path = `/plugins/official.collectors-archive/bounties?record_id=${item.id}`;
      if (item.target_date !== null && item.target_date - now <= 7 * 86400) {
        const days = Math.ceil((item.target_date - now) / 86400);
        reminders.push({id: `deadline:${item.id}`, label: item.title, path, description: days < 0 ? `Overdue by ${Math.abs(days)} day${Math.abs(days) === 1 ? "" : "s"}` : days === 0 ? "Due today" : `Due in ${days} day${days === 1 ? "" : "s"}`});
      }
      if (item.auto_generated && now - item.created_at <= 7 * 86400) reminders.push({id: `suggested:${item.id}`, label: item.title, description: "Suggested for you", path});
    }
    return reminders;
  });
  // Keep global providers small. Compiled SFCs evaluate only after their page
  // opens, with the public Vue/UI bindings already configured above.
  const pages = {
    cards: () => import("./views/CardCollection.vue"),
    "card-detail": () => import("./views/CardDetail.vue"),
    sets: () => import("./views/SetList.vue"),
    "set-detail": () => import("./views/SetDetail.vue"),
    bounties: () => import("./views/Bounties.vue"),
    goals: () => import("./GoalsWidget.vue"),
    migration: null,
  };
  for (const [id, loader] of Object.entries(pages)) {
    const View = loader ? defineAsyncComponent(async () => (await loader()).default) : null;
    context.registerComponent(id, defineComponent({
      props: ["context", "host"],
      setup(props) {
        provide("collector-route", { params: { cardId: props.context.record_id, setId: props.context.record_id, id: props.context.record_id }, query: props.context });
        const imported = ref(false), checking = ref(true), pending = ref(false), error = ref(""), progress = ref(""), generation = ref(0);
        let live = true;
        onBeforeUnmount(() => { live = false; });
        onMounted(async () => {
          try {
            const [result] = await Promise.all([host().runAction("migration-status"), ensureStyles()]);
            if (live) imported.value = Boolean(result.imported);
          }
          catch (err) { if (live) error.value = err instanceof Error ? err.message : "Could not check your archive."; }
          finally { if (live) checking.value = false; }
        });
        async function importLegacy() {
          pending.value = true; error.value = "";
          try {
            for (const table of TABLES) {
              let offset = 0, chunk_offset = 0, sha256: unknown;
              while (live) {
                progress.value = `Importing ${table.replaceAll("_", " ")}…`;
                const result = await host().runAction("import-legacy", { table, offset, chunk_offset, sha256 });
                if (result.complete) break;
                offset = Number(result.next_offset);
                chunk_offset = Number(result.next_chunk_offset ?? 0);
                sha256 = result.sha256;
              }
              if (!live) return;
            }
            if (live) { imported.value = true; generation.value++; progress.value = "Your archive is imported. Server originals remain available."; }
          } catch (err) { if (live) error.value = err instanceof Error ? err.message : "Import interrupted. Retry safely; original records are retained."; }
          finally { if (live) pending.value = false; }
        }
        return () => checking.value
          ? h("p", { class: "ui-state", role: "status" }, "Loading archive…")
          : h("section", { class: "collector-archive" }, [
          id === "migration" ? h("h1", "Collector's Archive") : null,
          !imported.value || id === "migration" ? h("section", { class: "collector-import ui-panel" }, [
            h("h2", "Bring your existing archive with you"),
            h("p", "Import Cards, Sets and Bounties from older host versions, including prestige, customization, evidence, journals and reward history. The server originals are retained. Retrying an interrupted import preserves records already imported."),
            h("button", { class: "ui-btn ui-btn-primary", disabled: checking.value || pending.value || imported.value, onClick: importLegacy }, checking.value ? "Checking archive…" : imported.value ? "Archive imported" : pending.value ? "Importing…" : "Import legacy records"),
            h("p", "For backups, use the plugin manager's storage backup and restore controls. Keep a database backup until you've verified the import."),
          ]) : null,
          progress.value ? h("p", { role: "status" }, progress.value) : null,
          error.value ? h("p", { role: "alert", class: "collector-error" }, error.value) : null,
          View && imported.value ? h(View, { key: generation.value }) : null,
        ]);
      },
    }));
  }
}
