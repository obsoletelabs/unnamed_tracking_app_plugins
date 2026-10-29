import {
  deleteSet,
  fetchSet,
  updateSet
} from "./chunk-UVTUI42S.js";
import "./chunk-AQDOIIHE.js";
import {
  fetchGames
} from "./chunk-JQELIRZM.js";
import {
  useRoute,
  useRouter
} from "./chunk-PPCLUKKJ.js";
import {
  Fragment,
  computed,
  createCommentVNode,
  createElementBlock,
  createElementVNode,
  createTextVNode,
  defineComponent,
  host,
  onMounted,
  openBlock,
  ref,
  renderList,
  toDisplayString,
  unref
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/native/dialog.ts
var useConfirm = () => (options) => host().confirm(options);
var usePrompt = () => (options) => host().prompt(options);

// official/collectors-archive/ui/views/SetDetail.vue
var _hoisted_1 = { class: "set-detail-page" };
var _hoisted_2 = {
  key: 0,
  class: "empty-state"
};
var _hoisted_3 = {
  key: 1,
  class: "empty-state error"
};
var _hoisted_4 = { class: "header-row" };
var _hoisted_5 = { class: "progress" };
var _hoisted_6 = {
  key: 0,
  class: "complete-banner"
};
var _hoisted_7 = {
  key: 1,
  class: "empty-state"
};
var _hoisted_8 = {
  key: 2,
  class: "cards-grid"
};
var _hoisted_9 = ["onClick"];
var _hoisted_10 = { class: "card-tile-title" };
var _hoisted_11 = { class: "card-tile-num" };
var component = /* @__PURE__ */ defineComponent({
  __name: "SetDetail",
  setup(__props) {
    const confirm = useConfirm();
    const prompt = usePrompt();
    const route = useRoute();
    const router = useRouter();
    const setId = route.params.id;
    const set = ref(null);
    const games = ref([]);
    const loading = ref(true);
    const error = ref(null);
    const gameById = computed(() => new Map(games.value.map((g) => [g.id, g])));
    async function load() {
      loading.value = true;
      try {
        const [s, g] = await Promise.all([fetchSet(setId), fetchGames()]);
        set.value = s;
        games.value = g;
      } catch (e) {
        error.value = e instanceof Error ? e.message : "Failed to load set.";
      } finally {
        loading.value = false;
      }
    }
    async function handleDelete() {
      if (!set.value) return;
      const ok = await confirm({
        title: "Delete set",
        message: `Delete set "${set.value.name}"? Cards in it are just unassigned, not deleted.`,
        confirmLabel: "Delete",
        danger: true
      });
      if (!ok) return;
      await deleteSet(setId);
      router.push("/sets");
    }
    async function editTarget() {
      if (!set.value) return;
      const input = await prompt({
        title: "Cards in this set",
        message: "Total cards expected for this set (blank for unknown).",
        defaultValue: String(set.value.targetTotal ?? "")
      });
      if (input === null) return;
      const target = input.trim() === "" ? null : Number(input);
      await updateSet(setId, {
        targetTotal: Number.isFinite(target) ? target : null
      });
      await load();
    }
    onMounted(load);
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("main", _hoisted_1, [
        createElementVNode("button", {
          type: "button",
          class: "back-btn",
          onClick: _cache[0] || (_cache[0] = ($event) => unref(router).push("/sets"))
        }, " \u2190 Sets "),
        loading.value ? (openBlock(), createElementBlock("p", _hoisted_2, "Loading\u2026")) : error.value ? (openBlock(), createElementBlock(
          "p",
          _hoisted_3,
          toDisplayString(error.value),
          1
          /* TEXT */
        )) : set.value ? (openBlock(), createElementBlock(
          Fragment,
          { key: 2 },
          [
            createElementVNode("div", _hoisted_4, [
              createElementVNode("div", null, [
                createElementVNode(
                  "h1",
                  null,
                  toDisplayString(set.value.name),
                  1
                  /* TEXT */
                ),
                createElementVNode("p", _hoisted_5, [
                  createTextVNode(
                    toDisplayString(set.value.targetTotal ? `${set.value.cardCount} / ${set.value.targetTotal} cards` : `${set.value.cardCount} cards`) + " ",
                    1
                    /* TEXT */
                  ),
                  createElementVNode("button", {
                    type: "button",
                    class: "link-btn",
                    onClick: editTarget
                  }, " edit target ")
                ])
              ]),
              createElementVNode("button", {
                type: "button",
                class: "danger-button",
                onClick: handleDelete
              }, " Delete set ")
            ]),
            set.value.isComplete ? (openBlock(), createElementBlock("div", _hoisted_6, [
              _cache[1] || (_cache[1] = createElementVNode(
                "span",
                { class: "complete-glow" },
                null,
                -1
                /* CACHED */
              )),
              createElementVNode(
                "span",
                null,
                "SET COMPLETE \u2014 " + toDisplayString(set.value.cardCount) + " / " + toDisplayString(set.value.targetTotal),
                1
                /* TEXT */
              )
            ])) : createCommentVNode("v-if", true),
            !set.value.cards.length ? (openBlock(), createElementBlock("p", _hoisted_7, " No cards in this set yet. Assign one from a card's own detail page. ")) : (openBlock(), createElementBlock("div", _hoisted_8, [
              (openBlock(true), createElementBlock(
                Fragment,
                null,
                renderList(set.value.cards, (c) => {
                  return openBlock(), createElementBlock("button", {
                    key: c.id,
                    type: "button",
                    class: "card-tile",
                    onClick: ($event) => unref(router).push(`/cards/${c.id}`)
                  }, [
                    createElementVNode(
                      "span",
                      _hoisted_10,
                      toDisplayString(gameById.value.get(c.gameId)?.title ?? "Unknown game"),
                      1
                      /* TEXT */
                    ),
                    createElementVNode(
                      "span",
                      _hoisted_11,
                      "#" + toDisplayString(String(c.archiveNumber ?? 0).padStart(3, "0")),
                      1
                      /* TEXT */
                    )
                  ], 8, _hoisted_9);
                }),
                128
                /* KEYED_FRAGMENT */
              ))
            ]))
          ],
          64
          /* STABLE_FRAGMENT */
        )) : createCommentVNode("v-if", true)
      ]);
    };
  }
});
component.__scopeId = "data-v-f5867ad9";
var SetDetail_default = component;
export {
  SetDetail_default as default
};
