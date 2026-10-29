import {
  fetchSets
} from "./chunk-UVTUI42S.js";
import {
  generatePrestigeChallenge,
  getCard,
  updateCard
} from "./chunk-AQDOIIHE.js";
import {
  fetchBounty
} from "./chunk-NF76CKRV.js";
import {
  fetchGame
} from "./chunk-JQELIRZM.js";
import {
  RouterLink,
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
  createVNode,
  defineComponent,
  normalizeClass,
  normalizeStyle,
  onMounted,
  openBlock,
  ref,
  renderList,
  toDisplayString,
  unref,
  vModelSelect,
  vModelText,
  vShow,
  watch,
  withCtx,
  withDirectives,
  withModifiers
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/types/card.ts
var DEFAULT_CARD_CUSTOMIZATION = {
  frontTemplate: "classic",
  backTemplate: "emblem",
  titlePosition: "top",
  accent: "gold",
  borderColor: "black",
  cardFace: "dark",
  prestigeVariant: "foil",
  symbol: "star",
  symbol2: "none",
  symbolRotation: 0,
  customSymbol: null,
  customArt: null,
  memorableAchievement: "",
  personalNote: ""
};
var CARD_SYMBOLS = {
  star: '<path d="M12 2l3.5 8.5L22 12l-6.5 1.5L12 22l-3.5-8.5L2 12l6.5-1.5z"/>',
  diamond: '<path d="M12 2l7 9-7 11-7-11z"/>',
  hex: '<path d="M12 2l8 5v10l-8 5-8-5V7z"/>',
  compass: '<circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" stroke-width="2"/><path d="M15 9l-2 6-6 2 2-6z"/>',
  shield: '<path d="M12 2l8 3.5v6c0 5-3.4 8.4-8 10.5-4.6-2.1-8-5.5-8-10.5v-6z"/>',
  circle: '<circle cx="12" cy="12" r="8.5"/>',
  crown: '<path d="M3 18h18l-1.5-9-4.5 3.5L12 5l-3 7.5L4.5 12.5z"/>',
  dagger: '<path d="M11 2h2v11h3l-4 9-4-9h3z"/>',
  laurel: '<path d="M12 3c5 2 7 7 5 13-6-1-9-6-8-11 1-1 2-2 3-2z"/>',
  flame: '<path d="M12 2c3 5 6 7 6 12a6 6 0 0 1-12 0c0-2 1-4 2-5-.3 2 .6 3 1.3 3 .9 0 1.2-1 .6-2.2C9 7.5 11 5 12 2z"/>',
  mountain: '<path d="M2 19L9 6l4 7 2-3 7 9z"/>',
  moon: '<path d="M19.5 14.5A8 8 0 1 1 9.5 4.5a6.5 6.5 0 0 0 10 10z"/>',
  feather: '<path d="M19 3C9 5 4 12 4 21c9-1 15-8 15-18z"/>',
  key: '<path d="M9 2a5 5 0 1 0 0 10 5 5 0 0 0 4.9-6H21v4h-2v3h-3v-3h-1.1A5 5 0 0 0 9 2zM9 5a2 2 0 1 1 0 4 2 2 0 0 1 0-4z"/>',
  book: '<path d="M4 4h7v16H4a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM13 4h7a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-7z"/>',
  anchor: '<circle cx="12" cy="5" r="2" fill="none" stroke="currentColor" stroke-width="2"/><path d="M12 7v13M6 12H2a10 10 0 0 0 8 9M18 12h4a10 10 0 0 1-8 9M6 15h12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>',
  banner: '<path d="M6 2h13l-3 5 3 5H6v10H4V2z"/>',
  helm: '<path d="M12 2C7.6 2 4 5.4 4 9.6v2.5c0 1.3.5 2.5 1.3 3.4L6.4 21h2.1l.6-2.6h5.8l.6 2.6h2.1l1.1-5.5c.8-.9 1.3-2.1 1.3-3.4V9.6C20 5.4 16.4 2 12 2z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M8 11h8M9 14h6" stroke="currentColor" stroke-width="1.4" fill="none" stroke-linecap="round"/>',
  swordscross: '<path d="M4 4l16 16M20 4L4 20" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round"/><path d="M8.5 8.5l2 2M15.5 8.5l-2 2M8.5 15.5l2-2M15.5 15.5l-2-2" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round"/>'
};
var CARD_SYMBOL_ORDER = [
  "star",
  "diamond",
  "hex",
  "compass",
  "shield",
  "circle",
  "crown",
  "dagger",
  "laurel",
  "flame",
  "mountain",
  "moon",
  "feather",
  "key",
  "book",
  "anchor",
  "banner",
  "helm",
  "swordscross"
];

// official/collectors-archive/ui/views/CardDetail.vue
var _hoisted_1 = { class: "designer-page" };
var _hoisted_2 = { class: "designer-header" };
var _hoisted_3 = { key: 0 };
var _hoisted_4 = { class: "archive-num" };
var _hoisted_5 = {
  key: 0,
  class: "empty-state"
};
var _hoisted_6 = {
  key: 1,
  class: "empty-state error"
};
var _hoisted_7 = {
  key: 2,
  class: "designer-layout"
};
var _hoisted_8 = { class: "stage" };
var _hoisted_9 = ["data-template", "data-border-color", "data-face", "data-prestige", "data-prestige-variant", "data-title-pos"];
var _hoisted_10 = { class: "card-inner" };
var _hoisted_11 = { class: "art-layer" };
var _hoisted_12 = ["src"];
var _hoisted_13 = {
  key: 1,
  class: "art-fallback"
};
var _hoisted_14 = { class: "content" };
var _hoisted_15 = {
  class: "row row-title plate",
  id: "rowTitleBar"
};
var _hoisted_16 = { class: "title-name" };
var _hoisted_17 = { class: "title-meta" };
var _hoisted_18 = { class: "bottom-stack" };
var _hoisted_19 = { class: "rules-box plate" };
var _hoisted_20 = { class: "row row-type" };
var _hoisted_21 = { class: "type-title" };
var _hoisted_22 = ["src"];
var _hoisted_23 = ["innerHTML"];
var _hoisted_24 = { class: "row row-text" };
var _hoisted_25 = {
  key: 0,
  class: "stat-line"
};
var _hoisted_26 = {
  key: 1,
  class: "stat-line"
};
var _hoisted_27 = {
  key: 2,
  class: "stat-line"
};
var _hoisted_28 = { class: "flavor-line" };
var _hoisted_29 = { class: "row row-collector plate" };
var _hoisted_30 = { class: "collector-left" };
var _hoisted_31 = ["src"];
var _hoisted_32 = ["innerHTML"];
var _hoisted_33 = {
  key: 0,
  class: "set-complete-tag"
};
var _hoisted_34 = { class: "collector-right" };
var _hoisted_35 = ["data-face"];
var _hoisted_36 = { class: "back-emblem" };
var _hoisted_37 = { class: "medallion" };
var _hoisted_38 = ["src"];
var _hoisted_39 = ["innerHTML"];
var _hoisted_40 = {
  key: 0,
  class: "medallion-badge"
};
var _hoisted_41 = { class: "icon-slot" };
var _hoisted_42 = ["innerHTML"];
var _hoisted_43 = { class: "back-setname" };
var _hoisted_44 = { class: "back-num" };
var _hoisted_45 = { class: "back-collector" };
var _hoisted_46 = { class: "medallion" };
var _hoisted_47 = ["src"];
var _hoisted_48 = ["innerHTML"];
var _hoisted_49 = { class: "bc-panel" };
var _hoisted_50 = { class: "bc-title" };
var _hoisted_51 = { class: "bc-stat-grid" };
var _hoisted_52 = { class: "bc-stat" };
var _hoisted_53 = { class: "val" };
var _hoisted_54 = { class: "bc-stat" };
var _hoisted_55 = { class: "val" };
var _hoisted_56 = { class: "bc-stat" };
var _hoisted_57 = { class: "val" };
var _hoisted_58 = { class: "bc-stat" };
var _hoisted_59 = { class: "val" };
var _hoisted_60 = { class: "bc-pills" };
var _hoisted_61 = { class: "bc-pill" };
var _hoisted_62 = {
  key: 0,
  class: "bc-pill bc-pill-prestige"
};
var _hoisted_63 = {
  key: 0,
  class: "bc-section"
};
var _hoisted_64 = { class: "val" };
var _hoisted_65 = {
  key: 1,
  class: "bc-section"
};
var _hoisted_66 = { class: "val bc-note" };
var _hoisted_67 = {
  key: 2,
  class: "bc-section"
};
var _hoisted_68 = { class: "val bc-note" };
var _hoisted_69 = { class: "back-record" };
var _hoisted_70 = { class: "record-top" };
var _hoisted_71 = { class: "icon-slot" };
var _hoisted_72 = ["src"];
var _hoisted_73 = ["innerHTML"];
var _hoisted_74 = { class: "record-top-num" };
var _hoisted_75 = { class: "record-main" };
var _hoisted_76 = { class: "record-title" };
var _hoisted_77 = { class: "record-completed" };
var _hoisted_78 = { class: "record-stats" };
var _hoisted_79 = {
  key: 0,
  class: "record-moment"
};
var _hoisted_80 = { class: "record-moment-name" };
var _hoisted_81 = {
  key: 0,
  class: "record-moment-desc"
};
var _hoisted_82 = { class: "record-bottom" };
var _hoisted_83 = { class: "stage-actions" };
var _hoisted_84 = { class: "panel" };
var _hoisted_85 = { class: "tabs" };
var _hoisted_86 = { class: "tab-panels" };
var _hoisted_87 = { class: "tab-panel" };
var _hoisted_88 = { class: "field" };
var _hoisted_89 = { class: "tpl-grid" };
var _hoisted_90 = ["onClick"];
var _hoisted_91 = {
  key: 0,
  class: "field"
};
var _hoisted_92 = { class: "tpl-grid" };
var _hoisted_93 = ["onClick"];
var _hoisted_94 = { class: "field" };
var _hoisted_95 = { class: "tpl-grid" };
var _hoisted_96 = ["onClick"];
var _hoisted_97 = { class: "field" };
var _hoisted_98 = { class: "tpl-grid" };
var _hoisted_99 = ["onClick"];
var _hoisted_100 = { class: "field" };
var _hoisted_101 = { class: "tpl-grid" };
var _hoisted_102 = ["onClick"];
var _hoisted_103 = { class: "field" };
var _hoisted_104 = { class: "accent-grid" };
var _hoisted_105 = ["onClick"];
var _hoisted_106 = { class: "tab-panel" };
var _hoisted_107 = {
  key: 0,
  class: "field"
};
var _hoisted_108 = { class: "field-hint" };
var _hoisted_109 = {
  key: 1,
  class: "field"
};
var _hoisted_110 = { class: "field-hint" };
var _hoisted_111 = ["disabled"];
var _hoisted_112 = {
  key: 0,
  class: "field-hint error"
};
var _hoisted_113 = { class: "field" };
var _hoisted_114 = { class: "prestige-status" };
var _hoisted_115 = { class: "prestige-status-title" };
var _hoisted_116 = { class: "field-hint" };
var _hoisted_117 = {
  key: 0,
  class: "field"
};
var _hoisted_118 = { class: "tpl-grid" };
var _hoisted_119 = ["onClick"];
var _hoisted_120 = { class: "tab-panel" };
var _hoisted_121 = { class: "field" };
var _hoisted_122 = ["src"];
var _hoisted_123 = ["innerHTML"];
var _hoisted_124 = { class: "tab-panel" };
var _hoisted_125 = { class: "field" };
var _hoisted_126 = { class: "upload-btn" };
var _hoisted_127 = { class: "field" };
var _hoisted_128 = { class: "field" };
var _hoisted_129 = { class: "tab-panel" };
var _hoisted_130 = { class: "field" };
var _hoisted_131 = { class: "rarity-grid" };
var _hoisted_132 = ["onClick"];
var _hoisted_133 = { class: "field" };
var _hoisted_134 = ["value"];
var _hoisted_135 = { class: "panel-actions" };
var _hoisted_136 = ["disabled"];
var _hoisted_137 = {
  class: "modal",
  role: "dialog",
  "aria-label": "Symbol"
};
var _hoisted_138 = { class: "modal-head" };
var _hoisted_139 = { class: "modal-body" };
var _hoisted_140 = { class: "field" };
var _hoisted_141 = { class: "icon-picker-grid" };
var _hoisted_142 = ["onClick"];
var _hoisted_143 = { class: "icon-slot" };
var _hoisted_144 = ["innerHTML"];
var _hoisted_145 = { class: "field" };
var _hoisted_146 = { class: "slider-field" };
var _hoisted_147 = { class: "sf-head" };
var _hoisted_148 = { class: "field" };
var _hoisted_149 = { class: "icon-picker-grid" };
var _hoisted_150 = ["onClick"];
var _hoisted_151 = { class: "icon-slot" };
var _hoisted_152 = ["innerHTML"];
var _hoisted_153 = { class: "field" };
var _hoisted_154 = { class: "custom-icon-row" };
var _hoisted_155 = {
  key: 0,
  class: "icon-slot"
};
var _hoisted_156 = ["src"];
var _hoisted_157 = { class: "small-upload-btn" };
var _hoisted_158 = { class: "modal-foot" };
var MAX_TILT = 12;
var component = /* @__PURE__ */ defineComponent({
  __name: "CardDetail",
  setup(__props) {
    const route = useRoute();
    const router = useRouter();
    const cardId = route.params.cardId;
    const card = ref(null);
    const game = ref(null);
    const sets = ref([]);
    const loading = ref(true);
    const error = ref(null);
    const saving = ref(false);
    const saved = ref(false);
    const flipped = ref(false);
    const artFailed = ref(false);
    const customization = ref({ ...DEFAULT_CARD_CUSTOMIZATION });
    const rarity = ref(null);
    const setId = ref(null);
    const activeTab = ref(
      "template"
    );
    const symbolModalOpen = ref(false);
    const bounty = ref(null);
    const generatingPrestige = ref(false);
    const prestigeError = ref(null);
    onMounted(async () => {
      try {
        const c = await getCard(cardId);
        card.value = c;
        customization.value = {
          ...DEFAULT_CARD_CUSTOMIZATION,
          ...c.cardCustomization ?? {}
        };
        rarity.value = c.rarity;
        setId.value = c.setId;
        const [g, s] = await Promise.all([fetchGame(c.gameId), fetchSets()]);
        game.value = g;
        sets.value = s;
        if (c.bountyId) {
          bounty.value = await fetchBounty(c.bountyId);
        }
      } catch (e) {
        error.value = e instanceof Error ? e.message : "Failed to load card.";
      } finally {
        loading.value = false;
      }
    });
    const isPrestige = computed(() => bounty.value?.status === "completed");
    const achievements100 = computed(() => {
      const g = game.value;
      return !!g && g.achievementTotal > 0 && g.achievementPercent >= 100;
    });
    async function generatePrestige() {
      if (!card.value) return;
      generatingPrestige.value = true;
      prestigeError.value = null;
      try {
        card.value = await generatePrestigeChallenge(card.value.id);
        if (card.value.bountyId) {
          bounty.value = await fetchBounty(card.value.bountyId);
        }
      } catch (e) {
        prestigeError.value = e instanceof Error ? e.message : "Failed to generate a prestige challenge.";
      } finally {
        generatingPrestige.value = false;
      }
    }
    const RARITY_LABEL = {
      common: "Common",
      uncommon: "Uncommon",
      rare: "Rare",
      legendary: "Legendary",
      mythic: "Mythic"
    };
    const ACCENTS = {
      gold: { gold: "#c8a35f", dim: "#8f7648", soft: "rgba(200,163,95,0.32)" },
      silver: { gold: "#c9ccd6", dim: "#8c8f99", soft: "rgba(201,204,214,0.32)" },
      bronze: { gold: "#b8793f", dim: "#8a5c33", soft: "rgba(184,121,63,0.32)" },
      copper: { gold: "#c17a52", dim: "#8f5b3d", soft: "rgba(193,122,82,0.32)" },
      rose: { gold: "#c99383", dim: "#93695d", soft: "rgba(201,147,131,0.32)" }
    };
    const accentVars = computed(() => {
      const a = ACCENTS[customization.value.accent];
      return { "--gold": a.gold, "--gold-dim": a.dim, "--gold-soft": a.soft };
    });
    function symbolInner(which) {
      const key = which || customization.value.symbol;
      return CARD_SYMBOLS[key] || "";
    }
    const rotStyle = computed(
      () => `rotate(${customization.value.symbolRotation}deg)`
    );
    const hasSecondarySymbol = computed(
      () => customization.value.symbol2 !== "none" && !customization.value.customSymbol
    );
    function onCustomSymbolUpload(e) {
      const input = e.target;
      const file = input.files?.[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = (ev) => {
        customization.value.customSymbol = ev.target?.result;
      };
      reader.readAsDataURL(file);
    }
    function clearCustomSymbol() {
      customization.value.customSymbol = null;
    }
    const artSrc = computed(
      () => customization.value.customArt || game.value?.coverImageUrl || null
    );
    function onArtUpload(e) {
      const input = e.target;
      const file = input.files?.[0];
      if (!file) return;
      artFailed.value = false;
      const reader = new FileReader();
      reader.onload = (ev) => {
        customization.value.customArt = ev.target?.result;
      };
      reader.readAsDataURL(file);
    }
    function resetArt() {
      customization.value.customArt = null;
      artFailed.value = false;
    }
    const tiltX = ref(0);
    const tiltY = ref(0);
    function onCardMouseMove(e) {
      const rect = e.currentTarget.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width - 0.5;
      const py = (e.clientY - rect.top) / rect.height - 0.5;
      tiltY.value = px * MAX_TILT * 2;
      tiltX.value = -py * MAX_TILT * 2;
    }
    function onCardMouseLeave() {
      tiltX.value = 0;
      tiltY.value = 0;
    }
    const rarityLetter = computed(
      () => rarity.value ? rarity.value.charAt(0).toUpperCase() : "?"
    );
    const platformLabel = computed(
      () => game.value?.platforms[0]?.platform ?? game.value?.source ?? "PC"
    );
    const playtimeLabel = computed(() => {
      const minutes = game.value?.platforms[0]?.playtimeMinutes ?? 0;
      if (!minutes) return null;
      const hrs = Math.floor(minutes / 60);
      const mins = minutes % 60;
      return hrs >= 1e3 ? `${hrs.toLocaleString()}h` : `${hrs}h ${mins}m`;
    });
    const achievementLabel = computed(() => {
      const g = game.value;
      if (!g || !g.achievementTotal) return null;
      const unlocked = g.achievements.filter((a) => a.unlockedAt).length || Math.round(g.achievementPercent / 100 * g.achievementTotal);
      return `${unlocked} / ${g.achievementTotal} achievements unlocked.`;
    });
    const statusWord = computed(
      () => game.value?.status === "mastered" ? "Mastered" : "Beaten"
    );
    const completionYear = computed(() => {
      const d = game.value?.completionDate;
      return d ? new Date(d).getFullYear() : null;
    });
    const currentSet = computed(
      () => sets.value.find((s) => s.id === setId.value) ?? null
    );
    const setPositionLabel = computed(() => {
      if (!currentSet.value || !card.value) return null;
      return currentSet.value.targetTotal ? `${String(currentSet.value.cardCount).padStart(2, "0")}/${currentSet.value.targetTotal}` : null;
    });
    const setComplete = computed(() => currentSet.value?.isComplete ?? false);
    async function saveCard() {
      if (!card.value) return;
      saving.value = true;
      saved.value = false;
      try {
        card.value = await updateCard(card.value.id, {
          setId: setId.value,
          rarity: rarity.value,
          cardCustomization: customization.value
        });
        saved.value = true;
        sets.value = await fetchSets();
      } catch (e) {
        error.value = e instanceof Error ? e.message : "Failed to save card.";
      } finally {
        saving.value = false;
      }
    }
    watch(
      [customization, rarity, setId],
      () => {
        saved.value = false;
      },
      { deep: true }
    );
    function printCard() {
      window.print();
    }
    const frontTemplates = [
      { value: "classic", label: "Classic", hint: "Full art, thin gold ring" },
      { value: "borderless", label: "Borderless", hint: "Art to the very edge" },
      { value: "ornate", label: "Ornate", hint: "Corner flourishes" },
      { value: "minimal", label: "Minimal", hint: "Title & collector line only" },
      {
        value: "bordered",
        label: "Bordered",
        hint: "Solid frame, art inset inside it"
      }
    ];
    const backTemplates = [
      { value: "emblem", label: "Emblem", hint: "Medallion" },
      { value: "collector", label: "Collector", hint: "Compact detail" },
      { value: "record", label: "Record", hint: "Completion record" }
    ];
    const accents = ["gold", "silver", "bronze", "copper", "rose"];
    const accentSwatch = {
      gold: "#c8a35f",
      silver: "#c9ccd6",
      bronze: "#b8793f",
      copper: "#c17a52",
      rose: "#c99383"
    };
    const borderColors = [
      { value: "black", label: "Black", hint: "The standard border color" },
      { value: "white", label: "White", hint: "The alternate print color" },
      { value: "accent", label: "Accent", hint: "Matches the metal accent" }
    ];
    const cardFaces = [
      { value: "dark", label: "Dark", hint: "The default look" },
      { value: "parchment", label: "Parchment", hint: "Real parchment, dark ink" }
    ];
    const titlePositions = [
      { value: "top", label: "Top of card", hint: "The usual spot" },
      {
        value: "bottom",
        label: "Merged into stats",
        hint: "For art with its own logo up top"
      }
    ];
    const prestigeVariants = [
      { value: "foil", label: "Foil", hint: "Reflective sheen" },
      { value: "engraved", label: "Engraved", hint: "Etched, restrained" },
      { value: "ceremonial", label: "Ceremonial", hint: "Heavier ornate frame" },
      { value: "minimal", label: "Minimal", hint: "Barely there" }
    ];
    const rarities = [
      "common",
      "uncommon",
      "rare",
      "legendary",
      "mythic"
    ];
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("main", _hoisted_1, [
        createElementVNode("div", _hoisted_2, [
          createElementVNode("button", {
            type: "button",
            class: "back-btn",
            onClick: _cache[0] || (_cache[0] = ($event) => unref(router).push("/cards"))
          }, " \u2190 All cards "),
          game.value && card.value ? (openBlock(), createElementBlock("h1", _hoisted_3, [
            createTextVNode(
              toDisplayString(game.value.title) + " ",
              1
              /* TEXT */
            ),
            createElementVNode(
              "span",
              _hoisted_4,
              "#" + toDisplayString(String(card.value.archiveNumber ?? 0).padStart(3, "0")),
              1
              /* TEXT */
            )
          ])) : createCommentVNode("v-if", true)
        ]),
        loading.value ? (openBlock(), createElementBlock("p", _hoisted_5, "Loading\u2026")) : error.value ? (openBlock(), createElementBlock(
          "p",
          _hoisted_6,
          toDisplayString(error.value),
          1
          /* TEXT */
        )) : game.value && card.value ? (openBlock(), createElementBlock("div", _hoisted_7, [
          createElementVNode("div", _hoisted_8, [
            createElementVNode(
              "div",
              {
                class: "flip-scene",
                style: normalizeStyle(accentVars.value),
                onMousemove: onCardMouseMove,
                onMouseleave: onCardMouseLeave,
                onClick: _cache[2] || (_cache[2] = ($event) => flipped.value = !flipped.value)
              },
              [
                createElementVNode(
                  "div",
                  {
                    class: normalizeClass(["flip-card", { flipped: flipped.value }])
                  },
                  [
                    createElementVNode(
                      "div",
                      {
                        class: "tilt-layer",
                        style: normalizeStyle({
                          transform: `rotateX(${flipped.value ? -tiltX.value : tiltX.value}deg) rotateY(${tiltY.value}deg)`
                        })
                      },
                      [
                        createCommentVNode(" ============ FRONT ============ "),
                        createElementVNode("div", {
                          class: "card-face card-front",
                          "data-template": customization.value.frontTemplate,
                          "data-border-color": customization.value.borderColor,
                          "data-face": customization.value.cardFace,
                          "data-prestige": isPrestige.value,
                          "data-prestige-variant": customization.value.prestigeVariant,
                          "data-title-pos": customization.value.titlePosition
                        }, [
                          createElementVNode("div", _hoisted_10, [
                            createElementVNode("div", _hoisted_11, [
                              artSrc.value && !artFailed.value ? (openBlock(), createElementBlock("img", {
                                key: 0,
                                src: artSrc.value,
                                alt: "",
                                onError: _cache[1] || (_cache[1] = ($event) => artFailed.value = true)
                              }, null, 40, _hoisted_12)) : (openBlock(), createElementBlock("div", _hoisted_13))
                            ]),
                            _cache[21] || (_cache[21] = createElementVNode(
                              "div",
                              { class: "corner tl" },
                              null,
                              -1
                              /* CACHED */
                            )),
                            _cache[22] || (_cache[22] = createElementVNode(
                              "div",
                              { class: "corner br" },
                              null,
                              -1
                              /* CACHED */
                            )),
                            createElementVNode("div", _hoisted_14, [
                              createElementVNode("div", _hoisted_15, [
                                createElementVNode(
                                  "span",
                                  _hoisted_16,
                                  toDisplayString(game.value.title),
                                  1
                                  /* TEXT */
                                ),
                                createElementVNode(
                                  "span",
                                  _hoisted_17,
                                  toDisplayString(platformLabel.value) + " \xB7 #" + toDisplayString(String(card.value.archiveNumber ?? 0).padStart(3, "0")),
                                  1
                                  /* TEXT */
                                )
                              ]),
                              createElementVNode("div", _hoisted_18, [
                                createElementVNode("div", _hoisted_19, [
                                  createElementVNode("div", _hoisted_20, [
                                    _cache[18] || (_cache[18] = createElementVNode(
                                      "span",
                                      { class: "type-text" },
                                      "Achievement",
                                      -1
                                      /* CACHED */
                                    )),
                                    createElementVNode(
                                      "span",
                                      _hoisted_21,
                                      toDisplayString(game.value.title),
                                      1
                                      /* TEXT */
                                    ),
                                    createElementVNode(
                                      "span",
                                      {
                                        class: "type-sym icon-slot",
                                        style: normalizeStyle({ transform: rotStyle.value })
                                      },
                                      [
                                        customization.value.customSymbol ? (openBlock(), createElementBlock("img", {
                                          key: 0,
                                          src: customization.value.customSymbol,
                                          alt: ""
                                        }, null, 8, _hoisted_22)) : (openBlock(), createElementBlock("svg", {
                                          key: 1,
                                          viewBox: "0 0 24 24",
                                          fill: "currentColor",
                                          innerHTML: symbolInner()
                                        }, null, 8, _hoisted_23))
                                      ],
                                      4
                                      /* STYLE */
                                    )
                                  ]),
                                  createElementVNode("div", _hoisted_24, [
                                    achievementLabel.value ? (openBlock(), createElementBlock(
                                      "p",
                                      _hoisted_25,
                                      toDisplayString(achievementLabel.value),
                                      1
                                      /* TEXT */
                                    )) : createCommentVNode("v-if", true),
                                    playtimeLabel.value ? (openBlock(), createElementBlock(
                                      "p",
                                      _hoisted_26,
                                      toDisplayString(playtimeLabel.value) + " played. ",
                                      1
                                      /* TEXT */
                                    )) : createCommentVNode("v-if", true),
                                    game.value.ratingOverall ? (openBlock(), createElementBlock(
                                      "p",
                                      _hoisted_27,
                                      " Rated " + toDisplayString(game.value.ratingOverall.toFixed(1)) + " / 10. ",
                                      1
                                      /* TEXT */
                                    )) : createCommentVNode("v-if", true),
                                    _cache[19] || (_cache[19] = createElementVNode(
                                      "div",
                                      { class: "stat-rule" },
                                      null,
                                      -1
                                      /* CACHED */
                                    )),
                                    createElementVNode("p", _hoisted_28, [
                                      createTextVNode(
                                        toDisplayString(statusWord.value),
                                        1
                                        /* TEXT */
                                      ),
                                      completionYear.value ? (openBlock(), createElementBlock(
                                        Fragment,
                                        { key: 0 },
                                        [
                                          createTextVNode(
                                            " \xB7 " + toDisplayString(completionYear.value),
                                            1
                                            /* TEXT */
                                          )
                                        ],
                                        64
                                        /* STABLE_FRAGMENT */
                                      )) : createCommentVNode("v-if", true)
                                    ])
                                  ])
                                ]),
                                createElementVNode("div", _hoisted_29, [
                                  createElementVNode("span", _hoisted_30, [
                                    createElementVNode(
                                      "span",
                                      {
                                        class: "collector-sym icon-slot",
                                        style: normalizeStyle({ transform: rotStyle.value })
                                      },
                                      [
                                        customization.value.customSymbol ? (openBlock(), createElementBlock("img", {
                                          key: 0,
                                          src: customization.value.customSymbol,
                                          alt: ""
                                        }, null, 8, _hoisted_31)) : (openBlock(), createElementBlock("svg", {
                                          key: 1,
                                          viewBox: "0 0 24 24",
                                          fill: "currentColor",
                                          innerHTML: symbolInner()
                                        }, null, 8, _hoisted_32))
                                      ],
                                      4
                                      /* STYLE */
                                    ),
                                    setPositionLabel.value ? (openBlock(), createElementBlock(
                                      Fragment,
                                      { key: 0 },
                                      [
                                        createTextVNode(
                                          toDisplayString(setPositionLabel.value) + " ",
                                          1
                                          /* TEXT */
                                        ),
                                        setComplete.value ? (openBlock(), createElementBlock("span", _hoisted_33, "COMPLETE")) : createCommentVNode("v-if", true),
                                        _cache[20] || (_cache[20] = createTextVNode(
                                          " \xB7 ",
                                          -1
                                          /* CACHED */
                                        ))
                                      ],
                                      64
                                      /* STABLE_FRAGMENT */
                                    )) : createCommentVNode("v-if", true),
                                    createTextVNode(
                                      " " + toDisplayString(rarityLetter.value),
                                      1
                                      /* TEXT */
                                    )
                                  ]),
                                  createElementVNode(
                                    "span",
                                    _hoisted_34,
                                    toDisplayString(game.value.developer || ""),
                                    1
                                    /* TEXT */
                                  )
                                ])
                              ])
                            ])
                          ]),
                          _cache[23] || (_cache[23] = createElementVNode(
                            "div",
                            { class: "prestige-shine" },
                            null,
                            -1
                            /* CACHED */
                          )),
                          _cache[24] || (_cache[24] = createElementVNode(
                            "div",
                            { class: "grain" },
                            null,
                            -1
                            /* CACHED */
                          ))
                        ], 8, _hoisted_9),
                        createCommentVNode(" ============ BACK ============ "),
                        createElementVNode("div", {
                          class: "card-face card-back-inner",
                          "data-face": customization.value.cardFace
                        }, [
                          withDirectives(createElementVNode(
                            "div",
                            _hoisted_36,
                            [
                              _cache[25] || (_cache[25] = createElementVNode(
                                "div",
                                { class: "back-corner tl" },
                                null,
                                -1
                                /* CACHED */
                              )),
                              _cache[26] || (_cache[26] = createElementVNode(
                                "div",
                                { class: "back-corner br" },
                                null,
                                -1
                                /* CACHED */
                              )),
                              createElementVNode("div", _hoisted_37, [
                                createElementVNode(
                                  "span",
                                  {
                                    class: "icon-slot",
                                    style: normalizeStyle({ transform: rotStyle.value })
                                  },
                                  [
                                    customization.value.customSymbol ? (openBlock(), createElementBlock("img", {
                                      key: 0,
                                      src: customization.value.customSymbol,
                                      alt: ""
                                    }, null, 8, _hoisted_38)) : (openBlock(), createElementBlock("svg", {
                                      key: 1,
                                      viewBox: "0 0 24 24",
                                      fill: "currentColor",
                                      innerHTML: symbolInner()
                                    }, null, 8, _hoisted_39))
                                  ],
                                  4
                                  /* STYLE */
                                ),
                                hasSecondarySymbol.value ? (openBlock(), createElementBlock("div", _hoisted_40, [
                                  createElementVNode("span", _hoisted_41, [
                                    (openBlock(), createElementBlock("svg", {
                                      viewBox: "0 0 24 24",
                                      fill: "currentColor",
                                      innerHTML: symbolInner(customization.value.symbol2)
                                    }, null, 8, _hoisted_42))
                                  ])
                                ])) : createCommentVNode("v-if", true)
                              ]),
                              _cache[27] || (_cache[27] = createElementVNode(
                                "div",
                                { class: "back-wordmark" },
                                "ARCHIVE",
                                -1
                                /* CACHED */
                              )),
                              createElementVNode(
                                "div",
                                _hoisted_43,
                                toDisplayString(currentSet.value?.name || "No set"),
                                1
                                /* TEXT */
                              ),
                              createElementVNode(
                                "div",
                                _hoisted_44,
                                " #" + toDisplayString(String(card.value.archiveNumber ?? 0).padStart(3, "0")),
                                1
                                /* TEXT */
                              )
                            ],
                            512
                            /* NEED_PATCH */
                          ), [
                            [vShow, customization.value.backTemplate === "emblem"]
                          ]),
                          withDirectives(createElementVNode(
                            "div",
                            _hoisted_45,
                            [
                              _cache[35] || (_cache[35] = createElementVNode(
                                "div",
                                { class: "back-corner tl" },
                                null,
                                -1
                                /* CACHED */
                              )),
                              _cache[36] || (_cache[36] = createElementVNode(
                                "div",
                                { class: "back-corner br" },
                                null,
                                -1
                                /* CACHED */
                              )),
                              createElementVNode("div", _hoisted_46, [
                                createElementVNode(
                                  "span",
                                  {
                                    class: "icon-slot",
                                    style: normalizeStyle({ transform: rotStyle.value })
                                  },
                                  [
                                    customization.value.customSymbol ? (openBlock(), createElementBlock("img", {
                                      key: 0,
                                      src: customization.value.customSymbol,
                                      alt: ""
                                    }, null, 8, _hoisted_47)) : (openBlock(), createElementBlock("svg", {
                                      key: 1,
                                      viewBox: "0 0 24 24",
                                      fill: "currentColor",
                                      innerHTML: symbolInner()
                                    }, null, 8, _hoisted_48))
                                  ],
                                  4
                                  /* STYLE */
                                )
                              ]),
                              createElementVNode("div", _hoisted_49, [
                                createElementVNode(
                                  "div",
                                  _hoisted_50,
                                  toDisplayString(game.value.title),
                                  1
                                  /* TEXT */
                                ),
                                createElementVNode("div", _hoisted_51, [
                                  createElementVNode("div", _hoisted_52, [
                                    _cache[28] || (_cache[28] = createElementVNode(
                                      "span",
                                      { class: "lbl" },
                                      "Set",
                                      -1
                                      /* CACHED */
                                    )),
                                    createElementVNode(
                                      "span",
                                      _hoisted_53,
                                      toDisplayString(setPositionLabel.value || "\u2013"),
                                      1
                                      /* TEXT */
                                    )
                                  ]),
                                  createElementVNode("div", _hoisted_54, [
                                    _cache[29] || (_cache[29] = createElementVNode(
                                      "span",
                                      { class: "lbl" },
                                      "Platform",
                                      -1
                                      /* CACHED */
                                    )),
                                    createElementVNode(
                                      "span",
                                      _hoisted_55,
                                      toDisplayString(platformLabel.value),
                                      1
                                      /* TEXT */
                                    )
                                  ]),
                                  createElementVNode("div", _hoisted_56, [
                                    _cache[30] || (_cache[30] = createElementVNode(
                                      "span",
                                      { class: "lbl" },
                                      "Completed",
                                      -1
                                      /* CACHED */
                                    )),
                                    createElementVNode(
                                      "span",
                                      _hoisted_57,
                                      toDisplayString(completionYear.value || "\u2013"),
                                      1
                                      /* TEXT */
                                    )
                                  ]),
                                  createElementVNode("div", _hoisted_58, [
                                    _cache[31] || (_cache[31] = createElementVNode(
                                      "span",
                                      { class: "lbl" },
                                      "Playtime",
                                      -1
                                      /* CACHED */
                                    )),
                                    createElementVNode(
                                      "span",
                                      _hoisted_59,
                                      toDisplayString(playtimeLabel.value || "\u2013"),
                                      1
                                      /* TEXT */
                                    )
                                  ])
                                ]),
                                createElementVNode("div", _hoisted_60, [
                                  createElementVNode(
                                    "span",
                                    _hoisted_61,
                                    toDisplayString(rarity.value ? RARITY_LABEL[rarity.value] : "Unrated"),
                                    1
                                    /* TEXT */
                                  ),
                                  isPrestige.value ? (openBlock(), createElementBlock("span", _hoisted_62, "Prestiged")) : createCommentVNode("v-if", true)
                                ]),
                                customization.value.memorableAchievement ? (openBlock(), createElementBlock("div", _hoisted_63, [
                                  _cache[32] || (_cache[32] = createElementVNode(
                                    "span",
                                    { class: "lbl" },
                                    "Memorable achievement",
                                    -1
                                    /* CACHED */
                                  )),
                                  createElementVNode(
                                    "div",
                                    _hoisted_64,
                                    toDisplayString(customization.value.memorableAchievement),
                                    1
                                    /* TEXT */
                                  )
                                ])) : createCommentVNode("v-if", true),
                                customization.value.personalNote ? (openBlock(), createElementBlock("div", _hoisted_65, [
                                  _cache[33] || (_cache[33] = createElementVNode(
                                    "span",
                                    { class: "lbl" },
                                    "Personal note",
                                    -1
                                    /* CACHED */
                                  )),
                                  createElementVNode(
                                    "div",
                                    _hoisted_66,
                                    toDisplayString(customization.value.personalNote),
                                    1
                                    /* TEXT */
                                  )
                                ])) : createCommentVNode("v-if", true),
                                isPrestige.value && bounty.value ? (openBlock(), createElementBlock("div", _hoisted_67, [
                                  _cache[34] || (_cache[34] = createElementVNode(
                                    "span",
                                    { class: "lbl" },
                                    "The challenge",
                                    -1
                                    /* CACHED */
                                  )),
                                  createElementVNode(
                                    "div",
                                    _hoisted_68,
                                    toDisplayString(bounty.value.title),
                                    1
                                    /* TEXT */
                                  )
                                ])) : createCommentVNode("v-if", true)
                              ])
                            ],
                            512
                            /* NEED_PATCH */
                          ), [
                            [vShow, customization.value.backTemplate === "collector"]
                          ]),
                          withDirectives(createElementVNode(
                            "div",
                            _hoisted_69,
                            [
                              _cache[39] || (_cache[39] = createElementVNode(
                                "div",
                                { class: "back-corner tl" },
                                null,
                                -1
                                /* CACHED */
                              )),
                              _cache[40] || (_cache[40] = createElementVNode(
                                "div",
                                { class: "back-corner br" },
                                null,
                                -1
                                /* CACHED */
                              )),
                              createElementVNode("div", _hoisted_70, [
                                createElementVNode("span", _hoisted_71, [
                                  customization.value.customSymbol ? (openBlock(), createElementBlock("img", {
                                    key: 0,
                                    src: customization.value.customSymbol,
                                    alt: ""
                                  }, null, 8, _hoisted_72)) : (openBlock(), createElementBlock("svg", {
                                    key: 1,
                                    viewBox: "0 0 24 24",
                                    fill: "currentColor",
                                    innerHTML: symbolInner()
                                  }, null, 8, _hoisted_73))
                                ]),
                                _cache[37] || (_cache[37] = createElementVNode(
                                  "span",
                                  { class: "record-top-label" },
                                  "Archive Card",
                                  -1
                                  /* CACHED */
                                )),
                                createElementVNode(
                                  "span",
                                  _hoisted_74,
                                  "#" + toDisplayString(String(card.value.archiveNumber ?? 0).padStart(3, "0")),
                                  1
                                  /* TEXT */
                                )
                              ]),
                              createElementVNode("div", _hoisted_75, [
                                createElementVNode(
                                  "div",
                                  _hoisted_76,
                                  toDisplayString(game.value.title),
                                  1
                                  /* TEXT */
                                ),
                                createElementVNode("div", _hoisted_77, [
                                  createTextVNode(
                                    toDisplayString(statusWord.value),
                                    1
                                    /* TEXT */
                                  ),
                                  completionYear.value ? (openBlock(), createElementBlock(
                                    Fragment,
                                    { key: 0 },
                                    [
                                      createTextVNode(
                                        toDisplayString(completionYear.value),
                                        1
                                        /* TEXT */
                                      )
                                    ],
                                    64
                                    /* STABLE_FRAGMENT */
                                  )) : createCommentVNode("v-if", true)
                                ]),
                                createElementVNode("div", _hoisted_78, [
                                  createTextVNode(
                                    toDisplayString(platformLabel.value),
                                    1
                                    /* TEXT */
                                  ),
                                  playtimeLabel.value ? (openBlock(), createElementBlock(
                                    Fragment,
                                    { key: 0 },
                                    [
                                      createTextVNode(
                                        " \xB7 " + toDisplayString(playtimeLabel.value),
                                        1
                                        /* TEXT */
                                      )
                                    ],
                                    64
                                    /* STABLE_FRAGMENT */
                                  )) : createCommentVNode("v-if", true)
                                ])
                              ]),
                              customization.value.memorableAchievement ? (openBlock(), createElementBlock("div", _hoisted_79, [
                                _cache[38] || (_cache[38] = createElementVNode(
                                  "div",
                                  { class: "record-moment-label" },
                                  " Most memorable achievement ",
                                  -1
                                  /* CACHED */
                                )),
                                createElementVNode(
                                  "div",
                                  _hoisted_80,
                                  toDisplayString(customization.value.memorableAchievement),
                                  1
                                  /* TEXT */
                                ),
                                customization.value.personalNote ? (openBlock(), createElementBlock(
                                  "div",
                                  _hoisted_81,
                                  toDisplayString(customization.value.personalNote),
                                  1
                                  /* TEXT */
                                )) : createCommentVNode("v-if", true)
                              ])) : createCommentVNode("v-if", true),
                              createElementVNode("div", _hoisted_82, [
                                createElementVNode(
                                  "span",
                                  null,
                                  toDisplayString(currentSet.value ? currentSet.value.name : "No set"),
                                  1
                                  /* TEXT */
                                ),
                                createElementVNode(
                                  "span",
                                  null,
                                  toDisplayString(rarity.value ? RARITY_LABEL[rarity.value] : "Unrated"),
                                  1
                                  /* TEXT */
                                )
                              ])
                            ],
                            512
                            /* NEED_PATCH */
                          ), [
                            [vShow, customization.value.backTemplate === "record"]
                          ]),
                          _cache[41] || (_cache[41] = createElementVNode(
                            "div",
                            { class: "grain" },
                            null,
                            -1
                            /* CACHED */
                          ))
                        ], 8, _hoisted_35)
                      ],
                      4
                      /* STYLE */
                    )
                  ],
                  2
                  /* CLASS */
                )
              ],
              36
              /* STYLE, NEED_HYDRATION */
            ),
            createElementVNode("div", _hoisted_83, [
              createElementVNode("button", {
                type: "button",
                class: "flip-btn",
                onClick: _cache[3] || (_cache[3] = withModifiers(($event) => flipped.value = !flipped.value, ["stop"]))
              }, " Flip card "),
              createElementVNode("button", {
                type: "button",
                class: "flip-btn",
                onClick: withModifiers(printCard, ["stop"])
              }, " Print ")
            ]),
            _cache[42] || (_cache[42] = createElementVNode(
              "p",
              { class: "print-note" },
              " Prints both faces at true 2.5\xD73.5in size. Foil is simulated, not real foil. ",
              -1
              /* CACHED */
            ))
          ]),
          createElementVNode("aside", _hoisted_84, [
            createElementVNode("div", _hoisted_85, [
              createElementVNode(
                "button",
                {
                  type: "button",
                  class: normalizeClass(["tab", { active: activeTab.value === "template" }]),
                  onClick: _cache[4] || (_cache[4] = ($event) => activeTab.value = "template")
                },
                " Template ",
                2
                /* CLASS */
              ),
              createElementVNode(
                "button",
                {
                  type: "button",
                  class: normalizeClass(["tab", { active: activeTab.value === "prestige" }]),
                  onClick: _cache[5] || (_cache[5] = ($event) => activeTab.value = "prestige")
                },
                " Prestige ",
                2
                /* CLASS */
              ),
              createElementVNode(
                "button",
                {
                  type: "button",
                  class: normalizeClass(["tab", { active: activeTab.value === "symbol" }]),
                  onClick: _cache[6] || (_cache[6] = ($event) => activeTab.value = "symbol")
                },
                " Symbol ",
                2
                /* CLASS */
              ),
              createElementVNode(
                "button",
                {
                  type: "button",
                  class: normalizeClass(["tab", { active: activeTab.value === "data" }]),
                  onClick: _cache[7] || (_cache[7] = ($event) => activeTab.value = "data")
                },
                " Data ",
                2
                /* CLASS */
              ),
              createElementVNode(
                "button",
                {
                  type: "button",
                  class: normalizeClass(["tab", { active: activeTab.value === "set" }]),
                  onClick: _cache[8] || (_cache[8] = ($event) => activeTab.value = "set")
                },
                " Rarity & Set ",
                2
                /* CLASS */
              )
            ]),
            createElementVNode("div", _hoisted_86, [
              withDirectives(createElementVNode(
                "div",
                _hoisted_87,
                [
                  createElementVNode("div", _hoisted_88, [
                    _cache[43] || (_cache[43] = createElementVNode(
                      "label",
                      null,
                      "Front template",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode("div", _hoisted_89, [
                      (openBlock(), createElementBlock(
                        Fragment,
                        null,
                        renderList(frontTemplates, (t) => {
                          return createElementVNode("button", {
                            key: t.value,
                            type: "button",
                            class: normalizeClass(["tpl-btn", { active: customization.value.frontTemplate === t.value }]),
                            onClick: ($event) => customization.value.frontTemplate = t.value
                          }, [
                            createTextVNode(
                              toDisplayString(t.label),
                              1
                              /* TEXT */
                            ),
                            createElementVNode(
                              "span",
                              null,
                              toDisplayString(t.hint),
                              1
                              /* TEXT */
                            )
                          ], 10, _hoisted_90);
                        }),
                        64
                        /* STABLE_FRAGMENT */
                      ))
                    ])
                  ]),
                  customization.value.frontTemplate === "bordered" ? (openBlock(), createElementBlock("div", _hoisted_91, [
                    _cache[44] || (_cache[44] = createElementVNode(
                      "label",
                      null,
                      "Border color",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode("div", _hoisted_92, [
                      (openBlock(), createElementBlock(
                        Fragment,
                        null,
                        renderList(borderColors, (b) => {
                          return createElementVNode("button", {
                            key: b.value,
                            type: "button",
                            class: normalizeClass(["tpl-btn", { active: customization.value.borderColor === b.value }]),
                            onClick: ($event) => customization.value.borderColor = b.value
                          }, [
                            createTextVNode(
                              toDisplayString(b.label),
                              1
                              /* TEXT */
                            ),
                            createElementVNode(
                              "span",
                              null,
                              toDisplayString(b.hint),
                              1
                              /* TEXT */
                            )
                          ], 10, _hoisted_93);
                        }),
                        64
                        /* STABLE_FRAGMENT */
                      ))
                    ])
                  ])) : createCommentVNode("v-if", true),
                  createElementVNode("div", _hoisted_94, [
                    _cache[45] || (_cache[45] = createElementVNode(
                      "label",
                      null,
                      "Title position",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode("div", _hoisted_95, [
                      (openBlock(), createElementBlock(
                        Fragment,
                        null,
                        renderList(titlePositions, (t) => {
                          return createElementVNode("button", {
                            key: t.value,
                            type: "button",
                            class: normalizeClass(["tpl-btn", { active: customization.value.titlePosition === t.value }]),
                            onClick: ($event) => customization.value.titlePosition = t.value
                          }, [
                            createTextVNode(
                              toDisplayString(t.label),
                              1
                              /* TEXT */
                            ),
                            createElementVNode(
                              "span",
                              null,
                              toDisplayString(t.hint),
                              1
                              /* TEXT */
                            )
                          ], 10, _hoisted_96);
                        }),
                        64
                        /* STABLE_FRAGMENT */
                      ))
                    ])
                  ]),
                  createElementVNode("div", _hoisted_97, [
                    _cache[46] || (_cache[46] = createElementVNode(
                      "label",
                      null,
                      "Back template",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode("div", _hoisted_98, [
                      (openBlock(), createElementBlock(
                        Fragment,
                        null,
                        renderList(backTemplates, (t) => {
                          return createElementVNode("button", {
                            key: t.value,
                            type: "button",
                            class: normalizeClass(["tpl-btn", { active: customization.value.backTemplate === t.value }]),
                            onClick: ($event) => customization.value.backTemplate = t.value
                          }, [
                            createTextVNode(
                              toDisplayString(t.label),
                              1
                              /* TEXT */
                            ),
                            createElementVNode(
                              "span",
                              null,
                              toDisplayString(t.hint),
                              1
                              /* TEXT */
                            )
                          ], 10, _hoisted_99);
                        }),
                        64
                        /* STABLE_FRAGMENT */
                      ))
                    ])
                  ]),
                  createElementVNode("div", _hoisted_100, [
                    _cache[47] || (_cache[47] = createElementVNode(
                      "label",
                      null,
                      "Card face",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode("div", _hoisted_101, [
                      (openBlock(), createElementBlock(
                        Fragment,
                        null,
                        renderList(cardFaces, (f) => {
                          return createElementVNode("button", {
                            key: f.value,
                            type: "button",
                            class: normalizeClass(["tpl-btn", { active: customization.value.cardFace === f.value }]),
                            onClick: ($event) => customization.value.cardFace = f.value
                          }, [
                            createTextVNode(
                              toDisplayString(f.label),
                              1
                              /* TEXT */
                            ),
                            createElementVNode(
                              "span",
                              null,
                              toDisplayString(f.hint),
                              1
                              /* TEXT */
                            )
                          ], 10, _hoisted_102);
                        }),
                        64
                        /* STABLE_FRAGMENT */
                      ))
                    ])
                  ]),
                  createElementVNode("div", _hoisted_103, [
                    _cache[48] || (_cache[48] = createElementVNode(
                      "label",
                      null,
                      "Metal accent",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode("div", _hoisted_104, [
                      (openBlock(), createElementBlock(
                        Fragment,
                        null,
                        renderList(accents, (a) => {
                          return createElementVNode("button", {
                            key: a,
                            type: "button",
                            class: normalizeClass(["accent-btn", { active: customization.value.accent === a }]),
                            style: normalizeStyle({ background: accentSwatch[a] }),
                            onClick: ($event) => customization.value.accent = a
                          }, null, 14, _hoisted_105);
                        }),
                        64
                        /* STABLE_FRAGMENT */
                      ))
                    ])
                  ])
                ],
                512
                /* NEED_PATCH */
              ), [
                [vShow, activeTab.value === "template"]
              ]),
              withDirectives(createElementVNode(
                "div",
                _hoisted_106,
                [
                  !achievements100.value ? (openBlock(), createElementBlock("div", _hoisted_107, [
                    _cache[49] || (_cache[49] = createElementVNode(
                      "label",
                      null,
                      "Prestige",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode(
                      "div",
                      _hoisted_108,
                      " Earn every achievement in " + toDisplayString(game.value?.title) + " to unlock a prestige challenge. There's nothing to pick here. The system generates the challenge itself once you're at 100%. ",
                      1
                      /* TEXT */
                    )
                  ])) : !bounty.value ? (openBlock(), createElementBlock("div", _hoisted_109, [
                    _cache[50] || (_cache[50] = createElementVNode(
                      "label",
                      null,
                      "Prestige",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode(
                      "div",
                      _hoisted_110,
                      " 100% complete. Generate the one prestige challenge for this card, a real goal built from " + toDisplayString(game.value?.title) + "'s own data, tracked and verified through Bounties. ",
                      1
                      /* TEXT */
                    ),
                    createElementVNode("button", {
                      type: "button",
                      class: "primary-btn",
                      disabled: generatingPrestige.value,
                      onClick: generatePrestige
                    }, toDisplayString(generatingPrestige.value ? "Generating\u2026" : "Generate prestige challenge"), 9, _hoisted_111),
                    prestigeError.value ? (openBlock(), createElementBlock(
                      "div",
                      _hoisted_112,
                      toDisplayString(prestigeError.value),
                      1
                      /* TEXT */
                    )) : createCommentVNode("v-if", true)
                  ])) : (openBlock(), createElementBlock(
                    Fragment,
                    { key: 2 },
                    [
                      createElementVNode("div", _hoisted_113, [
                        _cache[52] || (_cache[52] = createElementVNode(
                          "label",
                          null,
                          "Prestige challenge",
                          -1
                          /* CACHED */
                        )),
                        createElementVNode("div", _hoisted_114, [
                          createElementVNode(
                            "div",
                            _hoisted_115,
                            toDisplayString(bounty.value.title),
                            1
                            /* TEXT */
                          ),
                          createElementVNode(
                            "span",
                            {
                              class: normalizeClass(["bc-pill", {
                                "bc-pill-prestige": bounty.value.status === "completed"
                              }])
                            },
                            toDisplayString(bounty.value.status.replace("_", " ")),
                            3
                            /* TEXT, CLASS */
                          )
                        ]),
                        createElementVNode(
                          "div",
                          _hoisted_116,
                          toDisplayString(bounty.value.description),
                          1
                          /* TEXT */
                        ),
                        createVNode(unref(RouterLink), {
                          class: "reset-link",
                          to: "/bounties"
                        }, {
                          default: withCtx(() => [..._cache[51] || (_cache[51] = [
                            createTextVNode(
                              "Manage in Bounties \u2192",
                              -1
                              /* CACHED */
                            )
                          ])]),
                          _: 1
                          /* STABLE */
                        })
                      ]),
                      isPrestige.value ? (openBlock(), createElementBlock("div", _hoisted_117, [
                        _cache[53] || (_cache[53] = createElementVNode(
                          "label",
                          null,
                          "Prestige treatment",
                          -1
                          /* CACHED */
                        )),
                        createElementVNode("div", _hoisted_118, [
                          (openBlock(), createElementBlock(
                            Fragment,
                            null,
                            renderList(prestigeVariants, (v) => {
                              return createElementVNode("button", {
                                key: v.value,
                                type: "button",
                                class: normalizeClass(["tpl-btn", {
                                  active: customization.value.prestigeVariant === v.value
                                }]),
                                onClick: ($event) => customization.value.prestigeVariant = v.value
                              }, [
                                createTextVNode(
                                  toDisplayString(v.label),
                                  1
                                  /* TEXT */
                                ),
                                createElementVNode(
                                  "span",
                                  null,
                                  toDisplayString(v.hint),
                                  1
                                  /* TEXT */
                                )
                              ], 10, _hoisted_119);
                            }),
                            64
                            /* STABLE_FRAGMENT */
                          ))
                        ])
                      ])) : createCommentVNode("v-if", true)
                    ],
                    64
                    /* STABLE_FRAGMENT */
                  ))
                ],
                512
                /* NEED_PATCH */
              ), [
                [vShow, activeTab.value === "prestige"]
              ]),
              withDirectives(createElementVNode(
                "div",
                _hoisted_120,
                [
                  createElementVNode("div", _hoisted_121, [
                    _cache[55] || (_cache[55] = createElementVNode(
                      "label",
                      null,
                      "Primary symbol",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode("button", {
                      type: "button",
                      class: "symbol-trigger",
                      onClick: _cache[9] || (_cache[9] = ($event) => symbolModalOpen.value = true)
                    }, [
                      createElementVNode(
                        "span",
                        {
                          class: "icon-slot",
                          style: normalizeStyle({ transform: rotStyle.value })
                        },
                        [
                          customization.value.customSymbol ? (openBlock(), createElementBlock("img", {
                            key: 0,
                            src: customization.value.customSymbol,
                            alt: ""
                          }, null, 8, _hoisted_122)) : (openBlock(), createElementBlock("svg", {
                            key: 1,
                            viewBox: "0 0 24 24",
                            fill: "currentColor",
                            innerHTML: symbolInner()
                          }, null, 8, _hoisted_123))
                        ],
                        4
                        /* STYLE */
                      ),
                      _cache[54] || (_cache[54] = createElementVNode(
                        "span",
                        { class: "symbol-trigger-text" },
                        "Choose symbol\u2026",
                        -1
                        /* CACHED */
                      ))
                    ])
                  ])
                ],
                512
                /* NEED_PATCH */
              ), [
                [vShow, activeTab.value === "symbol"]
              ]),
              withDirectives(createElementVNode(
                "div",
                _hoisted_124,
                [
                  createElementVNode("div", _hoisted_125, [
                    _cache[56] || (_cache[56] = createElementVNode(
                      "label",
                      null,
                      "Card art",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode("label", _hoisted_126, [
                      createElementVNode(
                        "span",
                        null,
                        toDisplayString(customization.value.customArt ? "Replace card art" : "Upload card art"),
                        1
                        /* TEXT */
                      ),
                      createElementVNode(
                        "input",
                        {
                          type: "file",
                          accept: "image/*",
                          onChange: onArtUpload
                        },
                        null,
                        32
                        /* NEED_HYDRATION */
                      )
                    ]),
                    _cache[57] || (_cache[57] = createElementVNode(
                      "div",
                      { class: "field-hint" },
                      " Uses the game's own cover art by default. Nothing leaves your browser. ",
                      -1
                      /* CACHED */
                    )),
                    customization.value.customArt ? (openBlock(), createElementBlock("button", {
                      key: 0,
                      type: "button",
                      class: "reset-link",
                      onClick: resetArt
                    }, " Reset to game cover ")) : createCommentVNode("v-if", true)
                  ]),
                  createElementVNode("div", _hoisted_127, [
                    _cache[58] || (_cache[58] = createElementVNode(
                      "label",
                      null,
                      "Memorable achievement",
                      -1
                      /* CACHED */
                    )),
                    withDirectives(createElementVNode(
                      "input",
                      {
                        "onUpdate:modelValue": _cache[10] || (_cache[10] = ($event) => customization.value.memorableAchievement = $event),
                        type: "text",
                        maxlength: "80",
                        class: "text-input",
                        placeholder: "The one you actually want remembered"
                      },
                      null,
                      512
                      /* NEED_PATCH */
                    ), [
                      [vModelText, customization.value.memorableAchievement]
                    ])
                  ]),
                  createElementVNode("div", _hoisted_128, [
                    _cache[59] || (_cache[59] = createElementVNode(
                      "label",
                      null,
                      "Personal note (back only)",
                      -1
                      /* CACHED */
                    )),
                    withDirectives(createElementVNode(
                      "textarea",
                      {
                        "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => customization.value.personalNote = $event),
                        maxlength: "300",
                        class: "text-input textarea-input",
                        placeholder: "Why it mattered"
                      },
                      null,
                      512
                      /* NEED_PATCH */
                    ), [
                      [vModelText, customization.value.personalNote]
                    ])
                  ])
                ],
                512
                /* NEED_PATCH */
              ), [
                [vShow, activeTab.value === "data"]
              ]),
              withDirectives(createElementVNode(
                "div",
                _hoisted_129,
                [
                  createElementVNode("div", _hoisted_130, [
                    _cache[60] || (_cache[60] = createElementVNode(
                      "label",
                      null,
                      "Rarity",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode("div", _hoisted_131, [
                      (openBlock(), createElementBlock(
                        Fragment,
                        null,
                        renderList(rarities, (r) => {
                          return createElementVNode("button", {
                            key: r,
                            type: "button",
                            class: normalizeClass(["rarity-btn", { active: rarity.value === r }]),
                            onClick: ($event) => rarity.value = r
                          }, toDisplayString(RARITY_LABEL[r]), 11, _hoisted_132);
                        }),
                        64
                        /* STABLE_FRAGMENT */
                      ))
                    ])
                  ]),
                  createElementVNode("div", _hoisted_133, [
                    _cache[62] || (_cache[62] = createElementVNode(
                      "label",
                      null,
                      "Set",
                      -1
                      /* CACHED */
                    )),
                    withDirectives(createElementVNode(
                      "select",
                      {
                        "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => setId.value = $event),
                        class: "select-input"
                      },
                      [
                        _cache[61] || (_cache[61] = createElementVNode(
                          "option",
                          { value: null },
                          "No set",
                          -1
                          /* CACHED */
                        )),
                        (openBlock(true), createElementBlock(
                          Fragment,
                          null,
                          renderList(sets.value, (s) => {
                            return openBlock(), createElementBlock("option", {
                              key: s.id,
                              value: s.id
                            }, toDisplayString(s.name), 9, _hoisted_134);
                          }),
                          128
                          /* KEYED_FRAGMENT */
                        ))
                      ],
                      512
                      /* NEED_PATCH */
                    ), [
                      [vModelSelect, setId.value]
                    ]),
                    _cache[63] || (_cache[63] = createElementVNode(
                      "div",
                      { class: "field-hint" },
                      "Manage sets from the Sets page.",
                      -1
                      /* CACHED */
                    ))
                  ])
                ],
                512
                /* NEED_PATCH */
              ), [
                [vShow, activeTab.value === "set"]
              ])
            ]),
            createElementVNode("div", _hoisted_135, [
              createElementVNode("button", {
                type: "button",
                class: "save-btn",
                disabled: saving.value,
                onClick: saveCard
              }, toDisplayString(saving.value ? "Saving\u2026" : saved.value ? "Saved" : "Save"), 9, _hoisted_136)
            ])
          ])
        ])) : createCommentVNode("v-if", true),
        createCommentVNode(" ============ SYMBOL MODAL ============ "),
        symbolModalOpen.value ? (openBlock(), createElementBlock("div", {
          key: 3,
          class: "modal-backdrop",
          onClick: _cache[17] || (_cache[17] = withModifiers(($event) => symbolModalOpen.value = false, ["self"]))
        }, [
          createElementVNode("div", _hoisted_137, [
            createElementVNode("div", _hoisted_138, [
              _cache[64] || (_cache[64] = createElementVNode(
                "h2",
                null,
                "Symbol",
                -1
                /* CACHED */
              )),
              createElementVNode("button", {
                type: "button",
                class: "modal-close",
                onClick: _cache[13] || (_cache[13] = ($event) => symbolModalOpen.value = false)
              }, " \xD7 ")
            ]),
            createElementVNode("div", _hoisted_139, [
              createElementVNode("div", _hoisted_140, [
                _cache[65] || (_cache[65] = createElementVNode(
                  "label",
                  null,
                  "Primary symbol",
                  -1
                  /* CACHED */
                )),
                createElementVNode("div", _hoisted_141, [
                  (openBlock(true), createElementBlock(
                    Fragment,
                    null,
                    renderList(unref(CARD_SYMBOL_ORDER), (key) => {
                      return openBlock(), createElementBlock("button", {
                        key,
                        type: "button",
                        class: normalizeClass(["icon-btn", { active: customization.value.symbol === key }]),
                        onClick: ($event) => customization.value.symbol = key
                      }, [
                        createElementVNode("span", _hoisted_143, [
                          (openBlock(), createElementBlock("svg", {
                            viewBox: "0 0 24 24",
                            fill: "currentColor",
                            innerHTML: symbolInner(key)
                          }, null, 8, _hoisted_144))
                        ])
                      ], 10, _hoisted_142);
                    }),
                    128
                    /* KEYED_FRAGMENT */
                  ))
                ])
              ]),
              createElementVNode("div", _hoisted_145, [
                _cache[67] || (_cache[67] = createElementVNode(
                  "label",
                  null,
                  "Rotation",
                  -1
                  /* CACHED */
                )),
                createElementVNode("div", _hoisted_146, [
                  createElementVNode("div", _hoisted_147, [
                    _cache[66] || (_cache[66] = createElementVNode(
                      "span",
                      null,
                      "Tilts the primary symbol wherever it's shown",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode(
                      "b",
                      null,
                      toDisplayString(customization.value.symbolRotation) + "\xB0",
                      1
                      /* TEXT */
                    )
                  ]),
                  withDirectives(createElementVNode(
                    "input",
                    {
                      "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => customization.value.symbolRotation = $event),
                      type: "range",
                      min: "-45",
                      max: "45"
                    },
                    null,
                    512
                    /* NEED_PATCH */
                  ), [
                    [
                      vModelText,
                      customization.value.symbolRotation,
                      void 0,
                      { number: true }
                    ]
                  ])
                ])
              ]),
              createElementVNode("div", _hoisted_148, [
                _cache[68] || (_cache[68] = createElementVNode(
                  "label",
                  null,
                  "Combine with a second symbol (back medallion badge only)",
                  -1
                  /* CACHED */
                )),
                createElementVNode("div", _hoisted_149, [
                  createElementVNode(
                    "button",
                    {
                      type: "button",
                      class: normalizeClass(["icon-btn none-btn", { active: customization.value.symbol2 === "none" }]),
                      onClick: _cache[15] || (_cache[15] = ($event) => customization.value.symbol2 = "none")
                    },
                    " None ",
                    2
                    /* CLASS */
                  ),
                  (openBlock(true), createElementBlock(
                    Fragment,
                    null,
                    renderList(unref(CARD_SYMBOL_ORDER), (key) => {
                      return openBlock(), createElementBlock("button", {
                        key,
                        type: "button",
                        class: normalizeClass(["icon-btn", { active: customization.value.symbol2 === key }]),
                        onClick: ($event) => customization.value.symbol2 = key
                      }, [
                        createElementVNode("span", _hoisted_151, [
                          (openBlock(), createElementBlock("svg", {
                            viewBox: "0 0 24 24",
                            fill: "currentColor",
                            innerHTML: symbolInner(key)
                          }, null, 8, _hoisted_152))
                        ])
                      ], 10, _hoisted_150);
                    }),
                    128
                    /* KEYED_FRAGMENT */
                  ))
                ])
              ]),
              createElementVNode("div", _hoisted_153, [
                _cache[70] || (_cache[70] = createElementVNode(
                  "label",
                  null,
                  "Or upload your own icon",
                  -1
                  /* CACHED */
                )),
                createElementVNode("div", _hoisted_154, [
                  customization.value.customSymbol ? (openBlock(), createElementBlock("span", _hoisted_155, [
                    createElementVNode("img", {
                      src: customization.value.customSymbol,
                      alt: ""
                    }, null, 8, _hoisted_156)
                  ])) : createCommentVNode("v-if", true),
                  createElementVNode("label", _hoisted_157, [
                    _cache[69] || (_cache[69] = createElementVNode(
                      "span",
                      null,
                      "Upload icon",
                      -1
                      /* CACHED */
                    )),
                    createElementVNode(
                      "input",
                      {
                        type: "file",
                        accept: "image/*",
                        onChange: onCustomSymbolUpload
                      },
                      null,
                      32
                      /* NEED_HYDRATION */
                    )
                  ]),
                  customization.value.customSymbol ? (openBlock(), createElementBlock("button", {
                    key: 1,
                    class: "reset-link",
                    type: "button",
                    onClick: clearCustomSymbol
                  }, " Remove ")) : createCommentVNode("v-if", true)
                ]),
                _cache[71] || (_cache[71] = createElementVNode(
                  "div",
                  { class: "field-hint" },
                  " Tinted to match the metal accent, replaces the built-in symbol everywhere. ",
                  -1
                  /* CACHED */
                ))
              ])
            ]),
            createElementVNode("div", _hoisted_158, [
              createElementVNode("button", {
                type: "button",
                class: "primary-btn",
                onClick: _cache[16] || (_cache[16] = ($event) => symbolModalOpen.value = false)
              }, " Done ")
            ])
          ])
        ])) : createCommentVNode("v-if", true)
      ]);
    };
  }
});
component.__scopeId = "data-v-0c063e59";
var CardDetail_default = component;
export {
  CardDetail_default as default
};
