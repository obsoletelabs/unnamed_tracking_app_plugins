<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch, nextTick } from "vue";
import { DiscordSDK } from "@discord/embedded-app-sdk";
import GenrePicker from "./GenrePicker.vue";
import GameInfoDialog from "./GameInfoDialog.vue";
import GameAttentionList from "./GameAttentionList.vue";
import LibrarySettings from "./LibrarySettings.vue";
import { platforms, genres, currencies, combinedChoices, multiplayer, connectionScopes, trackingChange, gamePlatform, readableScope } from "./options.mjs";

const pluginId = "official.discord-social-activity";
const base = `/api/public-apps/${pluginId}`;
const room = ref(null), sources = ref([]), status = ref("Connecting to Discord…");
const error = ref(""), busy = ref(false), tab = ref("night"), token = ref("");
const rolling = ref(false), directBrowser = ref(false), message = ref("");
const consent = ref(null), origin = ref(""), search = ref("");
const artwork = reactive({}), selectedLibrary = ref("");
const avatarUrls = reactive({}), catalogue = reactive({}), detailsGame = ref(null);
const pendingGameInfo = new Map();
const detailsTrackingUrl = computed(() => {
  const imported = (me.value?.library || []).find(game => key(game) === detailsGame.value?.key);
  const source = sources.value.find(item => item.id === imported?.source_id);
  return source && imported ? source.origin + '/games/' + imported.id : null;
});
const transferTarget = ref(null), multiplayerOnly = ref(true), ownedOnly = ref(true);
const hostDialog = ref(null);
watch(transferTarget, async target => { if (target) { await nextTick(); hostDialog.value?.showModal(); } });
const legacyKey = ref(""), legacyAcknowledged = ref(false), legacyMode = ref(false);
const includeProgress = ref(false), includeCompatibility = ref(false);
const gamePage = ref(1), libraryPage = ref(1);
const manual = reactive({ title: "", platform: "PC", min_players: 1, max_players: 4,
  duration_minutes: null, genres: [], owned: true, crossplay: false, steam: "" });
const rules = reactive({ platform: "Any", max_minutes: null, budget: 0, currency: "USD",
  minimum_discount: 0, allow_purchase: false, owned_only: true, genres: [], avoid_genres: [] });
const tracking = reactive({ source_id: "", game_id: "", status: "PLAYING", completion_date: "", edit_completion_date: false });
const achievements = ref(null), achievementName = ref(""), writeConfirmed = ref(false);
let sdk, timer, polling = false, destroyed = false;
const me = computed(() => room.value?.me);
const isHost = computed(() => room.value?.host_id === me.value?.id);
const people = computed(() => room.value?.participants || []);
const activePeople = computed(() => people.value.filter(person => person.active));
const games = computed(() => room.value?.shortlist?.length ? room.value.shortlist : room.value?.pool?.eligible || []);
const library = computed(() => (me.value?.library || []).filter(game => game.title.toLowerCase().includes(search.value.toLowerCase()) && (!multiplayerOnly.value || multiplayer(game) === true || game.play_compatibility) && (!ownedOnly.value || game.owned)));
watch([search, multiplayerOnly, ownedOnly], () => { libraryPage.value = 1; });
const platformChoices = computed(() => combinedChoices(platforms, [manual.platform, rules.platform, ...(me.value?.library || []).map(game => game.platform)]).filter(value => value !== "Any"));
const genreChoices = computed(() => combinedChoices(genres, [...manual.genres, ...rules.genres, ...rules.avoid_genres, ...(me.value?.library || []).flatMap(game => game.tags || [])]));
const visibleGames = computed(() => games.value.slice((gamePage.value - 1) * 6, gamePage.value * 6));
const visibleLibrary = computed(() => library.value.slice((libraryPage.value - 1) * 15, libraryPage.value * 15));
const writableSource = computed(() => sources.value.find(source => source.id === tracking.source_id));
const writableGames = computed(() => (me.value?.library || []).filter(game => game.source_id === tracking.source_id));
watch(() => [tracking.source_id, tracking.game_id], () => {
  writeConfirmed.value = false;
  achievements.value = null;
  achievementName.value = "";
  tracking.edit_completion_date = false;
  const game = writableGames.value.find(item => item.id === tracking.game_id);
  tracking.status = game?.status || "PLAYING";
  tracking.completion_date = game?.completion_date ? new Date(game.completion_date * 1000).toISOString().slice(0, 10) : "";
});
const modes = [{ id: "strict", name: "Strict", description: "Everyone owns it" },
  { id: "balanced", name: "Balanced", description: "Shared favorites first" },
  { id: "discovery", name: "Discovery", description: "Try something different" }];
function initials(name) { return name.split(/\s+/).map(word => word[0]).join("").slice(0, 2).toUpperCase(); }
function key(game) { return room.value?.matching?.title_fallback !== false ? "title:" + game.title.normalize("NFKC").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "") : game.provider_ids?.steam ? "steam:" + game.provider_ids.steam : "title:" + game.title.trim().replace(/\s+/g, " ").toLowerCase(); }
async function api(path, method = "GET", body) {
  const response = await fetch(base + path, { method, credentials: "omit",
    headers: { ...(token.value ? { Authorization: "Bearer " + token.value } : {}),
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}) },
    ...(body !== undefined ? { body: JSON.stringify(body) } : {}) });
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(typeof detail.detail === "string" ? detail.detail : `Request failed (${response.status}).`);
  }
  return response.status === 204 ? null : await response.json();
}
async function saveLibrarySettings(game, preset) {
  return await api(`/sources/${game.source_id}/games/${game.id}/play-compatibility`, "PATCH", { play_compatibility: preset });
}
async function action(values, refresh = false, quiet = false) {
  if (!quiet) { busy.value = true; error.value = ""; }
  try {
    const result = await api("/action", "POST", { values, refresh_sources: refresh });
    if (result.error) throw new Error(result.error);
    if (!destroyed) { room.value = result; status.value = "Live with your group"; gamePage.value = Math.min(gamePage.value, Math.max(1, Math.ceil(games.value.length / 6))); loadArtwork(); loadAvatars(); if (!timer) timer = setInterval(tick, 2500); }
    return result;
  } catch (err) {
    status.value = "Reconnecting · your room is saved";
    if (!quiet) error.value = err.message;
    throw err;
  } finally { if (!quiet) busy.value = false; }
}
async function perform(values, refresh = false) { try { await action(values, refresh); } catch {} }
async function roll(reroll = false) {
  rolling.value = true;
  try { await action({ operation: "roll", reroll }); }
  catch {} finally { rolling.value = false; }
}
async function loadArtwork() {
  await Promise.all(visibleGames.value.map(async game => {
    const imported = (me.value?.library || []).find(item => key(item) === game.key);
    if (artwork[game.key] !== undefined) return;
    artwork[game.key] = "";
    try {
      if (imported) {
        const response = await fetch(`${base}/sources/${imported.source_id}/games/${imported.id}/artwork/key_art`,
          { headers: { Authorization: "Bearer " + token.value }, credentials: "omit" });
        if (response.ok && !destroyed) { artwork[game.key] = URL.createObjectURL(await response.blob()); return; }
      }
      const info = await loadGameInfo(game);
      const steamId = info?.provider_ids?.steam || game.provider_ids?.steam;
      if (steamId) {
        const response = await fetch(`${base}/catalogue/${steamId}/artwork`, { headers: {Authorization: 'Bearer ' + token.value}, credentials: 'omit' });
        if (response.ok && !destroyed) artwork[game.key] = URL.createObjectURL(await response.blob());
      }
    } catch {}
  }));
}
async function loadGameInfo(game) {
  if (catalogue[game.key] !== undefined) return catalogue[game.key];
  if (pendingGameInfo.has(game.key)) return pendingGameInfo.get(game.key);
  const pending = api('/catalogue', 'POST', {title: game.title.slice(0, 200), steam_app_id: game.provider_ids?.steam ? String(game.provider_ids.steam) : null})
    .catch(() => ({matched: false}))
    .then(info => { if (!destroyed) catalogue[game.key] = info; return info; })
    .finally(() => pendingGameInfo.delete(game.key));
  pendingGameInfo.set(game.key, pending);
  return pending;
}
function openGame(game) { detailsGame.value = game; loadGameInfo(game); }
async function inviteFriends() {
  try { await sdk.commands.openInviteDialog(); }
  catch { error.value = "Discord could not open invitations here. Use Discord's Activity invite controls."; }
}
async function openLink(url) { try { await sdk.commands.openExternalLink({url}); } catch { error.value = 'Discord could not open this link. Try again.'; } }
async function loadAvatars() {
  await Promise.all(people.value.map(async person => {
    if (!person.avatar_path || avatarUrls[person.id] !== undefined) return;
    avatarUrls[person.id] = '';
    try { const response = await fetch(person.avatar_path, {headers: {Authorization: 'Bearer ' + token.value}, credentials: 'omit'}); if (response.ok && !destroyed) avatarUrls[person.id] = URL.createObjectURL(await response.blob()); } catch {}
  }));
}
async function saveManual() {
  const game = { ...manual, provider_ids: manual.steam ? { steam: manual.steam } : {} };
  delete game.steam;
  try { await action({ operation: "manual", game }); message.value = "Game added. Compatibility is labeled self-reported."; manual.title = ""; manual.genres = []; manual.steam = ""; manual.crossplay = false; manual.duration_minutes = null; selectedLibrary.value = ""; }
  catch {}
}
function annotateLibrary(game) {
  manual.title = game.title; manual.steam = game.provider_ids?.steam ? String(game.provider_ids.steam) : "";
  manual.owned = game.owned; selectedLibrary.value = game.id;
  manual.platform = gamePlatform(game, room.value.matching.steam_platform) || "PC"; manual.genres = game.tags?.slice(0, 10) || [];
  manual.min_players = multiplayer(game) === true ? 2 : 1; manual.max_players = null;
  if (game.play_compatibility) Object.assign(manual, game.play_compatibility);
  message.value = "Confirm the platform and supported player count below, then add this game.";
}
async function saveRules() {
  try { await action({ operation: "preferences", preferences: { ...rules } }); message.value = "Your personal rules are saved."; }
  catch {}
}
async function connect() {
  busy.value = true; error.value = "";
  try { consent.value = await api(legacyMode.value ? "/sources/legacy" : "/sources", "POST", legacyMode.value ? { origin: origin.value.trim(), api_key: legacyKey.value, acknowledge_unrestricted_key: legacyAcknowledged.value } : { origin: origin.value.trim(), scopes: connectionScopes(includeProgress.value, includeCompatibility.value) });
    sources.value = await api("/sources"); }
  catch (err) { error.value = err.message; } finally { busy.value = false; legacyKey.value = ""; legacyAcknowledged.value = false; }
}
async function openConsent() {
  try { await sdk.commands.openExternalLink({ url: consent.value.consent_url }); }
  catch (err) { error.value = "Open the consent link in your normal browser: " + consent.value.consent_url; }
}
async function refreshSource(source) {
  busy.value = true; error.value = "";
  try { await api(`/sources/${source.id}/refresh`, "POST"); sources.value = await api("/sources");
    await action({ operation: "snapshot" }); }
  catch (err) { error.value = err.message; } finally { busy.value = false; }
}
async function disconnectSource(source) {
  busy.value = true;
  try { await api(`/sources/${source.id}`, "DELETE"); sources.value = await api("/sources");
    await action({ operation: "snapshot" }); message.value = "Connection removed. You can also revoke its grant in your instance's Connected apps."; }
  catch (err) { error.value = err.message; } finally { busy.value = false; }
}
async function loadAchievements() {
  error.value = ""; achievements.value = null;
  try { achievements.value = await api(`/sources/${tracking.source_id}/games/${tracking.game_id}/achievements`); }
  catch (err) { error.value = err.message; }
}
async function updateTracking() {
  if (!writeConfirmed.value) return;
  busy.value = true; error.value = "";
  try { await api(`/sources/${tracking.source_id}/games/${tracking.game_id}/tracking`, "PATCH",
    trackingChange(tracking));
    message.value = "Your tracking fields were updated."; writeConfirmed.value = false; }
  catch (err) { error.value = err.message; } finally { busy.value = false; }
}
async function reportAchievement(imported) {
  if (!writeConfirmed.value) return;
  busy.value = true; error.value = "";
  try { await api(`/sources/${tracking.source_id}/games/${tracking.game_id}/achievement-reports`, "POST",
    imported ? { provider: imported.provider, external_id: imported.external_id,
      unlocked: !Boolean(imported.local_report?.unlocked ?? imported.unlocked) }
      : { provider: "manual", name: achievementName.value, unlocked: true });
    message.value = "Local self-report saved. Provider-synced evidence stays separate.";
    achievementName.value = ""; writeConfirmed.value = false; await loadAchievements(); }
  catch (err) { error.value = err.message; } finally { busy.value = false; }
}
async function tick() {
  if (polling || busy.value || !token.value || destroyed) return;
  polling = true;
  try {
    if (consent.value?.state === "pending") {
      const result = await api(`/sources/${consent.value.id}/poll`, "POST");
      if (result.state !== "pending") {
        consent.value = result; sources.value = await api("/sources");
        if (result.state === "connected") await refreshSource(result);
      }
    }
    await action({ operation: "snapshot" }, false, true);
  } catch {} finally { polling = false; }
}
onMounted(async () => {
  const display = new URLSearchParams(location.search);
  document.documentElement.dataset.theme = display.get("theme") === "light" ? "light" : "dark";
  document.documentElement.classList.toggle("reduce-motion", display.get("reduced_motion") === "true");
  document.documentElement.classList.toggle("high-contrast", display.get("high_contrast") === "true");
  try {
    const config = await api("/config");
    if (!config.provider.configured) throw new Error("The operator needs to configure the Discord bot's Activity OAuth settings.");
    if (!new URLSearchParams(location.search).has("frame_id")) {
      directBrowser.value = true; status.value = "Ready to launch from Discord"; return;
    }
    sdk = new DiscordSDK(config.provider.application_id);
    await sdk.ready();
    const authorization = await sdk.commands.authorize({ client_id: config.provider.application_id,
      response_type: "code", state: crypto.randomUUID(), prompt: "none", scope: ["identify"] });
    const session = await api("/sessions", "POST", { proof: { code: authorization.code, instance_id: sdk.instanceId } });
    await sdk.commands.authenticate(session.sdk_authentication);
    token.value = session.session_token;
    const initial = await Promise.all([api("/sources"), action({ operation: "snapshot" })]);
    sources.value = initial[0];
    Object.assign(rules, me.value.preferences);
    if (!timer) timer = setInterval(tick, 2500);
  } catch (err) { error.value = err.message; status.value = "Unable to join · try reconnecting"; }
});
onBeforeUnmount(() => { destroyed = true; clearInterval(timer);
  [...Object.values(artwork), ...Object.values(avatarUrls)].forEach(url => { if (url) URL.revokeObjectURL(url); }); });
</script>

<template>
  <a class="skip" href="#main">Skip to game night</a>
  <div class="app-shell">
    <header class="topbar"><div class="wordmark"><span class="brand-dice" aria-hidden="true">⚄</span><div>Game <b>night</b><small>Unnamed Tracking</small></div></div>
      <button v-if="room" class="secondary" @click="inviteFriends">Invite friends</button>
      <span class="live" role="status"><i :class="{ offline: status.startsWith('Reconnecting') }"></i>{{ status }}</span>
    </header>
    <main id="main"><GameInfoDialog v-if="detailsGame" :game="detailsGame" :info="catalogue[detailsGame.key]" :busy="catalogue[detailsGame.key] === undefined" :artwork="artwork[detailsGame.key]" :tracking-url="detailsTrackingUrl" @close="detailsGame = null" @open-link="openLink" /><dialog v-if="transferTarget" ref="hostDialog" class="host-confirm" aria-labelledby="transfer-title" @cancel="transferTarget = null"><h2 id="transfer-title">Make {{ transferTarget.display_name }} the host?</h2><p>They will control the room mode and shortlist. Your personal rules and vetoes stay yours.</p><button class="secondary" @click="transferTarget = null">Cancel</button> <button class="primary" :disabled="busy" @click="perform({operation:'transfer',participant_id:transferTarget.id,confirmed:true}); transferTarget = null">Confirm host transfer</button></dialog>
      <div v-if="error" class="notice error" role="alert">{{ error }}<button @click="error = ''" aria-label="Dismiss error">×</button></div>
      <div v-if="message" class="notice" role="status">{{ message }}<button @click="message = ''" aria-label="Dismiss message">×</button></div>
      <section v-if="!room" class="launch-screen">
        <div class="eyebrow">LESS DECIDING. MORE PLAYING.</div><h1>Your people.<br>Your games.<br><em>One great night.</em></h1>
        <p>Bring your library or add a few games. Find something everyone can play, shortlist the favorites, and let the group choose.</p>
        <div class="launch-dice" aria-hidden="true"><span>⚄</span><span>✦</span></div>
        <button v-if="token && !directBrowser" class="primary" :disabled="busy" @click="perform({operation:'snapshot'})">Reconnect to room</button><div class="launch-detail"><strong>{{ directBrowser ? 'Launch Game Night inside Discord' : 'Getting your room ready' }}</strong>
          <p>{{ directBrowser ? 'Open the bot in the App Launcher in a text or voice channel. Your Discord identity and room membership are verified before you join.' : status }}</p>
        </div><div class="trust-line">Your instance. Your consent. Your personal rules.</div>
      </section>
      <template v-else>
        <section class="intro"><div><div class="eyebrow">THE GROUP CHAT HAS A PLAN</div><h1>What are we playing?</h1><p>Find your overlap. Keep everyone's rules. Get to the good part.</p></div>
          <div class="room-meta"><span class="pill">{{ room.pool.player_count }} playing · {{ activePeople.length - room.pool.player_count }} watching</span><span class="pill">Round {{ room.round || '—' }}</span></div></section>
        <div class="roster" aria-label="Participants"><div v-for="person in people" :key="person.id" class="person" :class="{ away: !person.active }">
          <span class="avatar"><img v-if="avatarUrls[person.id]" :src="avatarUrls[person.id]" :alt="person.display_name + ' avatar'" /><template v-else>{{ initials(person.display_name) }}</template></span><span><strong>{{ person.display_name }}{{ person.id === me.id ? ' · You' : '' }}</strong><small>{{ person.id === room.host_id ? 'Host · ' : '' }}{{ !person.active ? 'Away' : person.spectating ? 'Watching · Add games to play' : person.connected ? 'Library linked' : 'Guest · Self-reported' }}</small></span>
          <button v-if="isHost && person.id !== me.id && person.active" class="icon-button" :aria-label="'Choose ' + person.display_name + ' as host'" @click="transferTarget = person">♛</button></div></div>
        <nav class="tabs" aria-label="Game-night sections"><button v-for="item in [{id:'night',label:'Game night'},{id:'games',label:'My games'},{id:'rules',label:'My rules'},{id:'connections',label:'Connections'},{id:'tracking',label:'Tracking'}]" :key="item.id" :aria-current="tab === item.id ? 'page' : undefined" @click="tab = item.id">{{ item.label }}</button></nav>
        <section v-if="tab === 'night'">
          <div class="mode-strip"><button v-for="mode in modes" :key="mode.id" :class="{ chosen: room.mode === mode.id }" :disabled="!isHost || busy" @click="perform({operation:'mode',mode:mode.id})"><strong>{{ mode.name }}</strong><span>{{ mode.description }}</span></button></div>
          <details class="price-note"><summary>Price filters paused</summary><p>Prices are unavailable, so budgets and discounts are not checked. Ownership and each person's purchase consent still apply. Confirm any costs before buying.</p></details><details v-if="isHost" class="room-options"><summary>Room host settings</summary><label class="check"><input type="checkbox" :checked="room.matching.title_fallback" @change="perform({operation:'matching',matching:{...room.matching,title_fallback:$event.target.checked}})" /> Match normalized titles across app IDs</label><label class="check"><input type="checkbox" :checked="room.matching.platform_aliases" @change="perform({operation:'matching',matching:{...room.matching,platform_aliases:$event.target.checked}})" /> Treat platform aliases such as PC and Windows alike</label><label class="check"><input type="checkbox" :checked="room.matching.skip_empty" @change="perform({operation:'matching',matching:{...room.matching,skip_empty:$event.target.checked}})" /> People without games spectate without blocking the pool</label><label class="check"><input type="checkbox" :checked="room.matching.small_multiplayer" @change="perform({operation:'matching',matching:{...room.matching,small_multiplayer:$event.target.checked}})" /> Accept detected multiplayer for one or two players without exact limits</label><label class="check"><input type="checkbox" :checked="room.matching.steam_platform" @change="perform({operation:'matching',matching:{...room.matching,steam_platform:$event.target.checked}})" /> Infer PC from a Steam app ID when the platform is blank</label><p class="fine">These settings preserve personal rules and vetoes. Different platforms still need everyone's crossplay confirmation.</p></details>
          <section v-if="room.selected" class="winner" aria-live="polite"><span class="eyebrow">THE GROUP HAS SPOKEN</span><h2><button class="game-title" @click="openGame(room.selected)">{{ room.selected.title }}</button></h2><p>{{ room.selected.price_status === 'unavailable' ? 'Purchase may be required · Price unknown' : 'Everyone has access · No purchase required' }} · Your rules still apply</p><button class="secondary" :disabled="!isHost || busy" @click="roll(true)">Pick another</button></section>
          <div class="section-heading"><div><h2>{{ room.phase === 'voting' ? 'Vote for tonight' : 'Your shared possibilities' }}</h2><p>{{ room.pool.eligible.length }} eligible {{ room.pool.eligible.length === 1 ? 'game' : 'games' }} · {{ room.pool.excluded.length }} need attention</p></div>
            <button class="primary" :class="{ rolling }" :disabled="!isHost || busy || !room.pool.eligible.length" @click="roll(room.phase !== 'lobby')"><span aria-hidden="true">⚄</span> {{ rolling ? 'Finding your shortlist…' : room.phase === 'lobby' ? 'Make a shortlist' : 'Reroll shortlist' }}</button></div>
          <div v-if="!games.length" class="empty"><span class="empty-symbol" aria-hidden="true">✦</span><h3>A great night starts with a little overlap.</h3><p>Add the games you can play and confirm their player counts. Your group’s eligible games will appear here.</p><button class="primary" @click="tab = 'games'">Add your games</button></div>
          <div v-else class="game-grid"><article v-for="game in visibleGames" :key="game.key" class="game-card" :class="{ voted: me.vote === game.key }">
            <div class="cover" :style="{'--cover-hue': (game.title.charCodeAt(0) * 17) % 360}"><img v-if="artwork[game.key]" :src="artwork[game.key]" :alt="game.title + ' cover artwork'" /><div v-else class="cover-fallback"><span aria-hidden="true">✦</span><strong>{{ game.title }}</strong><small>GAME NIGHT</small></div><span class="cover-tag">{{ game.price_status === 'unavailable' ? 'PRICE UNKNOWN' : 'EVERYONE CAN PLAY' }}</span></div>
            <div class="card-body"><h3><button class="game-title" @click="openGame(game)">{{ game.title }}</button></h3><p class="cost">{{ game.price_status === 'unavailable' ? 'May need a purchase · Price unknown' : 'No extra spend' }} <span>· {{ game.access.length }} {{ game.access.length === 1 ? 'player' : 'players' }}</span></p><div class="tiny-avatars" aria-label="Players with access"><span v-for="person in game.access" :key="person.participant_id" :title="person.name"><img v-if="avatarUrls[person.participant_id]" :src="avatarUrls[person.participant_id]" :alt="person.name + ' avatar'" /><template v-else>{{ initials(person.name) }}</template></span></div>
              <details><summary>Why this works</summary><ul><li v-for="reason in game.reasons" :key="reason">{{ reason }}</li></ul><p v-if="game.player_limits" class="fine">{{ game.player_limits.min_players }}–{{ game.player_limits.max_players }} players · Confirmed by {{ people.find(person => person.id === game.player_limits.confirmed_by)?.display_name || 'a participant' }}</p><p class="fine">Compatibility is self-reported. {{ game.match_provenance === 'title_match' ? 'Matched by title; confirm the same game and edition.' : 'Matched by provider ID.' }}</p></details>
              <div class="card-actions"><button v-if="room.phase === 'voting'" class="secondary" :disabled="busy" @click="perform({operation:'vote',key:game.key})">{{ me.vote === game.key ? '✓ Your vote' : 'Vote' }} · {{ game.votes || 0 }}</button><button class="quiet" :disabled="busy" @click="perform({operation:'veto',key:game.key})">Veto</button></div></div></article></div>
          <div v-if="games.length > 6" class="pagination"><button class="quiet" :disabled="gamePage === 1" @click="gamePage--; loadArtwork()">Previous</button><span>{{ gamePage }} / {{ Math.ceil(games.length / 6) }}</span><button class="quiet" :disabled="gamePage * 6 >= games.length" @click="gamePage++; loadArtwork()">Next</button></div><div v-if="me.vetoes.length" class="veto-bar"><span>Your vetoes</span><button class="pill" v-for="veto in me.vetoes" :key="veto" :disabled="busy" @click="perform({operation:'clear-veto',key:veto})">Undo veto · {{ room.pool.excluded.find(game => game.key === veto)?.title || veto.replace(/^(title|steam):/, '') }}</button></div><button v-if="room.phase === 'voting'" class="primary finish" :disabled="!isHost || busy" @click="perform({operation:'finalize'})">Choose the group’s pick →</button>
          <GameAttentionList :games="room.pool.excluded" :me="me" :busy="busy" :player-count="room.pool.player_count" :platforms="platformChoices" @action="perform" @info="openGame" />
          <details v-if="room.history.length" class="panel"><summary>Tonight's selection history</summary><p v-for="(event,index) in room.history" :key="index">Round {{ event.round }} · {{ event.title || event.titles?.join(', ') }} · {{ event.event }}</p></details>
        </section>
        <section v-if="tab === 'games'" class="games-layout">
<div class="panel"><h2>Your multiplayer library</h2><p>Owned multiplayer games are included automatically. Saved group-play details are ready to use. For one or two players, detected multiplayer is enough unless known limits disagree. Larger groups can approve games together or set known limits from Game night. Steam IDs infer PC only when the platform is blank.</p><input v-model="search" @input="libraryPage = 1" aria-label="Search connected library" placeholder="Search your library" /><label class="check"><input v-model="multiplayerOnly" @change="libraryPage = 1" type="checkbox" /> Show detected multiplayer games</label><label class="check"><input v-model="ownedOnly" type="checkbox" /> Show owned games only</label><LibrarySettings :games="visibleLibrary" :library="me.library" :sources="sources" :busy="busy" :save="saveLibrarySettings" :infer-steam="room.matching.steam_platform" @annotate="annotateLibrary" /><div v-if="library.length > 15" class="pagination"><button class="quiet" :disabled="libraryPage === 1" @click="libraryPage--">Previous</button><span>{{ libraryPage }} / {{ Math.ceil(library.length / 15) }}</span><button class="quiet" :disabled="libraryPage * 15 >= library.length" @click="libraryPage++">Next</button></div><p v-if="!library.length" class="fine">Connect and refresh an instance to bring in your games, or add a manual entry.</p><button class="secondary" @click="tab = 'connections'">Manage connections</button></div>
          <details class="panel" :open="selectedLibrary !== '' || !me.library.length"><summary>Add or edit a playable game</summary><p>No account needed when the owner allows guests. These entries are labeled self-reported.</p>
            <div v-if="me.manual.length" class="manual-list"><article v-for="game in me.manual" :key="game.key"><div><strong>{{ game.title }}</strong><small>{{ game.platform }} · {{ game.min_players }}–{{ game.max_players }} players · Self-reported</small></div><button class="quiet" @click="perform({operation:'remove-manual',key:game.key})" :aria-label="'Remove ' + game.title">×</button></article></div>
            <form @submit.prevent="saveManual"><label>Game title<input v-model="manual.title" maxlength="200" required placeholder="What can you play tonight?" /></label><div class="fields"><label>Platform<select v-model="manual.platform"><option v-for="platform in platformChoices" :key="platform">{{ platform }}</option></select></label><label>Steam app ID <small>Optional exact match</small><input v-model="manual.steam" inputmode="numeric" placeholder="e.g. 550" /></label></div><div class="fields"><label>Minimum players<input v-model.number="manual.min_players" type="number" min="1" max="32" required /></label><label>Maximum players<input v-model.number="manual.max_players" type="number" min="1" max="32" required /></label></div><label>Typical play time (minutes)<input v-model.number="manual.duration_minutes" type="number" min="1" max="1440" placeholder="Unknown" /></label><GenrePicker v-model="manual.genres" :options="genreChoices" label="Genres" /><label class="check"><input v-model="manual.owned" type="checkbox" /> I own or already have access to this game</label><label class="check"><input v-model="manual.crossplay" type="checkbox" /> I confirm cross-platform play works for our group</label><button class="primary" :disabled="busy">Add playable game</button></form>
          </details>
        </section>
        <section v-if="tab === 'rules'" class="panel rules"><div class="eyebrow">YOUR CALL. ALWAYS.</div><h2>Your personal rules</h2><p>The host can change the mode, but cannot change these rules or remove your vetoes.</p><form @submit.prevent="saveRules"><div class="fields"><label>Platform<select v-model="rules.platform"><option>Any</option><option v-for="platform in platformChoices" :key="platform">{{ platform }}</option></select></label><label>Maximum play time (minutes)<input v-model.number="rules.max_minutes" type="number" min="1" max="1440" placeholder="No limit" /></label></div><div class="fields"><GenrePicker v-model="rules.genres" :options="genreChoices" label="Preferred genres" /><GenrePicker v-model="rules.avoid_genres" :options="genreChoices" label="Excluded genres" /></div><details class="future-pricing"><summary>Budget and currency · Price filters paused</summary><div class="fields"><label>Purchase budget<input v-model.number="rules.budget" type="number" min="0" max="10000" step="0.01" /></label><label>Currency<select v-model="rules.currency"><option v-for="currency in currencies" :key="currency">{{ currency }}</option></select></label><label>Minimum discount (%)<input v-model.number="rules.minimum_discount" type="number" min="0" max="100" /></label></div><p class="fine">These preferences are saved for when verified prices become available.</p></details><label class="check"><input v-model="rules.owned_only" type="checkbox" /> Only games I already own or can access</label><label class="check"><input v-model="rules.allow_purchase" type="checkbox" /> I consent to considering a purchase within my budget</label><p class="fine">Purchase consent lets the group consider a game you do not own. Price filters are paused, and this never authorizes a purchase.</p><button class="primary" :disabled="busy">Save my rules</button></form><div v-if="me.vetoes.length"><h3>Your vetoes</h3><button class="pill" v-for="veto in me.vetoes" :key="veto" @click="perform({operation:'clear-veto',key:veto})">{{ veto.replace(/^(title|steam):/, '') }} · Remove ×</button></div></section>
        <section v-if="tab === 'connections'" class="two-column"><div class="panel"><div class="eyebrow">BRING YOUR OWN INSTANCE</div><h2>Connect your tracking app</h2><p>Sign in on your instance and approve only the access you want. Your password stays there. Write access starts unchecked.</p><form @submit.prevent="connect"><label>Your instance's HTTPS origin<input v-model="origin" type="url" required placeholder="https://your-tracker.example" /></label><label class="check"><input v-model="legacyMode" type="checkbox" /> Unsafe legacy API key · Older app versions</label><template v-if="legacyMode"><p class="fine">This key may grant unrestricted access to your account, including administration if you are an admin. The Activity operator stores it encrypted and uses it only for identity and library reads. Revoke it in your instance to end access.</p><label>Legacy API key<input v-model="legacyKey" type="password" autocomplete="off" required placeholder="utk_…" /></label><label class="check"><input v-model="legacyAcknowledged" type="checkbox" required /> I understand this key has broader access than scoped consent</label></template><label v-if="!legacyMode" class="check"><input v-model="includeProgress" type="checkbox" /> Request optional tracking and achievement access</label><label v-if="!legacyMode" class="check"><input v-model="includeCompatibility" type="checkbox" /> Request optional multiplayer settings access</label><p v-if="!legacyMode" class="fine">Library matching only requests identity and game reads. Progress access adds achievement reads and optional writes, reviewed again on your instance. Multiplayer settings access is separate and allows saving bulk presets across your connected instances.</p><button class="primary" :disabled="busy || (legacyMode && !legacyAcknowledged)">{{ legacyMode ? 'Connect legacy library' : 'Review access on my instance →' }}</button></form><div v-if="consent" class="consent"><strong>{{ consent.state === 'pending' ? 'Your consent is waiting' : 'Connection ' + consent.state }}</strong><p>{{ consent.origin }}</p><button v-if="consent.state === 'pending'" class="secondary" @click="openConsent">Open consent in browser</button><p class="fine">Approve under your own account. Return here when you’re done.</p></div></div>
          <div class="panel"><h2>Your connections</h2><article v-for="source in sources" :key="source.id" class="source"><strong>{{ source.origin }}</strong><span class="pill">{{ source.state }}</span><p>{{ source.game_count }} games · {{ source.expires_at === null ? 'Until revoked' : 'Expires ' + new Date(source.expires_at * 1000).toLocaleString() }}<span v-if="source.credential_kind === 'legacy_api_key'"> · Unsafe legacy key · Library reads only</span></p><p class="fine">{{ source.scopes.map(readableScope).join(' · ') }}</p><p class="fine">{{ source.last_checked_at ? 'Access checked ' + new Date(source.last_checked_at * 1000).toLocaleString() : 'Access has not been checked yet' }}</p><button class="secondary" :disabled="busy" @click="refreshSource(source)">Refresh library</button> <button class="quiet" :disabled="busy" @click="disconnectSource(source)">Disconnect</button></article><p v-if="!sources.length">You haven't connected an instance yet. Guest games still work when enabled by the owner.</p><p class="fine">An offline or revoked connection cannot prove current access. Guest data expires under the owner’s retention policy.</p></div></section>
        <section v-if="tab === 'tracking'" class="panel rules"><div class="eyebrow">YOUR PROGRESS, WITH YOUR APPROVAL</div><h2>Update your tracking</h2><p>These actions apply only to your own connected account. Provider achievement evidence remains separate from local self-reports.</p><label>Instance<select v-model="tracking.source_id" @change="tracking.game_id = ''; achievements = null"><option value="">Choose a connection</option><option v-for="source in sources" :value="source.id" :key="source.id">{{ source.origin }}</option></select></label><label>Game<select v-model="tracking.game_id" @change="achievements = null"><option value="">Choose your game</option><option v-for="game in writableGames" :value="game.id" :key="game.id">{{ game.title }}</option></select></label>
          <template v-if="tracking.game_id"><label class="check"><input v-model="writeConfirmed" type="checkbox" /> I approve these changes to my own tracking account</label><div class="fields"><label>Status<select v-model="tracking.status"><option v-for="item in ['BACKLOG','PLAYING','PLAYED','BEATEN','MASTERED','ON_HOLD','DROPPED','WISHLIST']" :key="item">{{ item }}</option></select></label><label class="check"><input v-model="tracking.edit_completion_date" type="checkbox" /> Change completion date</label><label v-if="tracking.edit_completion_date">Completion date<input v-model="tracking.completion_date" type="date" /><small>Leave blank to clear the date.</small></label></div><button class="primary" :disabled="busy || !writeConfirmed || !writableSource?.scopes.includes('tracking.write')" @click="updateTracking">Update my tracking</button><p v-if="!writableSource?.scopes.includes('tracking.write')" class="fine">Tracking writes need fresh consent on your instance.</p><hr /><button class="secondary" :disabled="busy || !writableSource?.scopes.includes('achievements.read')" @click="loadAchievements">Load achievements</button><div v-if="achievements"><article v-for="achievement in achievements.achievements" :key="achievement.id" class="achievement"><div><strong>{{ achievement.name }}</strong><small>Provider-synced: {{ achievement.unlocked ? 'Unlocked' : 'Locked' }} · Local report: {{ achievement.local_report ? achievement.local_report.unlocked ? 'Unlocked' : 'Locked' : 'None' }}</small></div><button class="secondary" :disabled="busy || !writeConfirmed || !writableSource?.scopes.includes('achievements.write')" @click="reportAchievement(achievement)">Toggle local report</button></article><article v-for="report in achievements.local_reports.filter(item => item.provider === 'manual')" :key="report.id" class="achievement"><strong>{{ report.name }}</strong><small>Manual self-report · {{ report.unlocked ? 'Unlocked' : 'Locked' }}</small></article><p v-if="!achievements.complete" class="fine">Showing the first page. Open your tracking app to view the remaining achievements.</p><label>Manual achievement<input v-model="achievementName" maxlength="500" placeholder="Describe your achievement" /></label><button class="secondary" :disabled="busy || !writeConfirmed || !achievementName || !writableSource?.scopes.includes('achievements.write')" @click="reportAchievement(null)">Save manual self-report</button><p class="fine">Local reports are self-reported, never provider-verified.</p></div></template></section>
      </template>
    </main><footer><span>UNNAMED TRACKING / GAME NIGHT</span><span>Everyone gets a say.</span></footer>
  </div>
</template>

<style>
/* Standalone Activity palette and controls follow the host's public semantic tokens. */
:root{color-scheme:dark;--ui-bg:#17191c;--ui-surface:#212428;--ui-surface-2:#2b2f34;--ui-border:#3a4149;--ui-text:#edf0f3;--ui-dim:#adb5c0;--ui-accent:#efac59;--ui-accent-soft:#352c21;--ui-on-accent:#251808;--ui-good:#96d5a9;--ui-good-soft:#23382b;--ui-error:#ffa6a0;--ui-error-soft:#3f2525;--ui-overlay:#000a;--panel:var(--ui-surface);--line:var(--ui-border);--muted:var(--ui-dim);--accent:var(--ui-accent);font-family:Inter,"Segoe UI",system-ui,sans-serif;color:var(--ui-text);background:var(--ui-bg);font-synthesis:none}
:root[data-theme=light]{color-scheme:light;--ui-bg:#f5f4f1;--ui-surface:#fff;--ui-surface-2:#eeece7;--ui-border:#d6d8da;--ui-text:#252a30;--ui-dim:#59616c;--ui-accent:#a4520d;--ui-accent-soft:#f7ead8;--ui-on-accent:#fff;--ui-good:#216e3e;--ui-good-soft:#e8f4ec;--ui-error:#b42318;--ui-error-soft:#fff0ee;--ui-overlay:#0f13188c}
*{box-sizing:border-box;scrollbar-width:thin;scrollbar-color:var(--ui-border) var(--ui-bg)}body{margin:0;background:var(--ui-bg)}button,input,select{font:inherit}button{min-height:40px;padding:9px 13px;border:1px solid transparent;border-radius:10px;background:var(--ui-surface-2);color:var(--ui-text);font-size:13px;font-weight:600;line-height:1.4;cursor:pointer}button:hover:not(:disabled){filter:brightness(1.08)}button:disabled{opacity:.45;cursor:not-allowed}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}input,select{width:100%;min-height:40px;padding:9px 11px;border:1px solid var(--line);border-radius:10px;background:var(--ui-bg);color:var(--ui-text);font-size:13px}input::placeholder{color:var(--muted)}label{display:flex;flex-direction:column;gap:6px;margin:12px 0;font-size:13px;font-weight:500}label small{font-weight:400;color:var(--muted)}.check{flex-direction:row;align-items:center;line-height:1.5;font-weight:400}.check input{width:18px;height:18px;min-height:18px;flex:none;accent-color:var(--accent)}h1,h2,h3,p{margin-top:0}h1{font-size:27px;line-height:1.2;letter-spacing:-.6px;margin-bottom:6px}h2{font-size:19px;line-height:1.3;letter-spacing:-.3px;margin-bottom:10px}h3{font-size:16px;line-height:1.4}p{font-size:13px;color:var(--muted);line-height:1.6}small{font-size:12px}.app-shell{max-width:1200px;padding:0 20px;margin:auto}.topbar{min-height:64px;display:flex;align-items:center;justify-content:space-between;gap:14px;border-bottom:1px solid var(--line)}.wordmark{display:flex;align-items:center;gap:10px;font-size:16px;font-weight:600}.wordmark b{font-weight:600}.wordmark small{display:block;font-size:11px;color:var(--muted);font-weight:400;margin-top:2px}.brand-dice{display:grid;place-items:center;width:34px;height:34px;font-size:28px;color:var(--accent);background:var(--ui-accent-soft);border-radius:10px}.live{display:flex;align-items:center;gap:6px;color:var(--muted);font-size:11px}.live i{width:6px;height:6px;border-radius:50%;background:var(--ui-good)}.live i.offline{background:var(--accent)}.intro{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:22px 0 12px}.intro .eyebrow,.intro>div>p{display:none}.room-meta{display:flex;flex-wrap:wrap;gap:6px}.pill{display:inline-flex;align-items:center;min-height:28px;padding:4px 9px;border:1px solid var(--line);border-radius:8px;background:var(--ui-surface-2);color:var(--muted);font-size:11px;line-height:1.4;white-space:normal}.roster{display:flex;flex-wrap:wrap;gap:8px;margin:12px 0 18px}.person{display:flex;align-items:center;gap:9px;padding:8px 10px;background:var(--ui-surface);border:1px solid var(--line);border-radius:12px}.person strong{display:block;font-size:12px}.person small{display:block;color:var(--muted);margin-top:3px;font-size:11px}.person.away{opacity:.5}.avatar{display:grid;place-items:center;width:30px;height:30px;aspect-ratio:1;flex:none;overflow:hidden;border-radius:50%;background:var(--ui-surface-2);border:1px solid var(--line);font-size:11px}.avatar img,.tiny-avatars img{width:100%;height:100%;object-fit:cover;border-radius:50%;display:block}.icon-button{min-width:32px;min-height:32px;background:transparent;padding:4px}.tabs{display:flex;gap:4px;position:sticky;top:0;z-index:3;overflow-x:auto;padding:6px 0;margin-bottom:16px;background:var(--ui-bg);border-bottom:1px solid var(--line)}.tabs button{flex:none;background:transparent;color:var(--muted);font-size:12px}.tabs button[aria-current]{background:var(--ui-accent-soft);color:var(--accent)}.mode-strip{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px}.mode-strip button{background:var(--ui-surface);border:1px solid var(--line);text-align:left;padding:11px 12px}.mode-strip strong{display:block;font-size:13px;font-weight:600}.mode-strip span{display:block;font-size:11px;font-weight:400;color:var(--muted);margin-top:3px}.mode-strip .chosen{border-color:var(--accent);background:var(--ui-accent-soft)}.mode-strip .chosen strong{color:var(--accent)}.primary{background:var(--accent);color:var(--ui-on-accent)}.secondary{background:var(--ui-surface-2);border-color:var(--line)}.quiet{background:transparent;color:var(--muted)}.quiet:hover:not(:disabled){background:var(--ui-surface-2)}.price-note,.room-options,.future-pricing{font-size:12px;color:var(--muted);margin:12px 0}summary{cursor:pointer;min-height:32px;line-height:1.6;padding:4px 0}summary:focus-visible{border-radius:6px}.room-options{padding:8px 12px;border:1px solid var(--line);border-radius:10px}.fine{font-size:12px;color:var(--muted);line-height:1.6;margin:10px 0}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;margin:22px 0 14px}.section-heading h2{margin:0 0 4px}.section-heading p{font-size:12px;margin:0}.game-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.game-card{overflow:hidden;border:1px solid var(--line);border-radius:14px;background:var(--ui-surface);min-width:0}.game-card.voted{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}.cover{aspect-ratio:16/9;position:relative;overflow:hidden;background:var(--ui-surface-2)}.cover img{width:100%;height:100%;object-fit:cover;display:block}.cover-fallback{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:16px;text-align:center;background:linear-gradient(145deg,var(--ui-accent-soft),var(--ui-surface-2))}.cover-fallback>span{font-size:25px;color:var(--accent)}.cover-fallback strong{font-size:16px;margin-top:6px;overflow-wrap:anywhere}.cover-fallback small{display:none}.cover-tag{position:absolute;bottom:8px;left:8px;padding:4px 7px;border-radius:6px;background:var(--ui-bg);color:var(--ui-good);font-size:9px;font-weight:600;border:1px solid var(--line)}.card-body{padding:13px}.card-body h3{margin:0 0 8px;overflow-wrap:anywhere}.game-title{min-height:28px;background:transparent;padding:0;color:inherit;font:inherit;text-align:left;border-radius:4px}.game-title:hover:not(:disabled){color:var(--accent);filter:none}.cost{font-size:12px;color:var(--ui-text);margin:8px 0}.cost span{color:var(--muted)}.tiny-avatars{display:flex;gap:5px;margin:10px 0}.tiny-avatars span{display:grid;place-items:center;width:26px;height:26px;aspect-ratio:1;flex:none;overflow:hidden;border-radius:50%;border:1px solid var(--line);background:var(--ui-surface-2);font-size:10px}.card-body details{font-size:12px;color:var(--muted)}.card-body ul{padding-left:18px;font-size:12px;line-height:1.65}.card-actions{display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;margin-top:12px}.card-actions button{min-height:36px}.game-facts{display:flex;gap:6px;flex-wrap:wrap;margin:8px 0}.game-facts .pill{font-size:10px}.panel{border:1px solid var(--line);border-radius:14px;background:var(--ui-surface);padding:18px;margin:14px 0}.panel>summary{font-size:14px;font-weight:600}.panel p{margin-bottom:12px}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.fields label{min-width:0}.two-column{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px}.two-column>.panel{margin-top:0}.rules{max-width:800px;margin:0 auto}.manual-list{max-height:230px;overflow:auto}.manual-list article{display:flex;align-items:center;justify-content:space-between;gap:10px;border-bottom:1px solid var(--line);padding:10px 0}.manual-list strong,.manual-list small{display:block}.manual-list small{color:var(--muted);margin-top:5px}.library-list{margin:14px 0}.library-list button{width:100%;border-radius:0;border-bottom:1px solid var(--line);background:transparent;text-align:left;padding:12px 0}.library-list strong{display:block;font-size:13px}.library-list span{display:block;font-weight:400;font-size:11px;color:var(--muted);margin-top:4px}.pagination{display:flex;align-items:center;justify-content:center;gap:10px;margin:14px 0 0;color:var(--muted);font-size:12px}.exclusions article{padding:16px 0;border-top:1px solid var(--line);font-size:13px}.exclusions ul{padding-left:18px;color:var(--muted);line-height:1.6;font-size:12px}.veto-bar{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin:16px 0;font-size:12px}.source{padding:18px 0;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.source>strong{display:block;font-size:13px;margin-bottom:8px}.source p{font-size:12px;margin:8px 0}.consent{padding:16px;border:1px solid var(--accent);background:var(--ui-accent-soft);border-radius:12px;margin-top:18px;overflow-wrap:anywhere}.notice{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--line);border-radius:10px;background:var(--ui-good-soft);color:var(--ui-good);font-size:12px;padding:10px 12px;margin:12px 0}.notice button{min-height:28px;background:transparent;color:inherit;padding:0 6px;font-size:19px}.notice.error{background:var(--ui-error-soft);color:var(--ui-error)}.empty{padding:28px 20px;border:1px dashed var(--line);border-radius:14px;text-align:center;background:var(--ui-surface)}.empty-symbol{display:block;font-size:28px;color:var(--accent);margin-bottom:10px}.empty h3{margin-bottom:8px}.empty p{max-width:460px;margin:0 auto 18px}.winner{border:1px solid var(--accent);border-radius:14px;background:var(--ui-accent-soft);padding:22px;margin:20px 0}.winner h2{font-size:26px;margin-bottom:8px}.winner p{font-size:12px}.eyebrow{color:var(--accent);font-size:11px;font-weight:600;margin-bottom:10px}.finish{display:block;margin:18px auto}.achievement{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:16px 0;border-bottom:1px solid var(--line)}.achievement strong,.achievement small{display:block}.achievement small{color:var(--muted);line-height:1.5;margin-top:5px}.host-confirm{width:min(460px,calc(100% - 32px));max-height:85vh;overflow:auto;padding:24px;background:var(--ui-surface);color:var(--ui-text);border:1px solid var(--line);border-radius:20px}.host-confirm::backdrop{background:var(--ui-overlay)}.launch-screen{padding:48px 0;min-height:510px;position:relative;overflow:hidden}.launch-screen h1{font-size:clamp(34px,6vw,58px);letter-spacing:-1px;max-width:650px;position:relative;z-index:1}.launch-screen em{font-style:normal;color:var(--accent)}.launch-screen>p{max-width:430px;font-size:14px}.launch-detail{padding:12px 16px;border-left:2px solid var(--accent);max-width:450px;margin:24px 0}.launch-detail p{margin:8px 0 0;font-size:12px}.launch-dice{position:absolute;right:25px;top:100px;width:220px;height:240px;border:1px solid var(--line);border-radius:24px;background:var(--ui-accent-soft);display:grid;place-items:center;transform:rotate(10deg);opacity:.6}.launch-dice span:first-child{font-size:170px;color:var(--accent)}.launch-dice span:last-child{position:absolute;right:-12px;top:-20px;font-size:52px;color:var(--accent)}.trust-line{font-size:11px;color:var(--muted)}footer{display:flex;justify-content:space-between;gap:16px;padding:16px 0;margin-top:24px;border-top:1px solid var(--line);color:var(--muted);font-size:10px}.skip{position:absolute;top:-60px;left:12px;padding:12px;z-index:30;background:var(--accent);color:var(--ui-on-accent);border-radius:8px}.skip:focus{top:8px}hr{border:0;border-top:1px solid var(--line);margin:24px 0}.rolling span{display:inline-block;animation:turn 1s linear infinite}@keyframes turn{to{transform:rotate(360deg)}}
@media(max-width:850px){.two-column{grid-template-columns:1fr}.game-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.launch-dice{right:-60px;opacity:.2}}
@media(max-width:540px){.app-shell{padding:0 14px}.topbar{flex-wrap:wrap;gap:8px;padding:12px 0}.topbar .live{font-size:10px}.intro{flex-wrap:wrap;margin-top:18px}.room-meta{gap:6px}.intro h1{font-size:24px}.tabs button{padding:9px 10px}.mode-strip button{padding:10px 8px}.mode-strip span{font-size:10px}.section-heading{align-items:flex-start;gap:10px}.section-heading h2{font-size:18px}.section-heading>.primary{font-size:12px;padding:9px 11px}.game-grid{gap:10px}.card-body{padding:11px}.card-body h3{font-size:15px}.panel{padding:15px}.person{padding:7px 9px}.avatar{width:28px;height:28px}.launch-dice{right:-130px}.achievement{display:block}.achievement button{margin-top:10px}}
@media(max-width:380px){.game-grid,.fields{grid-template-columns:1fr}.section-heading{display:block}.section-heading>.primary{width:100%;margin-top:12px}.mode-strip span{display:none}.wordmark small{display:none}.room-meta .pill{font-size:10px}footer{flex-wrap:wrap}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}:root.reduce-motion *{animation:none!important;transition:none!important;scroll-behavior:auto!important}:root.high-contrast{--ui-dim:var(--ui-text)}
</style>
