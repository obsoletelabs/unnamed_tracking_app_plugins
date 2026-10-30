import {
  RouterLink
} from "./chunk-PPCLUKKJ.js";
import {
  Fragment,
  createCommentVNode,
  createElementBlock,
  createElementVNode,
  createTextVNode,
  createVNode,
  defineComponent,
  onBeforeUnmount,
  onMounted,
  openBlock,
  pluginRequest,
  ref,
  renderList,
  toDisplayString,
  unref,
  withCtx
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/GoalsWidget.vue
var _hoisted_1 = { class: "archive-goals" };
var _hoisted_2 = {
  key: 0,
  role: "status"
};
var _hoisted_3 = { key: 1 };
var _hoisted_4 = { key: 0 };
var _hoisted_5 = { key: 2 };
var component = /* @__PURE__ */ defineComponent({
  __name: "GoalsWidget",
  setup(__props) {
    const goals = ref([]), completed = ref(0), points = ref(0), error = ref("");
    let live = true;
    onBeforeUnmount(() => {
      live = false;
    });
    onMounted(async () => {
      try {
        const [goalResponse, pointsResponse] = await Promise.all([pluginRequest("bounties"), pluginRequest("bounties/points/total")]);
        if (!goalResponse.ok || !pointsResponse.ok) throw new Error("Could not load your goals. Open the archive to retry.");
        const [all, total] = await Promise.all([goalResponse.json(), pointsResponse.json()]);
        if (!live) return;
        goals.value = all.bounties.filter((item) => item.status === "active").slice(0, 4);
        completed.value = all.bounties.filter((item) => item.status === "completed" && Number(item.completed_at) >= Date.now() / 1e3 - 7 * 86400).length;
        points.value = total.total;
      } catch (reason) {
        if (live) error.value = reason instanceof Error ? reason.message : "Could not load goals.";
      }
    });
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("div", _hoisted_1, [
        error.value ? (openBlock(), createElementBlock(
          "p",
          _hoisted_2,
          toDisplayString(error.value),
          1
          /* TEXT */
        )) : goals.value.length ? (openBlock(), createElementBlock("ul", _hoisted_3, [
          (openBlock(true), createElementBlock(
            Fragment,
            null,
            renderList(goals.value, (goal) => {
              return openBlock(), createElementBlock("li", {
                key: goal.id
              }, [
                createVNode(unref(RouterLink), {
                  to: `/bounties?record_id=${goal.id}`
                }, {
                  default: withCtx(() => [
                    createTextVNode(
                      toDisplayString(goal.title),
                      1
                      /* TEXT */
                    ),
                    goal.game_title ? (openBlock(), createElementBlock(
                      "small",
                      _hoisted_4,
                      toDisplayString(goal.game_title),
                      1
                      /* TEXT */
                    )) : createCommentVNode("v-if", true)
                  ]),
                  _: 2
                  /* DYNAMIC */
                }, 1032, ["to"])
              ]);
            }),
            128
            /* KEYED_FRAGMENT */
          ))
        ])) : (openBlock(), createElementBlock("p", _hoisted_5, "No active goals. Create a bounty when you want some extra structure.")),
        createElementVNode("dl", null, [
          createElementVNode("div", null, [
            _cache[0] || (_cache[0] = createElementVNode(
              "dt",
              null,
              "Completed this week",
              -1
              /* CACHED */
            )),
            createElementVNode(
              "dd",
              null,
              toDisplayString(completed.value),
              1
              /* TEXT */
            )
          ]),
          createElementVNode("div", null, [
            _cache[1] || (_cache[1] = createElementVNode(
              "dt",
              null,
              "Reward points",
              -1
              /* CACHED */
            )),
            createElementVNode(
              "dd",
              null,
              toDisplayString(points.value),
              1
              /* TEXT */
            )
          ])
        ]),
        createVNode(unref(RouterLink), { to: "/bounties" }, {
          default: withCtx(() => [..._cache[2] || (_cache[2] = [
            createTextVNode(
              "View your goals and reminders",
              -1
              /* CACHED */
            )
          ])]),
          _: 1
          /* STABLE */
        })
      ]);
    };
  }
});
component.__scopeId = "data-v-cc47efd1";
var GoalsWidget_default = component;
export {
  GoalsWidget_default as default
};
