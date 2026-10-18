<script setup>
import { computed, reactive, ref, watch } from "vue";
import { playerCountLabel } from "./options.mjs";
const props = defineProps({ games: Array, me: Object, busy: Boolean, playerCount: Number, platforms: Array });
const emit = defineEmits(["action", "info"]);
const search = ref(""), page = ref(1), selected = ref([]), editing = ref("");
const draft = reactive({ min_players: null, max_players: null, platform: "" });
const filtered = computed(() => props.games.filter(game => game.title.toLowerCase().includes(search.value.toLowerCase())));
const visible = computed(() => filtered.value.slice((page.value - 1) * 8, page.value * 8));
const approvable = computed(() => visible.value.filter(game => game.requires_player_limits));
watch(search, () => { page.value = 1; });
watch(() => props.games, () => {
  page.value = Math.min(page.value, Math.max(1, Math.ceil(filtered.value.length / 8)));
  selected.value = selected.value.filter(key => props.games.some(game => game.key === key && game.requires_player_limits));
});
function edit(game) {
  editing.value = game.key;
  draft.min_players = game.player_limits?.min_players ?? null;
  draft.max_players = game.player_limits?.max_players ?? null;
  draft.platform = "";
}
function save(game) {
  const platform = game.missing_platforms.includes(props.me.id) ? { platform: draft.platform } : {};
  if (Number.isInteger(draft.min_players) || Number.isInteger(draft.max_players)) {
    emit("action", { operation: "player-limits", key: game.key, min_players: Number.isInteger(draft.min_players) ? draft.min_players : null, max_players: Number.isInteger(draft.max_players) ? draft.max_players : null, ...platform });
  } else emit("action", { operation: "approve-group", keys: [game.key], ...platform });
}
function selectVisible(checked) {
  selected.value = checked ? [...new Set([...selected.value, ...approvable.value.map(game => game.key)])] : selected.value.filter(key => !approvable.value.some(game => game.key === key));
}
</script>
<template>
  <details class="panel exclusions" v-if="games.length">
    <summary>Needs attention · {{ games.length }} games</summary>
    <p class="fine">One person can confirm known counts for everyone, or approve a game for this {{ playerCount }}-player group without extra details. Group approval needs renewing if the player count changes. Ownership, platforms and personal rules still apply.</p>
    <input v-model="search" type="search" aria-label="Search games needing attention" placeholder="Find a game…" />
    <div v-if="approvable.length || selected.length" class="approval-bar">
      <label class="check"><input type="checkbox" :checked="approvable.length > 0 && approvable.every(game => selected.includes(game.key))" @change="selectVisible($event.target.checked)" /> Select this page</label>
      <button class="secondary" :disabled="busy || !selected.length" @click="emit('action', {operation:'approve-group', keys:[...selected]})">Approve {{ selected.length || 'selected' }} for {{ playerCount }} players</button>
    </div>
    <article v-for="game in visible" :key="game.key" :aria-label="game.title + ' exclusion'">
      <div class="attention-title"><input v-if="game.requires_player_limits" v-model="selected" :value="game.key" type="checkbox" :aria-label="'Select ' + game.title + ' for group approval'" /><button class="game-title" @click="emit('info',game)">{{ game.title }}</button></div>
      <ul><li v-for="reason in game.excluded_reasons" :key="reason">{{ reason }}</li></ul>
      <div class="card-actions">
        <button v-if="game.requires_player_limits" class="secondary" :disabled="busy" @click="emit('action',{operation:'approve-group',keys:[game.key]})">Approve for {{ playerCount }} players</button>
        <button v-if="(game.needs_player_limits || game.missing_platforms.includes(me.id)) && editing !== game.key" class="quiet" :disabled="busy" @click="edit(game)">{{ game.missing_platforms.includes(me.id) ? 'Set my platform / details' : 'Set known player limits' }}</button>
        <button v-if="me.vetoes.includes(game.key)" class="quiet" :disabled="busy" @click="emit('action',{operation:'clear-veto',key:game.key})">Undo veto</button>
      </div>
      <form v-if="editing === game.key" @submit.prevent="save(game)">
        <label v-if="game.missing_platforms.includes(me.id)">Your platform<select v-model="draft.platform" required><option value="" disabled>Choose your platform</option><option v-for="platform in platforms" :key="platform">{{ platform }}</option></select><small>Only your own room entry changes.</small></label>
        <p v-if="game.player_limits" class="fine">{{ playerCountLabel(game.player_limits) }} already confirmed for the room.</p>
        <template v-if="game.needs_player_limits"><div class="limit-presets"><button v-for="range in [[1,2],[1,4],[2,8]]" :key="range.join('-')" type="button" class="pill" @click="draft.min_players=range[0]; draft.max_players=range[1]">{{ range[0] }}–{{ range[1] }}</button></div><div class="fields"><label>Minimum players <small>Optional</small><input v-model.number="draft.min_players" type="number" min="1" max="32" placeholder="Unknown" /></label><label>Maximum players <small>Optional</small><input v-model.number="draft.max_players" type="number" :min="draft.min_players || 1" max="32" placeholder="Unknown" /></label></div></template>
        <p class="fine">Leave either limit blank if unknown. Saving keeps any known limit and approves this {{ playerCount }}-player group only; approve again if its size changes. Confirm both limits to cover future group sizes.</p>
        <button class="primary" :disabled="busy">Save details</button> <button type="button" class="quiet" @click="editing=''">Cancel</button>
      </form>
    </article>
    <p v-if="!filtered.length" class="fine">No games match your search.</p>
    <div v-if="filtered.length > 8" class="pagination"><button class="quiet" :disabled="page===1" @click="page--">Previous</button><span>{{ page }} / {{ Math.ceil(filtered.length/8) }}</span><button class="quiet" :disabled="page*8>=filtered.length" @click="page++">Next</button></div>
  </details>
</template>
<style>
.approval-bar,.attention-title,.limit-presets{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.approval-bar{justify-content:space-between;margin:12px 0}.attention-title>input{width:18px;height:18px;accent-color:var(--accent)}.attention-title .game-title{font-weight:600}.limit-presets{margin-top:12px}.approval-bar .check{margin:0}.attention-title .game-title{overflow-wrap:anywhere}
</style>
