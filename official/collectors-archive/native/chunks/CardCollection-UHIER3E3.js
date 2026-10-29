import {
  createCard,
  listCards
} from "./chunk-AQDOIIHE.js";
import {
  fetchBounties
} from "./chunk-NF76CKRV.js";
import {
  fetchGames
} from "./chunk-JQELIRZM.js";
import {
  useRouter
} from "./chunk-PPCLUKKJ.js";
import {
  AccountChip,
  Fragment,
  PageHeader,
  UiModal,
  computed,
  createBlock,
  createCommentVNode,
  createElementBlock,
  createElementVNode,
  createVNode,
  defineComponent,
  onMounted,
  openBlock,
  ref,
  renderList,
  toDisplayString,
  unref,
  vModelText,
  withCtx,
  withDirectives
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/views/CardCollection.vue
var _hoisted_1 = { class: "cards-page" };
var _hoisted_2 = {
  key: 0,
  class: "empty-state"
};
var _hoisted_3 = {
  key: 1,
  class: "picker-list"
};
var _hoisted_4 = ["disabled", "onClick"];
var _hoisted_5 = {
  key: 1,
  class: "empty-state"
};
var _hoisted_6 = {
  key: 2,
  class: "empty-state error"
};
var _hoisted_7 = {
  key: 3,
  class: "empty-state"
};
var _hoisted_8 = {
  key: 4,
  class: "cards-grid"
};
var _hoisted_9 = ["onClick"];
var _hoisted_10 = {
  key: 0,
  class: "rarity-chip"
};
var _hoisted_11 = {
  key: 1,
  class: "prestige-chip"
};
var _hoisted_12 = { class: "card-tile-title" };
var _hoisted_13 = { class: "card-tile-num" };
var component = /* @__PURE__ */ defineComponent({
  __name: "CardCollection",
  setup(__props) {
    const router = useRouter();
    const cards = ref([]);
    const games = ref([]);
    const bounties = ref([]);
    const loading = ref(true);
    const error = ref(null);
    const showPicker = ref(false);
    const pickerQuery = ref("");
    const creating = ref(false);
    const RARITY_LETTER = {
      common: "C",
      uncommon: "U",
      rare: "R",
      legendary: "L",
      mythic: "M"
    };
    const gameById = computed(() => new Map(games.value.map((g) => [g.id, g])));
    const bountyById = computed(
      () => new Map(bounties.value.map((b) => [b.id, b]))
    );
    function isCardPrestiged(c) {
      return !!c.bountyId && bountyById.value.get(c.bountyId)?.status === "completed";
    }
    const eligibleGames = computed(() => {
      const cardedGameIds = new Set(cards.value.map((c) => c.gameId));
      return games.value.filter(
        (g) => (g.status === "beaten" || g.status === "mastered") && !cardedGameIds.has(g.id) && g.title.toLowerCase().includes(pickerQuery.value.toLowerCase())
      );
    });
    async function load() {
      loading.value = true;
      try {
        const [c, g, b] = await Promise.all([
          listCards(),
          fetchGames(),
          fetchBounties()
        ]);
        cards.value = c;
        games.value = g;
        bounties.value = b;
      } catch (e) {
        error.value = e instanceof Error ? e.message : "Failed to load cards.";
      } finally {
        loading.value = false;
      }
    }
    async function handleCreate(gameId) {
      creating.value = true;
      try {
        const card = await createCard({ gameId });
        router.push(`/cards/${card.id}`);
      } catch (e) {
        error.value = e instanceof Error ? e.message : "Failed to create card.";
      } finally {
        creating.value = false;
      }
    }
    onMounted(load);
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("main", _hoisted_1, [
        createVNode(unref(AccountChip), { fixed: "" }),
        createVNode(unref(PageHeader), {
          title: "Cards",
          description: "Every Collector Card you've generated, front-face up."
        }, {
          actions: withCtx(() => [
            createElementVNode("button", {
              type: "button",
              class: "ui-btn ui-btn-primary",
              onClick: _cache[0] || (_cache[0] = ($event) => showPicker.value = true),
              "data-shortcut": "create"
            }, " New card ")
          ]),
          _: 1
          /* STABLE */
        }),
        showPicker.value ? (openBlock(), createBlock(unref(UiModal), {
          key: 0,
          title: "New card",
          description: "Choose a Beaten or Mastered game that doesn't already have a card.",
          dismissible: !creating.value,
          onClose: _cache[2] || (_cache[2] = ($event) => showPicker.value = false)
        }, {
          default: withCtx(() => [
            withDirectives(createElementVNode(
              "input",
              {
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => pickerQuery.value = $event),
                type: "text",
                class: "text-input",
                placeholder: "Search Beaten/Mastered games\u2026",
                "aria-label": "Search eligible games"
              },
              null,
              512
              /* NEED_PATCH */
            ), [
              [vModelText, pickerQuery.value]
            ]),
            !eligibleGames.value.length ? (openBlock(), createElementBlock("p", _hoisted_2, " No eligible games. A card can only be made for a game marked Beaten or Mastered that doesn't already have one. ")) : (openBlock(), createElementBlock("ul", _hoisted_3, [
              (openBlock(true), createElementBlock(
                Fragment,
                null,
                renderList(eligibleGames.value, (g) => {
                  return openBlock(), createElementBlock("li", {
                    key: g.id,
                    class: "picker-item"
                  }, [
                    createElementVNode(
                      "span",
                      null,
                      toDisplayString(g.title),
                      1
                      /* TEXT */
                    ),
                    createElementVNode("button", {
                      type: "button",
                      class: "secondary-button",
                      disabled: creating.value,
                      onClick: ($event) => handleCreate(g.id)
                    }, " Create ", 8, _hoisted_4)
                  ]);
                }),
                128
                /* KEYED_FRAGMENT */
              ))
            ]))
          ]),
          _: 1
          /* STABLE */
        }, 8, ["dismissible"])) : createCommentVNode("v-if", true),
        loading.value ? (openBlock(), createElementBlock("p", _hoisted_5, "Loading\u2026")) : error.value ? (openBlock(), createElementBlock(
          "p",
          _hoisted_6,
          toDisplayString(error.value),
          1
          /* TEXT */
        )) : !cards.value.length ? (openBlock(), createElementBlock("p", _hoisted_7, "No cards yet.")) : (openBlock(), createElementBlock("div", _hoisted_8, [
          (openBlock(true), createElementBlock(
            Fragment,
            null,
            renderList(cards.value, (c) => {
              return openBlock(), createElementBlock("button", {
                key: c.id,
                type: "button",
                class: "card-tile",
                onClick: ($event) => unref(router).push(`/cards/${c.id}`)
              }, [
                c.rarity ? (openBlock(), createElementBlock(
                  "span",
                  _hoisted_10,
                  toDisplayString(RARITY_LETTER[c.rarity]),
                  1
                  /* TEXT */
                )) : createCommentVNode("v-if", true),
                isCardPrestiged(c) ? (openBlock(), createElementBlock("span", _hoisted_11, "P")) : createCommentVNode("v-if", true),
                createElementVNode(
                  "span",
                  _hoisted_12,
                  toDisplayString(gameById.value.get(c.gameId)?.title ?? "Unknown game"),
                  1
                  /* TEXT */
                ),
                createElementVNode(
                  "span",
                  _hoisted_13,
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
      ]);
    };
  }
});
component.__scopeId = "data-v-562daa07";
var CardCollection_default = component;
export {
  CardCollection_default as default
};
