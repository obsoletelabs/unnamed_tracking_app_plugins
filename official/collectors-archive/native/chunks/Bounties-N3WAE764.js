import {
  abandonBounty,
  completeBounty,
  createBounty,
  createEvidence,
  createJournalEntry,
  createObjective,
  deleteBounty,
  deleteEvidence,
  deleteJournalEntry,
  deleteObjective,
  fetchBounties,
  fetchPointsHistory,
  fetchPointsTotal,
  fetchRandomBountyProposal,
  pauseBounty,
  resumeBounty,
  updateBounty,
  updateObjective
} from "./chunk-NF76CKRV.js";
import {
  fetchGameAchievements,
  fetchGames
} from "./chunk-JQELIRZM.js";
import {
  RouterLink,
  useRoute
} from "./chunk-PPCLUKKJ.js";
import {
  AccountChip,
  Fragment,
  PageHeader,
  UiModal,
  archiveAction,
  computed,
  createBlock,
  createCommentVNode,
  createElementBlock,
  createElementVNode,
  createTextVNode,
  createVNode,
  defineComponent,
  normalizeClass,
  normalizeStyle,
  onBeforeUnmount,
  onMounted,
  openBlock,
  ref,
  renderList,
  toDisplayString,
  unref,
  vModelSelect,
  vModelText,
  watch,
  withCtx,
  withDirectives
} from "./chunk-2UKGPRFR.js";

// official/collectors-archive/ui/services/media.ts
async function listGameScreenshots(gameId) {
  const media = [];
  let offset = 0;
  while (true) {
    const result = await archiveAction({ game_id: gameId, offset }, "game-media");
    media.push(...result.media);
    if (result.complete) return media.filter((item) => item.kind === "screenshot");
    offset = Number(result.next_offset);
  }
}

// official/collectors-archive/ui/views/Bounties.vue
var _hoisted_1 = { class: "bounties-page" };
var _hoisted_2 = ["title"];
var _hoisted_3 = ["aria-pressed"];
var _hoisted_4 = {
  key: 0,
  class: "ui-alert",
  role: "alert"
};
var _hoisted_5 = ["disabled"];
var _hoisted_6 = {
  key: 1,
  class: "points-panel"
};
var _hoisted_7 = { class: "points-total" };
var _hoisted_8 = {
  key: 0,
  class: "empty-state"
};
var _hoisted_9 = {
  key: 1,
  class: "points-list"
};
var _hoisted_10 = { class: "points-amount" };
var _hoisted_11 = { class: "points-reason" };
var _hoisted_12 = { class: "points-date" };
var _hoisted_13 = {
  key: 2,
  class: "random-bounty-card"
};
var _hoisted_14 = { class: "random-bounty-main" };
var _hoisted_15 = { class: "random-bounty-body" };
var _hoisted_16 = { class: "random-bounty-title" };
var _hoisted_17 = { class: "random-bounty-sub" };
var _hoisted_18 = { class: "random-bounty-actions" };
var _hoisted_19 = ["disabled"];
var _hoisted_20 = ["disabled"];
var _hoisted_21 = {
  key: 0,
  class: "random-bounty-alts"
};
var _hoisted_22 = ["disabled", "onClick"];
var _hoisted_23 = { class: "random-bounty-alt-pts" };
var _hoisted_24 = { class: "filter-row" };
var _hoisted_25 = ["value"];
var _hoisted_26 = ["value"];
var _hoisted_27 = ["value"];
var _hoisted_28 = { class: "status-tabs" };
var _hoisted_29 = ["aria-pressed", "onClick"];
var _hoisted_30 = {
  key: 3,
  class: "empty-state"
};
var _hoisted_31 = {
  key: 4,
  class: "empty-state"
};
var _hoisted_32 = {
  key: 5,
  class: "bounty-list"
};
var _hoisted_33 = { class: "bounty-main" };
var _hoisted_34 = { class: "bounty-meta-row" };
var _hoisted_35 = { class: "bounty-type-pill" };
var _hoisted_36 = {
  key: 2,
  class: "bounty-auto-pill",
  title: "Proposed automatically"
};
var _hoisted_37 = { class: "bounty-title" };
var _hoisted_38 = {
  key: 0,
  class: "bounty-description"
};
var _hoisted_39 = {
  key: 1,
  class: "bounty-target-note"
};
var _hoisted_40 = {
  key: 2,
  class: "bounty-target-note"
};
var _hoisted_41 = {
  key: 3,
  class: "bounty-target-note"
};
var _hoisted_42 = { class: "progress-row" };
var _hoisted_43 = { class: "progress-track" };
var _hoisted_44 = { class: "progress-label" };
var _hoisted_45 = {
  key: 4,
  class: "manual-progress"
};
var _hoisted_46 = ["disabled", "onClick"];
var _hoisted_47 = ["onClick"];
var _hoisted_48 = { class: "bounty-footer-row" };
var _hoisted_49 = {
  key: 0,
  class: "bounty-points"
};
var _hoisted_50 = {
  key: 1,
  class: "bounty-deadline"
};
var _hoisted_51 = { class: "bounty-date" };
var _hoisted_52 = ["onClick"];
var _hoisted_53 = { class: "bounty-actions" };
var _hoisted_54 = ["disabled", "onClick"];
var _hoisted_55 = ["disabled", "onClick"];
var _hoisted_56 = ["disabled", "onClick"];
var _hoisted_57 = ["disabled", "onClick"];
var _hoisted_58 = ["disabled", "onClick"];
var _hoisted_59 = ["onClick"];
var _hoisted_60 = ["disabled", "onClick"];
var _hoisted_61 = {
  key: 0,
  class: "bounty-details"
};
var _hoisted_62 = { class: "details-section" };
var _hoisted_63 = { class: "details-header" };
var _hoisted_64 = ["onClick"];
var _hoisted_65 = {
  key: 0,
  class: "empty-state small"
};
var _hoisted_66 = {
  key: 1,
  class: "objective-list"
};
var _hoisted_67 = ["checked", "disabled", "onChange"];
var _hoisted_68 = {
  key: 2,
  class: "objective-progress"
};
var _hoisted_69 = {
  key: 3,
  class: "objective-progress"
};
var _hoisted_70 = ["disabled", "onClick"];
var _hoisted_71 = {
  key: 2,
  class: "inline-form"
};
var _hoisted_72 = ["value"];
var _hoisted_73 = ["disabled"];
var _hoisted_74 = ["value"];
var _hoisted_75 = {
  key: 2,
  class: "form-error small"
};
var _hoisted_76 = { class: "inline-form-actions" };
var _hoisted_77 = ["disabled", "onClick"];
var _hoisted_78 = { class: "details-section" };
var _hoisted_79 = { class: "details-header" };
var _hoisted_80 = ["onClick"];
var _hoisted_81 = {
  key: 0,
  class: "empty-state small"
};
var _hoisted_82 = {
  key: 1,
  class: "evidence-list"
};
var _hoisted_83 = { class: "evidence-kind" };
var _hoisted_84 = ["href"];
var _hoisted_85 = ["href"];
var _hoisted_86 = {
  key: 2,
  class: "evidence-text"
};
var _hoisted_87 = ["disabled", "onClick"];
var _hoisted_88 = {
  key: 2,
  class: "inline-form"
};
var _hoisted_89 = ["value"];
var _hoisted_90 = ["disabled"];
var _hoisted_91 = { value: "" };
var _hoisted_92 = ["value"];
var _hoisted_93 = {
  key: 3,
  class: "form-error small"
};
var _hoisted_94 = { class: "inline-form-actions" };
var _hoisted_95 = ["disabled", "onClick"];
var _hoisted_96 = { class: "details-section" };
var _hoisted_97 = {
  key: 0,
  class: "empty-state small"
};
var _hoisted_98 = {
  key: 1,
  class: "journal-list"
};
var _hoisted_99 = { class: "journal-date" };
var _hoisted_100 = { class: "journal-text" };
var _hoisted_101 = ["disabled", "onClick"];
var _hoisted_102 = {
  key: 2,
  class: "inline-form"
};
var _hoisted_103 = ["onUpdate:modelValue"];
var _hoisted_104 = { class: "inline-form-actions" };
var _hoisted_105 = ["disabled", "onClick"];
var _hoisted_106 = { class: "add-form" };
var _hoisted_107 = { class: "field-label" };
var _hoisted_108 = { class: "field-label" };
var _hoisted_109 = ["value"];
var _hoisted_110 = {
  key: 0,
  class: "field-label"
};
var _hoisted_111 = ["value"];
var _hoisted_112 = {
  key: 1,
  class: "field-label"
};
var _hoisted_113 = ["disabled"];
var _hoisted_114 = { value: "" };
var _hoisted_115 = ["value"];
var _hoisted_116 = {
  key: 2,
  class: "field-label"
};
var _hoisted_117 = { id: "collection-names" };
var _hoisted_118 = ["value"];
var _hoisted_119 = {
  key: 3,
  class: "field-label"
};
var _hoisted_120 = { class: "field-label" };
var _hoisted_121 = ["value"];
var _hoisted_122 = { class: "field-label" };
var _hoisted_123 = { class: "field-hint" };
var _hoisted_124 = ["onClick"];
var _hoisted_125 = { class: "field-label" };
var _hoisted_126 = { class: "field-label" };
var _hoisted_127 = {
  key: 4,
  class: "form-error"
};
var _hoisted_128 = { class: "dialog-actions" };
var _hoisted_129 = ["disabled"];
var component = /* @__PURE__ */ defineComponent({
  __name: "Bounties",
  setup(__props) {
    const TYPE_LABELS = {
      completion: "Completion",
      mastery: "Mastery",
      achievement: "Achievement",
      collection: "Collection",
      challenge: "Challenge",
      watch: "Watch",
      custom: "Custom"
    };
    const DIFFICULTY_LABELS = {
      easy: "Easy",
      normal: "Normal",
      hard: "Hard",
      extreme: "Extreme"
    };
    const AUTOMATIC_TYPES = [
      "completion",
      "mastery",
      "achievement",
      "collection"
    ];
    const SUGGESTED_POINTS = {
      easy: 50,
      normal: 100,
      hard: 200,
      extreme: 400
    };
    const OBJECTIVE_KIND_LABELS = {
      checkbox: "Checkbox",
      numeric: "Numeric",
      achievement: "Achievement"
    };
    const EVIDENCE_KIND_LABELS = {
      screenshot: "\u{1F4F8} Screenshot",
      clip: "\u{1F3AC} Clip",
      document: "\u{1F4C4} Document",
      note: "\u{1F4DD} Note",
      link: "\u{1F517} Link"
    };
    const bounties = ref([]);
    const games = ref([]);
    const loading = ref(true);
    const loadError = ref("");
    const actionPending = ref(null);
    const statusFilter = ref(
      "active"
    );
    const typeFilter = ref("");
    const difficultyFilter = ref("");
    const gameFilter = ref("");
    const searchQuery = ref("");
    const route = useRoute();
    async function loadAll() {
      loading.value = true;
      loadError.value = "";
      try {
        const [b, g] = await Promise.all([fetchBounties(), fetchGames()]);
        bounties.value = b;
        const requested = b.find((item) => item.id === route.query.record_id);
        if (requested) {
          searchQuery.value = requested.title;
          statusFilter.value = requested.status;
        }
        games.value = g.slice().sort((a, c) => a.title.localeCompare(c.title));
      } catch (reason) {
        loadError.value = reason instanceof Error ? reason.message : "Could not load your bounties.";
      } finally {
        loading.value = false;
      }
    }
    onMounted(loadAll);
    onMounted(loadRandomProposal);
    const filteredBounties = computed(
      () => bounties.value.filter((b) => {
        if (b.status !== statusFilter.value) return false;
        if (typeFilter.value && b.type !== typeFilter.value) return false;
        if (difficultyFilter.value && b.difficulty !== difficultyFilter.value)
          return false;
        if (gameFilter.value && b.game_id !== gameFilter.value) return false;
        if (searchQuery.value.trim() && !b.title.toLowerCase().includes(searchQuery.value.trim().toLowerCase()))
          return false;
        return true;
      })
    );
    const activeCount = computed(
      () => bounties.value.filter((b) => b.status === "active").length
    );
    const gamesWithBounties = computed(() => {
      const ids = new Set(
        bounties.value.map((b) => b.game_id).filter((id) => !!id)
      );
      return games.value.filter((g) => ids.has(g.id));
    });
    function progressPercent(b) {
      if (b.progress_mode === "binary") return b.progress_value >= 100 ? 100 : 0;
      if (!b.progress_target || b.progress_target <= 0) return 0;
      return Math.min(
        100,
        Math.round(b.progress_value / b.progress_target * 100)
      );
    }
    function progressLabel(b) {
      if (b.progress_mode === "binary")
        return b.status === "completed" ? "Complete" : "Not complete";
      if (b.progress_mode === "percentage")
        return `${Math.round(b.progress_value)}%`;
      return `${b.progress_value} / ${b.progress_target ?? "?"}`;
    }
    function formatDate(epochSeconds) {
      return new Date(epochSeconds * 1e3).toLocaleDateString(void 0, {
        month: "short",
        day: "numeric",
        year: "numeric"
      });
    }
    function deadlineLabel(b) {
      if (!b.target_date) return null;
      const daysLeft = Math.ceil((b.target_date - Date.now() / 1e3) / 86400);
      if (daysLeft < 0) return `Overdue, was due ${formatDate(b.target_date)}`;
      if (daysLeft === 0) return "Due today";
      return `${daysLeft} day${daysLeft === 1 ? "" : "s"} remaining`;
    }
    function weekStart(unixSeconds) {
      const d = new Date(unixSeconds * 1e3);
      const isoDay = (d.getDay() + 6) % 7;
      d.setHours(0, 0, 0, 0);
      d.setDate(d.getDate() - isoDay);
      return d.getTime();
    }
    const bountyStreakWeeks = computed(() => {
      const weeks = new Set(
        bounties.value.filter((b) => b.completed_at !== null).map((b) => weekStart(b.completed_at))
      );
      if (!weeks.size) return 0;
      const oneWeek = 7 * 864e5;
      let cursor = weekStart(Math.floor(Date.now() / 1e3));
      let streak = 0;
      while (weeks.has(cursor)) {
        streak++;
        cursor -= oneWeek;
      }
      return streak;
    });
    function shareBountyCard(b) {
      const canvas = document.createElement("canvas");
      canvas.width = 1e3;
      canvas.height = 560;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const bg = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
      bg.addColorStop(0, "#1a1408");
      bg.addColorStop(1, "#121212");
      ctx.fillStyle = bg;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.strokeStyle = "#d68a34";
      ctx.lineWidth = 3;
      ctx.strokeRect(24, 24, canvas.width - 48, canvas.height - 48);
      ctx.fillStyle = "#d68a34";
      ctx.font = "700 22px system-ui, sans-serif";
      ctx.fillText("BOUNTY COMPLETE", 64, 110);
      ctx.fillStyle = "#ffffff";
      ctx.font = "700 52px system-ui, sans-serif";
      wrapText(ctx, b.title, 64, 200, canvas.width - 128, 60);
      const metaY = 360;
      ctx.fillStyle = "#d68a34";
      ctx.font = "600 26px system-ui, sans-serif";
      const metaParts = [TYPE_LABELS[b.type]];
      if (b.difficulty) metaParts.push(DIFFICULTY_LABELS[b.difficulty]);
      if (b.game_title) metaParts.push(b.game_title);
      ctx.fillText(metaParts.join("   \xB7   "), 64, metaY);
      if (b.points_reward) {
        ctx.fillStyle = "#ffffff";
        ctx.font = "700 26px system-ui, sans-serif";
        ctx.fillText(`+${b.points_reward} pts`, 64, metaY + 50);
      }
      ctx.fillStyle = "#999999";
      ctx.font = "400 18px system-ui, sans-serif";
      const completedLabel = b.completed_at ? formatDate(b.completed_at) : formatDate(b.created_at);
      ctx.fillText(`Completed ${completedLabel}`, 64, canvas.height - 60);
      const link = document.createElement("a");
      link.download = `${b.title.replace(/[^a-z0-9]+/gi, "-").toLowerCase()}-bounty.png`;
      link.href = canvas.toDataURL("image/png");
      link.click();
    }
    function wrapText(ctx, text, x, y, maxWidth, lineHeight) {
      const words = text.split(" ");
      let line = "";
      let curY = y;
      for (const word of words) {
        const test = line ? `${line} ${word}` : word;
        if (ctx.measureText(test).width > maxWidth && line) {
          ctx.fillText(line, x, curY);
          line = word;
          curY += lineHeight;
        } else {
          line = test;
        }
      }
      ctx.fillText(line, x, curY);
    }
    const randomProposal = ref(null);
    const randomLoading = ref(false);
    const randomAccepting = ref(false);
    function proposalKey(p) {
      return `${p.type}:${p.game_id}:${p.title}`;
    }
    const suggestionAlternatives = ref([]);
    let suggestionsLive = true;
    let suggestionGeneration = 0;
    onBeforeUnmount(() => {
      suggestionsLive = false;
      suggestionGeneration++;
    });
    async function loadSuggestionAlternatives(generation) {
      const seen = new Set(
        randomProposal.value ? [proposalKey(randomProposal.value)] : []
      );
      const results = [];
      for (let i = 0; i < 5 && results.length < 2 && suggestionsLive && generation === suggestionGeneration; i++) {
        const p = await fetchRandomBountyProposal();
        if (!p) break;
        const key = proposalKey(p);
        if (!seen.has(key)) {
          seen.add(key);
          results.push(p);
        }
      }
      if (suggestionsLive && generation === suggestionGeneration) suggestionAlternatives.value = results;
    }
    async function loadRandomProposal() {
      const generation = ++suggestionGeneration;
      randomLoading.value = true;
      suggestionAlternatives.value = [];
      try {
        const proposal = await fetchRandomBountyProposal();
        if (!suggestionsLive || generation !== suggestionGeneration) return;
        randomProposal.value = proposal;
        if (proposal) await loadSuggestionAlternatives(generation);
      } catch {
        if (suggestionsLive && generation === suggestionGeneration) randomProposal.value = null;
      } finally {
        if (suggestionsLive && generation === suggestionGeneration) randomLoading.value = false;
      }
    }
    async function acceptAlternative(proposal) {
      randomAccepting.value = true;
      try {
        const created = await createBounty({
          title: proposal.title,
          type: proposal.type,
          game_id: proposal.game_id,
          points_reward: proposal.points_reward
        });
        bounties.value = [created, ...bounties.value];
        suggestionAlternatives.value = suggestionAlternatives.value.filter(
          (p) => proposalKey(p) !== proposalKey(proposal)
        );
        statusFilter.value = "active";
      } finally {
        randomAccepting.value = false;
      }
    }
    async function acceptRandomProposal() {
      if (!randomProposal.value) return;
      randomAccepting.value = true;
      try {
        const created = await createBounty({
          title: randomProposal.value.title,
          type: randomProposal.value.type,
          game_id: randomProposal.value.game_id,
          points_reward: randomProposal.value.points_reward
        });
        bounties.value = [created, ...bounties.value];
        randomProposal.value = null;
        statusFilter.value = "active";
        await loadRandomProposal();
      } finally {
        randomAccepting.value = false;
      }
    }
    const showAddForm = ref(false);
    const newType = ref("custom");
    const newTitle = ref("");
    const newDescription = ref("");
    const newDifficulty = ref("");
    const newGameId = ref("");
    const newAchievementId = ref("");
    const newCollectionName = ref("");
    const newProgressTarget = ref(null);
    const newPoints = ref(0);
    const newDeadline = ref("");
    const saving = ref(false);
    const formError = ref("");
    const gameAchievements = ref([]);
    const loadingAchievements = ref(false);
    watch([newType, newGameId], async ([type, gameId]) => {
      if (type !== "achievement" || !gameId) {
        gameAchievements.value = [];
        return;
      }
      loadingAchievements.value = true;
      try {
        gameAchievements.value = await fetchGameAchievements(gameId);
      } finally {
        loadingAchievements.value = false;
      }
    });
    const knownCollections = computed(() => {
      const names = /* @__PURE__ */ new Set();
      for (const g of games.value) {
        for (const c of g.collections ?? []) names.add(c);
      }
      return [...names].sort();
    });
    const needsGame = computed(
      () => ["completion", "mastery", "achievement"].includes(newType.value)
    );
    const isAutomatic = computed(() => AUTOMATIC_TYPES.includes(newType.value));
    function openAddForm() {
      newType.value = "custom";
      newTitle.value = "";
      newDescription.value = "";
      newDifficulty.value = "";
      newGameId.value = "";
      newAchievementId.value = "";
      newCollectionName.value = "";
      newProgressTarget.value = null;
      newPoints.value = 0;
      newDeadline.value = "";
      formError.value = "";
      showAddForm.value = true;
    }
    async function submitNewBounty() {
      if (!newTitle.value.trim()) {
        formError.value = "Give the goal a title.";
        return;
      }
      if (needsGame.value && !newGameId.value) {
        formError.value = "Pick a target game.";
        return;
      }
      if (newType.value === "achievement" && !newAchievementId.value) {
        formError.value = "Pick a target achievement.";
        return;
      }
      if (newType.value === "collection" && !newCollectionName.value.trim()) {
        formError.value = "Name the target collection.";
        return;
      }
      saving.value = true;
      formError.value = "";
      try {
        const created = await createBounty({
          title: newTitle.value.trim(),
          description: newDescription.value.trim() || null,
          type: newType.value,
          difficulty: newDifficulty.value || null,
          game_id: newType.value === "collection" ? null : newGameId.value || null,
          target_achievement_id: newType.value === "achievement" ? newAchievementId.value : null,
          target_collection_name: newType.value === "collection" ? newCollectionName.value.trim() : null,
          progress_mode: newType.value === "challenge" || newType.value === "watch" || newType.value === "custom" ? "numeric" : void 0,
          progress_target: !isAutomatic.value ? newProgressTarget.value : null,
          points_reward: newPoints.value,
          target_date: newDeadline.value ? Math.floor(new Date(newDeadline.value).getTime() / 1e3) : null
        });
        bounties.value = [created, ...bounties.value];
        showAddForm.value = false;
        statusFilter.value = created.status === "completed" ? "completed" : "active";
      } catch (err) {
        formError.value = err instanceof Error ? err.message : "Failed to create bounty.";
      } finally {
        saving.value = false;
      }
    }
    async function doAction(bounty, action) {
      actionPending.value = bounty.id;
      try {
        if (action === "complete") await completeBounty(bounty.id);
        else if (action === "pause") await pauseBounty(bounty.id);
        else if (action === "resume") await resumeBounty(bounty.id);
        else if (action === "abandon") await abandonBounty(bounty.id);
        else if (action === "delete") {
          await deleteBounty(bounty.id);
          bounties.value = bounties.value.filter((b) => b.id !== bounty.id);
          return;
        }
        bounties.value = await fetchBounties();
      } finally {
        actionPending.value = null;
      }
    }
    const editingProgressId = ref(null);
    const progressDraft = ref(0);
    function startEditProgress(b) {
      editingProgressId.value = b.id;
      progressDraft.value = b.progress_value;
    }
    async function saveProgress(b) {
      actionPending.value = b.id;
      try {
        const updated = await updateBounty(b.id, {
          progress_value: progressDraft.value
        });
        const idx = bounties.value.findIndex((x) => x.id === b.id);
        if (idx !== -1) bounties.value[idx] = updated;
        editingProgressId.value = null;
      } finally {
        actionPending.value = null;
      }
    }
    const expandedId = ref(null);
    function toggleExpand(b) {
      expandedId.value = expandedId.value === b.id ? null : b.id;
    }
    function replaceBounty(updated) {
      const idx = bounties.value.findIndex((x) => x.id === updated.id);
      if (idx !== -1) bounties.value[idx] = updated;
    }
    const showObjectiveForm = ref(null);
    const objTitle = ref("");
    const objKind = ref("checkbox");
    const objTarget = ref(null);
    const objAchievementId = ref("");
    const objAchievements = ref([]);
    const objSaving = ref(false);
    const objError = ref("");
    function openObjectiveForm(b) {
      showObjectiveForm.value = b.id;
      objTitle.value = "";
      objKind.value = "checkbox";
      objTarget.value = null;
      objAchievementId.value = "";
      objError.value = "";
      objAchievements.value = [];
      if (b.game_id)
        fetchGameAchievements(b.game_id).then((a) => objAchievements.value = a);
    }
    async function submitObjective(b) {
      if (!objTitle.value.trim()) {
        objError.value = "Give the objective a title.";
        return;
      }
      if (objKind.value === "achievement" && !objAchievementId.value) {
        objError.value = "Pick an achievement.";
        return;
      }
      objSaving.value = true;
      objError.value = "";
      try {
        const updated = await createObjective(b.id, {
          title: objTitle.value.trim(),
          kind: objKind.value,
          progress_target: objKind.value === "numeric" ? objTarget.value : null,
          target_achievement_id: objKind.value === "achievement" ? objAchievementId.value : null
        });
        replaceBounty(updated);
        showObjectiveForm.value = null;
      } catch (err) {
        objError.value = err instanceof Error ? err.message : "Failed to add objective.";
      } finally {
        objSaving.value = false;
      }
    }
    async function toggleObjectiveDone(b, objectiveId, done) {
      actionPending.value = objectiveId;
      try {
        const updated = await updateObjective(b.id, objectiveId, { done });
        replaceBounty(updated);
      } finally {
        actionPending.value = null;
      }
    }
    async function removeObjective(b, objectiveId) {
      actionPending.value = objectiveId;
      try {
        await deleteObjective(b.id, objectiveId);
        const updated = await fetchBounties();
        const fresh = updated.find((x) => x.id === b.id);
        if (fresh) replaceBounty(fresh);
      } finally {
        actionPending.value = null;
      }
    }
    const showEvidenceForm = ref(null);
    const evKind = ref("note");
    const evText = ref("");
    const evUrl = ref("");
    const evMediaId = ref("");
    const evMediaOptions = ref([]);
    const evSaving = ref(false);
    const evError = ref("");
    function openEvidenceForm(b) {
      showEvidenceForm.value = b.id;
      evKind.value = "note";
      evText.value = "";
      evUrl.value = "";
      evMediaId.value = "";
      evError.value = "";
      evMediaOptions.value = [];
      if (b.game_id)
        listGameScreenshots(b.game_id).then((m) => evMediaOptions.value = m);
    }
    async function submitEvidence(b) {
      if (evKind.value === "note" && !evText.value.trim()) {
        evError.value = "Write a note.";
        return;
      }
      if (evKind.value === "link" && !evUrl.value.trim()) {
        evError.value = "Enter a URL.";
        return;
      }
      if ((evKind.value === "screenshot" || evKind.value === "clip" || evKind.value === "document") && !evMediaId.value) {
        evError.value = "Pick a file from the game gallery.";
        return;
      }
      evSaving.value = true;
      evError.value = "";
      try {
        await createEvidence(b.id, {
          kind: evKind.value,
          text: evKind.value === "note" ? evText.value.trim() : null,
          url: evKind.value === "link" ? evUrl.value.trim() : null,
          media_item_id: ["screenshot", "clip", "document"].includes(evKind.value) ? evMediaId.value : null
        });
        const fresh = await fetchBounties();
        const updatedBounty = fresh.find((x) => x.id === b.id);
        if (updatedBounty) replaceBounty(updatedBounty);
        showEvidenceForm.value = null;
      } catch (err) {
        evError.value = err instanceof Error ? err.message : "Failed to add evidence.";
      } finally {
        evSaving.value = false;
      }
    }
    async function removeEvidence(b, evidenceId) {
      actionPending.value = evidenceId;
      try {
        await deleteEvidence(b.id, evidenceId);
        const fresh = await fetchBounties();
        const updatedBounty = fresh.find((x) => x.id === b.id);
        if (updatedBounty) replaceBounty(updatedBounty);
      } finally {
        actionPending.value = null;
      }
    }
    const journalDraft = ref({});
    async function addJournalEntry(b) {
      const text = (journalDraft.value[b.id] ?? "").trim();
      if (!text) return;
      actionPending.value = `journal-${b.id}`;
      try {
        await createJournalEntry(b.id, text);
        journalDraft.value[b.id] = "";
        const fresh = await fetchBounties();
        const updatedBounty = fresh.find((x) => x.id === b.id);
        if (updatedBounty) replaceBounty(updatedBounty);
      } finally {
        actionPending.value = null;
      }
    }
    async function removeJournalEntry(b, entryId) {
      actionPending.value = entryId;
      try {
        await deleteJournalEntry(b.id, entryId);
        const fresh = await fetchBounties();
        const updatedBounty = fresh.find((x) => x.id === b.id);
        if (updatedBounty) replaceBounty(updatedBounty);
      } finally {
        actionPending.value = null;
      }
    }
    const showPoints = ref(false);
    const pointsTotal = ref(0);
    const pointsHistory = ref([]);
    const pointsLoaded = ref(false);
    async function togglePoints() {
      showPoints.value = !showPoints.value;
      if (showPoints.value && !pointsLoaded.value) {
        const [total, history] = await Promise.all([
          fetchPointsTotal(),
          fetchPointsHistory()
        ]);
        pointsTotal.value = total;
        pointsHistory.value = history;
        pointsLoaded.value = true;
      }
    }
    return (_ctx, _cache) => {
      return openBlock(), createElementBlock("main", _hoisted_1, [
        createVNode(unref(AccountChip), { fixed: "" }),
        createVNode(unref(PageHeader), {
          title: "Bounties",
          description: "Personal goals and challenges. Points are there if you want them."
        }, {
          actions: withCtx(() => [
            bountyStreakWeeks.value > 0 ? (openBlock(), createElementBlock("span", {
              key: 0,
              class: "streak-pill",
              title: `${bountyStreakWeeks.value} consecutive week${bountyStreakWeeks.value === 1 ? "" : "s"} with a bounty completed`
            }, " \u{1F525} " + toDisplayString(bountyStreakWeeks.value) + " week" + toDisplayString(bountyStreakWeeks.value === 1 ? "" : "s"), 9, _hoisted_2)) : createCommentVNode("v-if", true),
            createElementVNode("button", {
              type: "button",
              class: "points-toggle",
              "aria-pressed": showPoints.value,
              onClick: togglePoints
            }, " \u{1F3C5} " + toDisplayString(showPoints.value ? "Hide" : "Points"), 9, _hoisted_3),
            createElementVNode("button", {
              type: "button",
              class: "add-button",
              "data-shortcut": "create",
              onClick: openAddForm
            }, " + New Bounty ")
          ]),
          _: 1
          /* STABLE */
        }),
        loadError.value ? (openBlock(), createElementBlock("div", _hoisted_4, [
          createTextVNode(
            toDisplayString(loadError.value) + " ",
            1
            /* TEXT */
          ),
          createElementVNode("button", {
            type: "button",
            class: "ui-btn ui-btn-ghost",
            disabled: loading.value,
            onClick: loadAll
          }, "Retry", 8, _hoisted_5)
        ])) : createCommentVNode("v-if", true),
        showPoints.value ? (openBlock(), createElementBlock("div", _hoisted_6, [
          createElementVNode("div", _hoisted_7, [
            _cache[28] || (_cache[28] = createTextVNode(
              " Total ",
              -1
              /* CACHED */
            )),
            createElementVNode(
              "strong",
              null,
              toDisplayString(pointsTotal.value),
              1
              /* TEXT */
            )
          ]),
          pointsHistory.value.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_8, " No points earned yet. ")) : (openBlock(), createElementBlock("div", _hoisted_9, [
            (openBlock(true), createElementBlock(
              Fragment,
              null,
              renderList(pointsHistory.value, (t) => {
                return openBlock(), createElementBlock("div", {
                  key: t.id,
                  class: "points-row"
                }, [
                  createElementVNode(
                    "span",
                    _hoisted_10,
                    "+" + toDisplayString(t.amount),
                    1
                    /* TEXT */
                  ),
                  createElementVNode(
                    "span",
                    _hoisted_11,
                    toDisplayString(t.reason),
                    1
                    /* TEXT */
                  ),
                  createElementVNode(
                    "span",
                    _hoisted_12,
                    toDisplayString(formatDate(t.created_at)),
                    1
                    /* TEXT */
                  )
                ]);
              }),
              128
              /* KEYED_FRAGMENT */
            ))
          ]))
        ])) : createCommentVNode("v-if", true),
        randomProposal.value ? (openBlock(), createElementBlock("div", _hoisted_13, [
          createElementVNode("div", _hoisted_14, [
            _cache[29] || (_cache[29] = createElementVNode(
              "div",
              { class: "random-bounty-label" },
              "\u{1F3B2} RANDOM BOUNTY",
              -1
              /* CACHED */
            )),
            createElementVNode("div", _hoisted_15, [
              createElementVNode(
                "span",
                _hoisted_16,
                toDisplayString(randomProposal.value.title),
                1
                /* TEXT */
              ),
              createElementVNode(
                "span",
                _hoisted_17,
                toDisplayString(TYPE_LABELS[randomProposal.value.type]) + " \xB7 " + toDisplayString(randomProposal.value.game_title) + " \xB7 +" + toDisplayString(randomProposal.value.points_reward) + " pts",
                1
                /* TEXT */
              )
            ]),
            createElementVNode("div", _hoisted_18, [
              createElementVNode("button", {
                type: "button",
                class: "save-btn",
                disabled: randomAccepting.value,
                onClick: acceptRandomProposal
              }, " Accept ", 8, _hoisted_19),
              createElementVNode("button", {
                type: "button",
                class: "cancel-btn",
                disabled: randomLoading.value,
                onClick: loadRandomProposal
              }, " Reroll ", 8, _hoisted_20)
            ])
          ]),
          suggestionAlternatives.value.length ? (openBlock(), createElementBlock("div", _hoisted_21, [
            _cache[30] || (_cache[30] = createElementVNode(
              "span",
              { class: "random-bounty-alts-label" },
              "Or:",
              -1
              /* CACHED */
            )),
            (openBlock(true), createElementBlock(
              Fragment,
              null,
              renderList(suggestionAlternatives.value, (alt) => {
                return openBlock(), createElementBlock("button", {
                  key: proposalKey(alt),
                  type: "button",
                  class: "random-bounty-alt",
                  disabled: randomAccepting.value,
                  onClick: ($event) => acceptAlternative(alt)
                }, [
                  createTextVNode(
                    toDisplayString(alt.title) + " ",
                    1
                    /* TEXT */
                  ),
                  createElementVNode(
                    "span",
                    _hoisted_23,
                    "+" + toDisplayString(alt.points_reward),
                    1
                    /* TEXT */
                  )
                ], 8, _hoisted_22);
              }),
              128
              /* KEYED_FRAGMENT */
            ))
          ])) : createCommentVNode("v-if", true)
        ])) : createCommentVNode("v-if", true),
        createElementVNode("div", _hoisted_24, [
          withDirectives(createElementVNode(
            "input",
            {
              "onUpdate:modelValue": _cache[0] || (_cache[0] = ($event) => searchQuery.value = $event),
              type: "text",
              class: "field-input search-input",
              placeholder: "Search bounties\u2026",
              "aria-label": "Search bounties",
              "data-shortcut": "search"
            },
            null,
            512
            /* NEED_PATCH */
          ), [
            [vModelText, searchQuery.value]
          ]),
          withDirectives(createElementVNode(
            "select",
            {
              "onUpdate:modelValue": _cache[1] || (_cache[1] = ($event) => typeFilter.value = $event),
              class: "field-input",
              "aria-label": "Filter by type"
            },
            [
              _cache[31] || (_cache[31] = createElementVNode(
                "option",
                { value: "" },
                "All types",
                -1
                /* CACHED */
              )),
              (openBlock(), createElementBlock(
                Fragment,
                null,
                renderList(TYPE_LABELS, (label, key) => {
                  return createElementVNode("option", {
                    key,
                    value: key
                  }, toDisplayString(label), 9, _hoisted_25);
                }),
                64
                /* STABLE_FRAGMENT */
              ))
            ],
            512
            /* NEED_PATCH */
          ), [
            [vModelSelect, typeFilter.value]
          ]),
          withDirectives(createElementVNode(
            "select",
            {
              "onUpdate:modelValue": _cache[2] || (_cache[2] = ($event) => difficultyFilter.value = $event),
              class: "field-input",
              "aria-label": "Filter by difficulty"
            },
            [
              _cache[32] || (_cache[32] = createElementVNode(
                "option",
                { value: "" },
                "All difficulties",
                -1
                /* CACHED */
              )),
              (openBlock(), createElementBlock(
                Fragment,
                null,
                renderList(DIFFICULTY_LABELS, (label, key) => {
                  return createElementVNode("option", {
                    key,
                    value: key
                  }, toDisplayString(label), 9, _hoisted_26);
                }),
                64
                /* STABLE_FRAGMENT */
              ))
            ],
            512
            /* NEED_PATCH */
          ), [
            [vModelSelect, difficultyFilter.value]
          ]),
          withDirectives(createElementVNode(
            "select",
            {
              "onUpdate:modelValue": _cache[3] || (_cache[3] = ($event) => gameFilter.value = $event),
              class: "field-input",
              "aria-label": "Filter by game"
            },
            [
              _cache[33] || (_cache[33] = createElementVNode(
                "option",
                { value: "" },
                "All games",
                -1
                /* CACHED */
              )),
              (openBlock(true), createElementBlock(
                Fragment,
                null,
                renderList(gamesWithBounties.value, (g) => {
                  return openBlock(), createElementBlock("option", {
                    key: g.id,
                    value: g.id
                  }, toDisplayString(g.title), 9, _hoisted_27);
                }),
                128
                /* KEYED_FRAGMENT */
              ))
            ],
            512
            /* NEED_PATCH */
          ), [
            [vModelSelect, gameFilter.value]
          ])
        ]),
        createElementVNode("div", _hoisted_28, [
          (openBlock(), createElementBlock(
            Fragment,
            null,
            renderList(["active", "completed", "paused", "abandoned"], (s) => {
              return createElementVNode("button", {
                key: s,
                type: "button",
                class: normalizeClass(["status-tab", { active: statusFilter.value === s }]),
                "aria-pressed": statusFilter.value === s,
                onClick: ($event) => statusFilter.value = s
              }, toDisplayString(s === "active" ? `Active (${activeCount.value})` : s.charAt(0).toUpperCase() + s.slice(1)), 11, _hoisted_29);
            }),
            64
            /* STABLE_FRAGMENT */
          ))
        ]),
        loading.value ? (openBlock(), createElementBlock("div", _hoisted_30, "Loading\u2026")) : filteredBounties.value.length === 0 ? (openBlock(), createElementBlock(
          "div",
          _hoisted_31,
          toDisplayString(statusFilter.value === "active" ? "No active bounties yet. Set a goal for one of your games." : `No ${statusFilter.value} bounties.`),
          1
          /* TEXT */
        )) : (openBlock(), createElementBlock("div", _hoisted_32, [
          (openBlock(true), createElementBlock(
            Fragment,
            null,
            renderList(filteredBounties.value, (b) => {
              return openBlock(), createElementBlock("div", {
                key: b.id,
                class: "bounty-card-wrapper"
              }, [
                createElementVNode(
                  "div",
                  {
                    class: normalizeClass(["bounty-card", { muted: b.status !== "active" }])
                  },
                  [
                    createElementVNode("div", _hoisted_33, [
                      createElementVNode("div", _hoisted_34, [
                        b.game_id ? (openBlock(), createBlock(unref(RouterLink), {
                          key: 0,
                          to: `/games/${b.game_id}`,
                          class: "bounty-game-link"
                        }, {
                          default: withCtx(() => [
                            createTextVNode(
                              toDisplayString(b.game_title),
                              1
                              /* TEXT */
                            )
                          ]),
                          _: 2
                          /* DYNAMIC */
                        }, 1032, ["to"])) : createCommentVNode("v-if", true),
                        createElementVNode(
                          "span",
                          _hoisted_35,
                          toDisplayString(TYPE_LABELS[b.type]),
                          1
                          /* TEXT */
                        ),
                        b.difficulty ? (openBlock(), createElementBlock(
                          "span",
                          {
                            key: 1,
                            class: normalizeClass(["bounty-difficulty-pill", b.difficulty])
                          },
                          toDisplayString(DIFFICULTY_LABELS[b.difficulty]),
                          3
                          /* TEXT, CLASS */
                        )) : createCommentVNode("v-if", true),
                        b.auto_generated ? (openBlock(), createElementBlock("span", _hoisted_36, "\u{1F916} Suggested")) : createCommentVNode("v-if", true)
                      ]),
                      createElementVNode(
                        "span",
                        _hoisted_37,
                        toDisplayString(b.title),
                        1
                        /* TEXT */
                      ),
                      b.description ? (openBlock(), createElementBlock(
                        "p",
                        _hoisted_38,
                        toDisplayString(b.description),
                        1
                        /* TEXT */
                      )) : createCommentVNode("v-if", true),
                      b.type === "achievement" && b.target_achievement_name ? (openBlock(), createElementBlock(
                        "p",
                        _hoisted_39,
                        " Achievement: " + toDisplayString(b.target_achievement_name),
                        1
                        /* TEXT */
                      )) : createCommentVNode("v-if", true),
                      b.type === "collection" && b.target_collection_name ? (openBlock(), createElementBlock(
                        "p",
                        _hoisted_40,
                        " Collection: " + toDisplayString(b.target_collection_name),
                        1
                        /* TEXT */
                      )) : createCommentVNode("v-if", true),
                      b.required_evidence_kinds.length ? (openBlock(), createElementBlock(
                        "p",
                        _hoisted_41,
                        " Suggested evidence: " + toDisplayString(b.required_evidence_kinds.map((k) => EVIDENCE_KIND_LABELS[k]).join(", ")),
                        1
                        /* TEXT */
                      )) : createCommentVNode("v-if", true),
                      createElementVNode("div", _hoisted_42, [
                        createElementVNode("div", _hoisted_43, [
                          createElementVNode(
                            "div",
                            {
                              class: "progress-fill",
                              style: normalizeStyle({ width: progressPercent(b) + "%" })
                            },
                            null,
                            4
                            /* STYLE */
                          )
                        ]),
                        createElementVNode(
                          "span",
                          _hoisted_44,
                          toDisplayString(progressLabel(b)),
                          1
                          /* TEXT */
                        )
                      ]),
                      b.status === "active" && b.objectives.length === 0 && !AUTOMATIC_TYPES.includes(b.type) ? (openBlock(), createElementBlock("div", _hoisted_45, [
                        editingProgressId.value === b.id ? (openBlock(), createElementBlock(
                          Fragment,
                          { key: 0 },
                          [
                            withDirectives(createElementVNode(
                              "input",
                              {
                                "onUpdate:modelValue": _cache[4] || (_cache[4] = ($event) => progressDraft.value = $event),
                                type: "number",
                                min: "0",
                                class: "progress-input"
                              },
                              null,
                              512
                              /* NEED_PATCH */
                            ), [
                              [
                                vModelText,
                                progressDraft.value,
                                void 0,
                                { number: true }
                              ]
                            ]),
                            createElementVNode("button", {
                              type: "button",
                              class: "mini-btn",
                              disabled: actionPending.value === b.id,
                              onClick: ($event) => saveProgress(b)
                            }, " Save ", 8, _hoisted_46),
                            createElementVNode("button", {
                              type: "button",
                              class: "mini-btn",
                              onClick: _cache[5] || (_cache[5] = ($event) => editingProgressId.value = null)
                            }, " Cancel ")
                          ],
                          64
                          /* STABLE_FRAGMENT */
                        )) : (openBlock(), createElementBlock("button", {
                          key: 1,
                          type: "button",
                          class: "mini-btn",
                          onClick: ($event) => startEditProgress(b)
                        }, " Update progress ", 8, _hoisted_47))
                      ])) : createCommentVNode("v-if", true),
                      createElementVNode("div", _hoisted_48, [
                        b.points_reward ? (openBlock(), createElementBlock(
                          "span",
                          _hoisted_49,
                          "+" + toDisplayString(b.points_reward) + " pts",
                          1
                          /* TEXT */
                        )) : createCommentVNode("v-if", true),
                        deadlineLabel(b) ? (openBlock(), createElementBlock(
                          "span",
                          _hoisted_50,
                          toDisplayString(deadlineLabel(b)),
                          1
                          /* TEXT */
                        )) : createCommentVNode("v-if", true),
                        createElementVNode(
                          "span",
                          _hoisted_51,
                          "Set " + toDisplayString(formatDate(b.created_at)),
                          1
                          /* TEXT */
                        ),
                        createElementVNode("button", {
                          type: "button",
                          class: "mini-btn",
                          onClick: ($event) => toggleExpand(b)
                        }, toDisplayString(expandedId.value === b.id ? "Hide" : "Objectives & Evidence") + " (" + toDisplayString(b.objectives.length + b.evidence.length) + ") ", 9, _hoisted_52)
                      ])
                    ]),
                    createElementVNode("div", _hoisted_53, [
                      b.status === "active" ? (openBlock(), createElementBlock(
                        Fragment,
                        { key: 0 },
                        [
                          createElementVNode("button", {
                            type: "button",
                            class: "action-btn complete",
                            disabled: actionPending.value === b.id,
                            title: "Mark complete",
                            "aria-label": "Mark bounty complete",
                            onClick: ($event) => doAction(b, "complete")
                          }, " \u2713 ", 8, _hoisted_54),
                          createElementVNode("button", {
                            type: "button",
                            class: "action-btn pause",
                            disabled: actionPending.value === b.id,
                            title: "Pause",
                            "aria-label": "Pause bounty",
                            onClick: ($event) => doAction(b, "pause")
                          }, " \u23F8 ", 8, _hoisted_55),
                          createElementVNode("button", {
                            type: "button",
                            class: "action-btn abandon",
                            disabled: actionPending.value === b.id,
                            title: "Abandon",
                            "aria-label": "Abandon bounty",
                            onClick: ($event) => doAction(b, "abandon")
                          }, " \u2715 ", 8, _hoisted_56)
                        ],
                        64
                        /* STABLE_FRAGMENT */
                      )) : b.status === "paused" ? (openBlock(), createElementBlock(
                        Fragment,
                        { key: 1 },
                        [
                          createElementVNode("button", {
                            type: "button",
                            class: "action-btn resume",
                            disabled: actionPending.value === b.id,
                            title: "Resume",
                            "aria-label": "Resume bounty",
                            onClick: ($event) => doAction(b, "resume")
                          }, " \u25B6 ", 8, _hoisted_57),
                          createElementVNode("button", {
                            type: "button",
                            class: "action-btn abandon",
                            disabled: actionPending.value === b.id,
                            title: "Abandon",
                            "aria-label": "Abandon bounty",
                            onClick: ($event) => doAction(b, "abandon")
                          }, " \u2715 ", 8, _hoisted_58)
                        ],
                        64
                        /* STABLE_FRAGMENT */
                      )) : createCommentVNode("v-if", true),
                      b.status === "completed" ? (openBlock(), createElementBlock("button", {
                        key: 2,
                        type: "button",
                        class: "action-btn share",
                        title: "Save a shareable image",
                        "aria-label": "Save a shareable bounty image",
                        onClick: ($event) => shareBountyCard(b)
                      }, " \u21E9 ", 8, _hoisted_59)) : createCommentVNode("v-if", true),
                      b.status !== "completed" ? (openBlock(), createElementBlock("button", {
                        key: 3,
                        type: "button",
                        class: "action-btn delete",
                        disabled: actionPending.value === b.id,
                        title: "Delete",
                        "aria-label": "Delete bounty",
                        onClick: ($event) => doAction(b, "delete")
                      }, " \u{1F5D1} ", 8, _hoisted_60)) : createCommentVNode("v-if", true)
                    ])
                  ],
                  2
                  /* CLASS */
                ),
                expandedId.value === b.id ? (openBlock(), createElementBlock("div", _hoisted_61, [
                  createElementVNode("div", _hoisted_62, [
                    createElementVNode("div", _hoisted_63, [
                      _cache[34] || (_cache[34] = createElementVNode(
                        "h4",
                        null,
                        "Objectives",
                        -1
                        /* CACHED */
                      )),
                      b.status === "active" ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        type: "button",
                        class: "mini-btn",
                        onClick: ($event) => openObjectiveForm(b)
                      }, " + Add ", 8, _hoisted_64)) : createCommentVNode("v-if", true)
                    ]),
                    b.objectives.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_65, " No objectives, this is a simple goal. ")) : (openBlock(), createElementBlock("div", _hoisted_66, [
                      (openBlock(true), createElementBlock(
                        Fragment,
                        null,
                        renderList(b.objectives, (o) => {
                          return openBlock(), createElementBlock("div", {
                            key: o.id,
                            class: "objective-row"
                          }, [
                            o.kind === "checkbox" ? (openBlock(), createElementBlock("input", {
                              key: 0,
                              type: "checkbox",
                              checked: o.done,
                              disabled: b.status !== "active" || actionPending.value === o.id,
                              onChange: ($event) => toggleObjectiveDone(
                                b,
                                o.id,
                                $event.target.checked
                              )
                            }, null, 40, _hoisted_67)) : (openBlock(), createElementBlock(
                              "span",
                              {
                                key: 1,
                                class: normalizeClass(["objective-status", { done: o.done }])
                              },
                              toDisplayString(o.done ? "\u2713" : "\u25CB"),
                              3
                              /* TEXT, CLASS */
                            )),
                            createElementVNode(
                              "span",
                              {
                                class: normalizeClass(["objective-title", { done: o.done }])
                              },
                              toDisplayString(o.title),
                              3
                              /* TEXT, CLASS */
                            ),
                            o.kind === "numeric" ? (openBlock(), createElementBlock(
                              "span",
                              _hoisted_68,
                              toDisplayString(o.progress_value) + " / " + toDisplayString(o.progress_target ?? "?"),
                              1
                              /* TEXT */
                            )) : createCommentVNode("v-if", true),
                            o.kind === "achievement" ? (openBlock(), createElementBlock("span", _hoisted_69, "achievement")) : createCommentVNode("v-if", true),
                            b.status === "active" ? (openBlock(), createElementBlock("button", {
                              key: 4,
                              type: "button",
                              class: "mini-btn danger",
                              disabled: actionPending.value === o.id,
                              onClick: ($event) => removeObjective(b, o.id)
                            }, " \u2715 ", 8, _hoisted_70)) : createCommentVNode("v-if", true)
                          ]);
                        }),
                        128
                        /* KEYED_FRAGMENT */
                      ))
                    ])),
                    showObjectiveForm.value === b.id ? (openBlock(), createElementBlock("div", _hoisted_71, [
                      withDirectives(createElementVNode(
                        "input",
                        {
                          "onUpdate:modelValue": _cache[6] || (_cache[6] = ($event) => objTitle.value = $event),
                          class: "field-input",
                          type: "text",
                          placeholder: "Earn 3 badges",
                          maxlength: "200"
                        },
                        null,
                        512
                        /* NEED_PATCH */
                      ), [
                        [vModelText, objTitle.value]
                      ]),
                      withDirectives(createElementVNode(
                        "select",
                        {
                          "onUpdate:modelValue": _cache[7] || (_cache[7] = ($event) => objKind.value = $event),
                          class: "field-input"
                        },
                        [
                          (openBlock(), createElementBlock(
                            Fragment,
                            null,
                            renderList(OBJECTIVE_KIND_LABELS, (label, key) => {
                              return createElementVNode("option", {
                                key,
                                value: key
                              }, toDisplayString(label), 9, _hoisted_72);
                            }),
                            64
                            /* STABLE_FRAGMENT */
                          ))
                        ],
                        512
                        /* NEED_PATCH */
                      ), [
                        [vModelSelect, objKind.value]
                      ]),
                      objKind.value === "numeric" ? withDirectives((openBlock(), createElementBlock(
                        "input",
                        {
                          key: 0,
                          "onUpdate:modelValue": _cache[8] || (_cache[8] = ($event) => objTarget.value = $event),
                          class: "field-input",
                          type: "number",
                          min: "1",
                          placeholder: "Target (e.g. 10)"
                        },
                        null,
                        512
                        /* NEED_PATCH */
                      )), [
                        [
                          vModelText,
                          objTarget.value,
                          void 0,
                          { number: true }
                        ]
                      ]) : createCommentVNode("v-if", true),
                      objKind.value === "achievement" ? withDirectives((openBlock(), createElementBlock("select", {
                        key: 1,
                        "onUpdate:modelValue": _cache[9] || (_cache[9] = ($event) => objAchievementId.value = $event),
                        class: "field-input",
                        disabled: !b.game_id
                      }, [
                        _cache[35] || (_cache[35] = createElementVNode(
                          "option",
                          { value: "" },
                          "Select an achievement\u2026",
                          -1
                          /* CACHED */
                        )),
                        (openBlock(true), createElementBlock(
                          Fragment,
                          null,
                          renderList(objAchievements.value, (a) => {
                            return openBlock(), createElementBlock("option", {
                              key: a.id,
                              value: a.id
                            }, toDisplayString(a.name), 9, _hoisted_74);
                          }),
                          128
                          /* KEYED_FRAGMENT */
                        ))
                      ], 8, _hoisted_73)), [
                        [vModelSelect, objAchievementId.value]
                      ]) : createCommentVNode("v-if", true),
                      objError.value ? (openBlock(), createElementBlock(
                        "p",
                        _hoisted_75,
                        toDisplayString(objError.value),
                        1
                        /* TEXT */
                      )) : createCommentVNode("v-if", true),
                      createElementVNode("div", _hoisted_76, [
                        createElementVNode("button", {
                          type: "button",
                          class: "mini-btn",
                          onClick: _cache[10] || (_cache[10] = ($event) => showObjectiveForm.value = null)
                        }, " Cancel "),
                        createElementVNode("button", {
                          type: "button",
                          class: "mini-btn primary",
                          disabled: objSaving.value,
                          onClick: ($event) => submitObjective(b)
                        }, toDisplayString(objSaving.value ? "Saving\u2026" : "Add"), 9, _hoisted_77)
                      ])
                    ])) : createCommentVNode("v-if", true)
                  ]),
                  createElementVNode("div", _hoisted_78, [
                    createElementVNode("div", _hoisted_79, [
                      _cache[36] || (_cache[36] = createElementVNode(
                        "h4",
                        null,
                        "Evidence",
                        -1
                        /* CACHED */
                      )),
                      b.status === "active" ? (openBlock(), createElementBlock("button", {
                        key: 0,
                        type: "button",
                        class: "mini-btn",
                        onClick: ($event) => openEvidenceForm(b)
                      }, " + Add ", 8, _hoisted_80)) : createCommentVNode("v-if", true)
                    ]),
                    b.evidence.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_81, " No evidence attached. ")) : (openBlock(), createElementBlock("div", _hoisted_82, [
                      (openBlock(true), createElementBlock(
                        Fragment,
                        null,
                        renderList(b.evidence, (e) => {
                          return openBlock(), createElementBlock("div", {
                            key: e.id,
                            class: "evidence-row"
                          }, [
                            createElementVNode(
                              "span",
                              _hoisted_83,
                              toDisplayString(EVIDENCE_KIND_LABELS[e.kind]),
                              1
                              /* TEXT */
                            ),
                            e.media_url ? (openBlock(), createElementBlock("a", {
                              key: 0,
                              href: e.media_url,
                              target: "_blank",
                              rel: "noopener",
                              class: "evidence-link"
                            }, toDisplayString(e.media_filename), 9, _hoisted_84)) : e.url ? (openBlock(), createElementBlock("a", {
                              key: 1,
                              href: e.url,
                              target: "_blank",
                              rel: "noopener",
                              class: "evidence-link"
                            }, toDisplayString(e.url), 9, _hoisted_85)) : e.text ? (openBlock(), createElementBlock(
                              "span",
                              _hoisted_86,
                              toDisplayString(e.text),
                              1
                              /* TEXT */
                            )) : createCommentVNode("v-if", true),
                            createElementVNode("button", {
                              type: "button",
                              class: "mini-btn danger",
                              disabled: actionPending.value === e.id,
                              onClick: ($event) => removeEvidence(b, e.id)
                            }, " \u2715 ", 8, _hoisted_87)
                          ]);
                        }),
                        128
                        /* KEYED_FRAGMENT */
                      ))
                    ])),
                    showEvidenceForm.value === b.id ? (openBlock(), createElementBlock("div", _hoisted_88, [
                      withDirectives(createElementVNode(
                        "select",
                        {
                          "onUpdate:modelValue": _cache[11] || (_cache[11] = ($event) => evKind.value = $event),
                          class: "field-input"
                        },
                        [
                          (openBlock(), createElementBlock(
                            Fragment,
                            null,
                            renderList(EVIDENCE_KIND_LABELS, (label, key) => {
                              return createElementVNode("option", {
                                key,
                                value: key
                              }, toDisplayString(label), 9, _hoisted_89);
                            }),
                            64
                            /* STABLE_FRAGMENT */
                          ))
                        ],
                        512
                        /* NEED_PATCH */
                      ), [
                        [vModelSelect, evKind.value]
                      ]),
                      evKind.value === "note" ? withDirectives((openBlock(), createElementBlock(
                        "textarea",
                        {
                          key: 0,
                          "onUpdate:modelValue": _cache[12] || (_cache[12] = ($event) => evText.value = $event),
                          class: "field-input",
                          rows: "2",
                          placeholder: "Write a note"
                        },
                        null,
                        512
                        /* NEED_PATCH */
                      )), [
                        [vModelText, evText.value]
                      ]) : createCommentVNode("v-if", true),
                      evKind.value === "link" ? withDirectives((openBlock(), createElementBlock(
                        "input",
                        {
                          key: 1,
                          "onUpdate:modelValue": _cache[13] || (_cache[13] = ($event) => evUrl.value = $event),
                          class: "field-input",
                          type: "text",
                          placeholder: "https://\u2026"
                        },
                        null,
                        512
                        /* NEED_PATCH */
                      )), [
                        [vModelText, evUrl.value]
                      ]) : createCommentVNode("v-if", true),
                      ["screenshot", "clip", "document"].includes(evKind.value) ? withDirectives((openBlock(), createElementBlock("select", {
                        key: 2,
                        "onUpdate:modelValue": _cache[14] || (_cache[14] = ($event) => evMediaId.value = $event),
                        class: "field-input",
                        disabled: !b.game_id || evMediaOptions.value.length === 0
                      }, [
                        createElementVNode(
                          "option",
                          _hoisted_91,
                          toDisplayString(evMediaOptions.value.length === 0 ? "No media in this game's gallery yet" : "Select a file\u2026"),
                          1
                          /* TEXT */
                        ),
                        (openBlock(true), createElementBlock(
                          Fragment,
                          null,
                          renderList(evMediaOptions.value, (m) => {
                            return openBlock(), createElementBlock("option", {
                              key: m.id,
                              value: m.id
                            }, toDisplayString(m.filename), 9, _hoisted_92);
                          }),
                          128
                          /* KEYED_FRAGMENT */
                        ))
                      ], 8, _hoisted_90)), [
                        [vModelSelect, evMediaId.value]
                      ]) : createCommentVNode("v-if", true),
                      evError.value ? (openBlock(), createElementBlock(
                        "p",
                        _hoisted_93,
                        toDisplayString(evError.value),
                        1
                        /* TEXT */
                      )) : createCommentVNode("v-if", true),
                      createElementVNode("div", _hoisted_94, [
                        createElementVNode("button", {
                          type: "button",
                          class: "mini-btn",
                          onClick: _cache[15] || (_cache[15] = ($event) => showEvidenceForm.value = null)
                        }, " Cancel "),
                        createElementVNode("button", {
                          type: "button",
                          class: "mini-btn primary",
                          disabled: evSaving.value,
                          onClick: ($event) => submitEvidence(b)
                        }, toDisplayString(evSaving.value ? "Saving\u2026" : "Add"), 9, _hoisted_95)
                      ])
                    ])) : createCommentVNode("v-if", true)
                  ]),
                  createElementVNode("div", _hoisted_96, [
                    _cache[37] || (_cache[37] = createElementVNode(
                      "div",
                      { class: "details-header" },
                      [
                        createElementVNode("h4", null, "Journal")
                      ],
                      -1
                      /* CACHED */
                    )),
                    b.journal.length === 0 ? (openBlock(), createElementBlock("div", _hoisted_97, " No journal entries yet. ")) : (openBlock(), createElementBlock("div", _hoisted_98, [
                      (openBlock(true), createElementBlock(
                        Fragment,
                        null,
                        renderList(b.journal, (j) => {
                          return openBlock(), createElementBlock("div", {
                            key: j.id,
                            class: "journal-entry"
                          }, [
                            createElementVNode(
                              "span",
                              _hoisted_99,
                              toDisplayString(formatDate(j.created_at)),
                              1
                              /* TEXT */
                            ),
                            createElementVNode(
                              "span",
                              _hoisted_100,
                              toDisplayString(j.text),
                              1
                              /* TEXT */
                            ),
                            createElementVNode("button", {
                              type: "button",
                              class: "mini-btn danger",
                              disabled: actionPending.value === j.id,
                              onClick: ($event) => removeJournalEntry(b, j.id)
                            }, " \u2715 ", 8, _hoisted_101)
                          ]);
                        }),
                        128
                        /* KEYED_FRAGMENT */
                      ))
                    ])),
                    b.status === "active" ? (openBlock(), createElementBlock("div", _hoisted_102, [
                      withDirectives(createElementVNode("textarea", {
                        "onUpdate:modelValue": ($event) => journalDraft.value[b.id] = $event,
                        class: "field-input",
                        rows: "2",
                        placeholder: "What happened today?"
                      }, null, 8, _hoisted_103), [
                        [vModelText, journalDraft.value[b.id]]
                      ]),
                      createElementVNode("div", _hoisted_104, [
                        createElementVNode("button", {
                          type: "button",
                          class: "mini-btn primary",
                          disabled: actionPending.value === `journal-${b.id}`,
                          onClick: ($event) => addJournalEntry(b)
                        }, " Add entry ", 8, _hoisted_105)
                      ])
                    ])) : createCommentVNode("v-if", true)
                  ])
                ])) : createCommentVNode("v-if", true)
              ]);
            }),
            128
            /* KEYED_FRAGMENT */
          ))
        ])),
        showAddForm.value ? (openBlock(), createBlock(unref(UiModal), {
          key: 6,
          title: "New bounty",
          dismissible: !saving.value,
          onClose: _cache[27] || (_cache[27] = ($event) => showAddForm.value = false)
        }, {
          default: withCtx(() => [
            createElementVNode("div", _hoisted_106, [
              createElementVNode("label", _hoisted_107, [
                _cache[38] || (_cache[38] = createTextVNode(
                  "Title ",
                  -1
                  /* CACHED */
                )),
                withDirectives(createElementVNode(
                  "input",
                  {
                    "onUpdate:modelValue": _cache[16] || (_cache[16] = ($event) => newTitle.value = $event),
                    class: "field-input",
                    type: "text",
                    placeholder: "Finish Elden Ring",
                    maxlength: "200"
                  },
                  null,
                  512
                  /* NEED_PATCH */
                ), [
                  [vModelText, newTitle.value]
                ])
              ]),
              createElementVNode("label", _hoisted_108, [
                _cache[39] || (_cache[39] = createTextVNode(
                  "Type ",
                  -1
                  /* CACHED */
                )),
                withDirectives(createElementVNode(
                  "select",
                  {
                    "onUpdate:modelValue": _cache[17] || (_cache[17] = ($event) => newType.value = $event),
                    class: "field-input",
                    "aria-label": "Bounty type"
                  },
                  [
                    (openBlock(), createElementBlock(
                      Fragment,
                      null,
                      renderList(TYPE_LABELS, (label, key) => {
                        return createElementVNode("option", {
                          key,
                          value: key
                        }, toDisplayString(label), 9, _hoisted_109);
                      }),
                      64
                      /* STABLE_FRAGMENT */
                    ))
                  ],
                  512
                  /* NEED_PATCH */
                ), [
                  [vModelSelect, newType.value]
                ])
              ]),
              needsGame.value || newType.value === "challenge" || newType.value === "watch" ? (openBlock(), createElementBlock("label", _hoisted_110, [
                createTextVNode(
                  " Target Game" + toDisplayString(needsGame.value ? "" : " (optional)") + " ",
                  1
                  /* TEXT */
                ),
                withDirectives(createElementVNode(
                  "select",
                  {
                    "onUpdate:modelValue": _cache[18] || (_cache[18] = ($event) => newGameId.value = $event),
                    class: "field-input"
                  },
                  [
                    _cache[40] || (_cache[40] = createElementVNode(
                      "option",
                      { value: "" },
                      "None",
                      -1
                      /* CACHED */
                    )),
                    (openBlock(true), createElementBlock(
                      Fragment,
                      null,
                      renderList(games.value, (g) => {
                        return openBlock(), createElementBlock("option", {
                          key: g.id,
                          value: g.id
                        }, toDisplayString(g.title), 9, _hoisted_111);
                      }),
                      128
                      /* KEYED_FRAGMENT */
                    ))
                  ],
                  512
                  /* NEED_PATCH */
                ), [
                  [vModelSelect, newGameId.value]
                ])
              ])) : createCommentVNode("v-if", true),
              newType.value === "achievement" ? (openBlock(), createElementBlock("label", _hoisted_112, [
                _cache[41] || (_cache[41] = createTextVNode(
                  "Target Achievement ",
                  -1
                  /* CACHED */
                )),
                withDirectives(createElementVNode("select", {
                  "onUpdate:modelValue": _cache[19] || (_cache[19] = ($event) => newAchievementId.value = $event),
                  class: "field-input",
                  disabled: loadingAchievements.value || gameAchievements.value.length === 0
                }, [
                  createElementVNode(
                    "option",
                    _hoisted_114,
                    toDisplayString(loadingAchievements.value ? "Loading\u2026" : "Select one\u2026"),
                    1
                    /* TEXT */
                  ),
                  (openBlock(true), createElementBlock(
                    Fragment,
                    null,
                    renderList(gameAchievements.value, (a) => {
                      return openBlock(), createElementBlock("option", {
                        key: a.id,
                        value: a.id
                      }, toDisplayString(a.name) + toDisplayString(a.unlockedAt ? " (already unlocked)" : ""), 9, _hoisted_115);
                    }),
                    128
                    /* KEYED_FRAGMENT */
                  ))
                ], 8, _hoisted_113), [
                  [vModelSelect, newAchievementId.value]
                ])
              ])) : createCommentVNode("v-if", true),
              newType.value === "collection" ? (openBlock(), createElementBlock("label", _hoisted_116, [
                _cache[42] || (_cache[42] = createTextVNode(
                  "Target Collection ",
                  -1
                  /* CACHED */
                )),
                withDirectives(createElementVNode(
                  "input",
                  {
                    "onUpdate:modelValue": _cache[20] || (_cache[20] = ($event) => newCollectionName.value = $event),
                    class: "field-input",
                    type: "text",
                    list: "collection-names",
                    placeholder: "Souls series"
                  },
                  null,
                  512
                  /* NEED_PATCH */
                ), [
                  [vModelText, newCollectionName.value]
                ]),
                createElementVNode("datalist", _hoisted_117, [
                  (openBlock(true), createElementBlock(
                    Fragment,
                    null,
                    renderList(knownCollections.value, (c) => {
                      return openBlock(), createElementBlock("option", {
                        key: c,
                        value: c
                      }, null, 8, _hoisted_118);
                    }),
                    128
                    /* KEYED_FRAGMENT */
                  ))
                ])
              ])) : createCommentVNode("v-if", true),
              !isAutomatic.value ? (openBlock(), createElementBlock("label", _hoisted_119, [
                _cache[43] || (_cache[43] = createTextVNode(
                  'Progress Target (optional, numeric goals like "10 games") ',
                  -1
                  /* CACHED */
                )),
                withDirectives(createElementVNode(
                  "input",
                  {
                    "onUpdate:modelValue": _cache[21] || (_cache[21] = ($event) => newProgressTarget.value = $event),
                    class: "field-input",
                    type: "number",
                    min: "1",
                    placeholder: "e.g. 10"
                  },
                  null,
                  512
                  /* NEED_PATCH */
                ), [
                  [
                    vModelText,
                    newProgressTarget.value,
                    void 0,
                    { number: true }
                  ]
                ])
              ])) : createCommentVNode("v-if", true),
              createElementVNode("label", _hoisted_120, [
                _cache[45] || (_cache[45] = createTextVNode(
                  "Difficulty (optional) ",
                  -1
                  /* CACHED */
                )),
                withDirectives(createElementVNode(
                  "select",
                  {
                    "onUpdate:modelValue": _cache[22] || (_cache[22] = ($event) => newDifficulty.value = $event),
                    class: "field-input"
                  },
                  [
                    _cache[44] || (_cache[44] = createElementVNode(
                      "option",
                      { value: "" },
                      "None",
                      -1
                      /* CACHED */
                    )),
                    (openBlock(), createElementBlock(
                      Fragment,
                      null,
                      renderList(DIFFICULTY_LABELS, (label, key) => {
                        return createElementVNode("option", {
                          key,
                          value: key
                        }, toDisplayString(label), 9, _hoisted_121);
                      }),
                      64
                      /* STABLE_FRAGMENT */
                    ))
                  ],
                  512
                  /* NEED_PATCH */
                ), [
                  [vModelSelect, newDifficulty.value]
                ])
              ]),
              createElementVNode("label", _hoisted_122, [
                _cache[47] || (_cache[47] = createTextVNode(
                  "Points Reward ",
                  -1
                  /* CACHED */
                )),
                withDirectives(createElementVNode(
                  "input",
                  {
                    "onUpdate:modelValue": _cache[23] || (_cache[23] = ($event) => newPoints.value = $event),
                    class: "field-input",
                    type: "number",
                    min: "0"
                  },
                  null,
                  512
                  /* NEED_PATCH */
                ), [
                  [
                    vModelText,
                    newPoints.value,
                    void 0,
                    { number: true }
                  ]
                ]),
                createElementVNode("span", _hoisted_123, [
                  _cache[46] || (_cache[46] = createTextVNode(
                    " Points are entirely up to you, a rough scale to stay consistent: ",
                    -1
                    /* CACHED */
                  )),
                  (openBlock(), createElementBlock(
                    Fragment,
                    null,
                    renderList(SUGGESTED_POINTS, (pts, key) => {
                      return createElementVNode("button", {
                        key,
                        type: "button",
                        class: "points-suggestion",
                        onClick: ($event) => newPoints.value = pts
                      }, toDisplayString(DIFFICULTY_LABELS[key]) + " " + toDisplayString(pts), 9, _hoisted_124);
                    }),
                    64
                    /* STABLE_FRAGMENT */
                  ))
                ])
              ]),
              createElementVNode("label", _hoisted_125, [
                _cache[48] || (_cache[48] = createTextVNode(
                  "Deadline (optional) ",
                  -1
                  /* CACHED */
                )),
                withDirectives(createElementVNode(
                  "input",
                  {
                    "onUpdate:modelValue": _cache[24] || (_cache[24] = ($event) => newDeadline.value = $event),
                    class: "field-input",
                    type: "date"
                  },
                  null,
                  512
                  /* NEED_PATCH */
                ), [
                  [vModelText, newDeadline.value]
                ])
              ]),
              createElementVNode("label", _hoisted_126, [
                _cache[49] || (_cache[49] = createTextVNode(
                  "Description (optional) ",
                  -1
                  /* CACHED */
                )),
                withDirectives(createElementVNode(
                  "textarea",
                  {
                    "onUpdate:modelValue": _cache[25] || (_cache[25] = ($event) => newDescription.value = $event),
                    class: "field-input",
                    rows: "2",
                    placeholder: "Any extra detail"
                  },
                  null,
                  512
                  /* NEED_PATCH */
                ), [
                  [vModelText, newDescription.value]
                ])
              ]),
              formError.value ? (openBlock(), createElementBlock(
                "p",
                _hoisted_127,
                toDisplayString(formError.value),
                1
                /* TEXT */
              )) : createCommentVNode("v-if", true),
              createElementVNode("div", _hoisted_128, [
                createElementVNode("button", {
                  type: "button",
                  class: "cancel-btn",
                  onClick: _cache[26] || (_cache[26] = ($event) => showAddForm.value = false)
                }, " Cancel "),
                createElementVNode("button", {
                  type: "button",
                  class: "save-btn",
                  disabled: saving.value,
                  onClick: submitNewBounty
                }, toDisplayString(saving.value ? "Saving\u2026" : "Create"), 9, _hoisted_129)
              ])
            ])
          ]),
          _: 1
          /* STABLE */
        }, 8, ["dismissible"])) : createCommentVNode("v-if", true)
      ]);
    };
  }
});
component.__scopeId = "data-v-555f512a";
var Bounties_default = component;
export {
  Bounties_default as default
};
