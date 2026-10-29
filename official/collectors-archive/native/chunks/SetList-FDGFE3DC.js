import {
  createSet,
  fetchSets
} from "./chunk-UVTUI42S.js";
import "./chunk-AQDOIIHE.js";
import {
  useRouter
} from "./chunk-PPCLUKKJ.js";
import {
  AccountChip,
  Fragment,
  PageHeader,
  createCommentVNode,
  createElementBlock,
  createElementVNode,
  createVNode,
  defineComponent,
  normalizeClass,
  onMounted,
  openBlock,
  ref,
  renderList,
  toDisplayString,
  unref,
  vModelText,
  withDirectives,
  withModifiers
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/views/SetList.vue
var _hoisted_1 = { class: "sets-page" };
var _hoisted_2 = ["disabled"];
var _hoisted_3 = {
  key: 0,
  class: "error"
};
var _hoisted_4 = {
  key: 1,
  class: "empty-state"
};
var _hoisted_5 = {
  key: 2,
  class: "empty-state error"
};
var _hoisted_6 = {
  key: 3,
  class: "empty-state"
};
var _hoisted_7 = {
  key: 4,
  class: "sets-grid"
};
var _hoisted_8 = ["onClick"];
var _hoisted_9 = {
  key: 0,
  class: "complete-badge"
};
var _hoisted_10 = { class: "progress" };
var component = /* @__PURE__ */ defineComponent({
  __name: "SetList",
  setup(__props) {
    const router = useRouter();
    const sets = ref([]);
    const loading = ref(true);
    const error = ref(null);
    const newName = ref("");
    const newTarget = ref(null);
    const creating = ref(false);
    const createError = ref(null);
    async function load() {
      loading.value = true;
      try {
        sets.value = await fetchSets();
      } catch (e) {
        error.value = e instanceof Error ? e.message : "Failed to load sets.";
      } finally {
        loading.value = false;
      }
    }
    async function handleCreate() {
      if (creating.value) return;
      const name = newName.value.trim();
      if (!name) return;
      creating.value = true;
      createError.value = null;
      try {
        await createSet({ name, targetTotal: newTarget.value });
        newName.value = "";
        newTarget.value = null;
        await load();
      } catch (e) {
        createError.value = e instanceof Error ? e.message : "Failed to create set.";
      } finally {
        creating.value = false;
      }
    }
    onMounted(load);
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("main", _hoisted_1, [
        createVNode(unref(AccountChip), { fixed: "" }),
        createVNode(unref(PageHeader), {
          title: "Sets",
          description: "Group cards with a position and total. Assign a card to a set from the card's detail page. When every expected card is in, the set shows as complete."
        }),
        createElementVNode(
          "form",
          {
            class: "create-row",
            onSubmit: withModifiers(handleCreate, ["prevent"])
          },
          [
            withDirectives(createElementVNode(
              "input",
              {
                "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => newName.value = $event),
                type: "text",
                class: "text-input",
                placeholder: "New set name",
                "aria-label": "New set name",
                "data-shortcut": "create"
              },
              null,
              512
              /* NEED_PATCH */
            ), [
              [vModelText, newName.value]
            ]),
            withDirectives(createElementVNode(
              "input",
              {
                "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => newTarget.value = $event),
                type: "number",
                min: "1",
                class: "text-input target-input",
                placeholder: "Total (optional)",
                "aria-label": "Expected card total (optional)"
              },
              null,
              512
              /* NEED_PATCH */
            ), [
              [
                vModelText,
                newTarget.value,
                void 0,
                { number: true }
              ]
            ]),
            createElementVNode("button", {
              type: "submit",
              class: "add-button",
              disabled: creating.value || !newName.value.trim()
            }, " + Create Set ", 8, _hoisted_2)
          ],
          32
          /* NEED_HYDRATION */
        ),
        createError.value ? (openBlock(), createElementBlock(
          "p",
          _hoisted_3,
          toDisplayString(createError.value),
          1
          /* TEXT */
        )) : createCommentVNode("v-if", true),
        loading.value ? (openBlock(), createElementBlock("p", _hoisted_4, "Loading\u2026")) : error.value ? (openBlock(), createElementBlock(
          "p",
          _hoisted_5,
          toDisplayString(error.value),
          1
          /* TEXT */
        )) : !sets.value.length ? (openBlock(), createElementBlock("p", _hoisted_6, "No sets yet.")) : (openBlock(), createElementBlock("div", _hoisted_7, [
          (openBlock(true), createElementBlock(
            Fragment,
            null,
            renderList(sets.value, (s) => {
              return openBlock(), createElementBlock("button", {
                key: s.id,
                type: "button",
                class: normalizeClass(["set-card", { complete: s.isComplete }]),
                onClick: ($event) => unref(router).push(`/sets/${s.id}`)
              }, [
                s.isComplete ? (openBlock(), createElementBlock("span", _hoisted_9, "COMPLETE")) : createCommentVNode("v-if", true),
                createElementVNode(
                  "h3",
                  null,
                  toDisplayString(s.name),
                  1
                  /* TEXT */
                ),
                createElementVNode(
                  "p",
                  _hoisted_10,
                  toDisplayString(s.targetTotal ? `${s.cardCount} / ${s.targetTotal}` : `${s.cardCount} card${s.cardCount === 1 ? "" : "s"}`),
                  1
                  /* TEXT */
                )
              ], 10, _hoisted_8);
            }),
            128
            /* KEYED_FRAGMENT */
          ))
        ]))
      ]);
    };
  }
});
component.__scopeId = "data-v-0ce1d780";
var SetList_default = component;
export {
  SetList_default as default
};
