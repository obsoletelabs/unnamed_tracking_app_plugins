<script setup>
import { ref, computed, watch } from "vue";
import { gamePlatform } from "./options.mjs";
import { canSaveCompatibility, saveCompatibilityTargets, summarizeSaveResults } from "./library.mjs";
const props = defineProps({ games: Array, library: Array, sources: Array, busy: Boolean, inferSteam: Boolean, save: Function });
const emit = defineEmits(["annotate"]);
const summary = computed(() => summarizeSaveResults(results.value)), selected = ref([]), editing = ref(false), saving = ref(false), results = ref([]);
const known = ref(false), minimum = ref(1), maximum = ref(4), crossplay = ref(false), clear = ref(false), confirmed = ref(false);
const id = game => game.source_id + ":" + game.id;
const targets = computed(() => (props.library || []).filter(game => selected.value.includes(id(game))).map(game => ({ ...game, source: props.sources.find(source => source.id === game.source_id) })));
const writable = computed(() => targets.value.length > 0 && targets.value.every(game => canSaveCompatibility(game.source)));
watch(() => props.library, () => {
  const remaining = selected.value.filter(value => props.library.some(game => id(game) === value));
  if (remaining.length !== selected.value.length) selected.value = remaining;
});
watch([selected, known, minimum, maximum, crossplay, clear], () => { confirmed.value = false; });
function selectPage() { selected.value = [...new Set([...selected.value, ...props.games.map(id)])].slice(0, 100); }
async function submit() {
  saving.value = true; results.value = [];
  const preset = clear.value ? null : { min_players: known.value ? Number(minimum.value) : null, max_players: known.value ? Number(maximum.value) : null, duration_minutes: null, crossplay: crossplay.value };
  results.value = await saveCompatibilityTargets(targets.value, preset, props.save);
  confirmed.value = false; saving.value = false;
}
</script>
<template>
  <div class="library-settings">
    <div class="library-tools"><button class="quiet" :disabled="busy || saving" @click="selectPage">Select this page</button><button class="quiet" :disabled="!selected.length || saving" @click="selected = []">Clear selection</button><span>{{ selected.length }} / 100 selected</span><button v-if="selected.length" class="secondary" :disabled="saving || busy" @click="editing = !editing">Edit selected multiplayer settings</button></div>
    <form v-if="editing && selected.length" class="bulk-preset" @submit.prevent="submit">
      <h3>Save to {{ targets.length }} game records</h3><p>Replaces multiplayer settings in your selected tracking instances. Other fields are unchanged. For room-only approval, use Game night.</p>
      <p v-if="!writable" role="status">Every selected connection needs scoped “Multiplayer settings” access. Reconnect with that option checked and approve it on the source instance. Legacy keys support reads only.</p>
      <label class="check"><input type="checkbox" v-model="clear" :disabled="saving" /> Clear saved multiplayer settings</label>
      <template v-if="!clear"><p class="fine">Without extra details, marks these games playable with others and leaves exact limits unknown.</p><label class="check"><input type="checkbox" v-model="known" :disabled="saving" /> Set known player limits</label>
      <template v-if="known"><div class="library-tools"><button v-for="pair in [[1,2],[1,4],[2,8]]" :key="pair.join('-')" type="button" class="secondary" :disabled="saving" @click="minimum = pair[0]; maximum = pair[1]">{{ pair[0] }}–{{ pair[1] }}</button></div><div class="fields"><label>Minimum players<input v-model="minimum" type="number" min="1" max="32" required :disabled="saving" /></label><label>Maximum players<input v-model="maximum" type="number" :min="minimum || 1" max="32" required :disabled="saving" /></label></div></template>
      <label class="check"><input type="checkbox" v-model="crossplay" :disabled="saving" /> Cross-platform play confirmed</label></template>
      <details><summary>Review selected games and instances</summary><ul><li v-for="game in targets" :key="id(game)">{{ game.title }} · {{ game.source?.origin }} · {{ game.play_compatibility ? (game.play_compatibility.source === 'provider' ? 'Replaces provider-supplied details' : 'Replaces saved details') : 'No saved details' }}</li></ul></details>
      <label class="check"><input type="checkbox" v-model="confirmed" required :disabled="saving || !writable" /> Apply these settings to my {{ targets.length }} selected game records</label>
      <button type="submit" class="primary" :disabled="saving || busy || !writable || !confirmed">{{ saving ? 'Saving to your instances…' : 'Save selected settings' }}</button>
    </form>
    <ul v-if="summary.length" class="save-results" aria-live="polite"><li v-for="entry in summary" :key="entry.origin"><strong>{{ entry.origin }}</strong> · {{ entry.saved }} saved · {{ entry.failed.length ? entry.failed.length + ' failed' : 'none failed' }}</li></ul><ul v-if="results.length" class="save-results"><li v-for="result in results" :key="result.source_id + result.id">{{ result.title }} · {{ result.origin }} · {{ result.error || 'Saved' }}</li></ul><p v-if="results.length" class="fine">Each game saves separately. Successful saves remain applied if another instance fails. Review failures before trying again; refresh your connections to use saved details.</p>
    <div class="library-selection" v-for="game in games" :key="id(game)">
      <label class="check"><input type="checkbox" v-model="selected" :value="id(game)" :disabled="saving || (!selected.includes(id(game)) && selected.length >= 100)" :aria-label="'Select ' + game.title" /></label>
      <button class="quiet library-game" :disabled="saving" @click="emit('annotate', game)"><strong>{{ game.title }}</strong><span>{{ game.platform || (gamePlatform(game, inferSteam) ? 'PC · Inferred from Steam' : 'Platform unknown') }} · {{ game.owned ? 'Owned' : 'Wishlist' }} · {{ game.play_compatibility?.min_players != null ? game.play_compatibility.min_players + '–' + game.play_compatibility.max_players + ' players' : 'Player limits unknown' }}</span><small>{{ sources.find(source => source.id === game.source_id)?.origin }}<template v-if="game.play_compatibility?.source === 'provider'"> · Player limits from a metadata provider</template></small></button>
    </div>

  </div>
</template>
<style>
.library-tools{display:flex;align-items:center;gap:8px;flex-wrap:wrap;font-size:12px;color:var(--muted);margin:12px 0}.library-selection{display:flex;align-items:center;gap:8px;border-bottom:1px solid var(--line)}.library-selection>.check{margin:0}.library-game{display:block;text-align:left;min-width:0;flex:1;padding:12px 4px}.library-game strong,.library-game span,.library-game small{display:block;overflow-wrap:anywhere}.library-game span,.library-game small{color:var(--muted);font-size:11px;font-weight:400;margin-top:5px}.bulk-preset{margin-top:16px;padding-top:16px;border-top:1px solid var(--line)}.bulk-preset ul{font-size:12px;color:var(--muted);line-height:1.6;padding-left:20px}.save-results{overflow-wrap:anywhere}
</style>
