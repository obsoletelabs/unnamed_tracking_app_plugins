<script setup>
import { ref, onMounted, computed } from "vue";
const props = defineProps({ game: Object, info: Object, artwork: String, trackingUrl: String, busy: Boolean });
const emit = defineEmits(["close", "open-link"]);
const dialog = ref(null);
const description = computed(() => (props.info?.description || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").slice(0, 1500));
const steamId = computed(() => props.info?.provider_ids?.steam || props.game.provider_ids?.steam);
onMounted(() => dialog.value.showModal());
</script>
<template>
  <dialog ref="dialog" class="game-info" aria-labelledby="game-info-title" @cancel="emit('close')">
    <button class="quiet dialog-close" aria-label="Close game information" @click="emit('close')">×</button>
    <h2 id="game-info-title">{{ game.title }}</h2>
    <img v-if="artwork" :src="artwork" :alt="game.title + ' artwork'" class="info-cover" />
    <p v-if="busy" role="status">Finding public game information…</p>
    <p v-if="description">{{ description }}</p>
    <p v-if="info?.developer">Developer · {{ info.developer }}</p>
    <p v-if="info?.genres?.length">Genres · {{ info.genres.join(', ') }}</p>
    <p v-if="info?.features?.length">Features · {{ info.features.join(' · ') }}</p>
    <p v-if="!busy && !info?.matched">Public metadata is unavailable for this title. Your group's own game details still apply.</p>
    <p v-if="game.group_approval" class="fine">Approved for the current {{ game.group_approval.players }} players. Exact limits remain unknown.</p>
    <ul><li v-for="person in game.access" :key="person.participant_id">{{ person.name }} · {{ person.platform }}<span v-if="person.platform_provenance === 'inferred_steam'"> (inferred from Steam)</span> · {{ person.owned ? 'Has access' : 'Considering a purchase · Price unknown' }} · {{ person.min_players != null ? person.min_players + '–' + person.max_players + ' players' : 'Exact player limits unknown' }}<span v-if="person.compatibility === 'detected_multiplayer'"> · Detected multiplayer accepted for this small group</span></li></ul>
    <div class="info-links"><button v-if="steamId" class="secondary" @click="emit('open-link', 'https://store.steampowered.com/app/' + steamId + '/')">Steam page ↗</button><button v-if="trackingUrl" class="primary" @click="emit('open-link', trackingUrl)">My tracking page ↗</button><button class="quiet" @click="emit('close')">Close</button></div>
  </dialog>
</template>
<style>
.game-info{width:min(600px,calc(100% - 30px));max-height:85vh;overflow:auto;background:var(--ui-surface);color:var(--ui-text);border:1px solid var(--line);border-radius:14px;padding:24px}.game-info::backdrop{background:#0009}.dialog-close{float:right;font-size:22px;padding:0 5px}.info-cover{float:left;width:110px;height:155px;object-fit:cover;border-radius:9px;margin:0 18px 12px 0}.game-info ul{clear:both;font-size:12px;line-height:1.8;color:var(--muted);padding-left:20px}.info-links{clear:both;display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}
</style>
