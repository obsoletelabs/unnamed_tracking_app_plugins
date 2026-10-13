<script setup>
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch, nextTick } from "vue";
import { DiscordSDK } from "@discord/embedded-app-sdk";
import GenrePicker from "./GenrePicker.vue";
import GameInfoDialog from "./GameInfoDialog.vue";
import { platforms, genres, currencies, combinedChoices, multiplayer, connectionScopes } from "./options.mjs";

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
const includeProgress = ref(false);
const gamePage = ref(1), libraryPage = ref(1);
const manual = reactive({ title: "", platform: "PC", min_players: 1, max_players: 4,
  duration_minutes: null, genres: [], owned: true, crossplay: false, steam: "" });
const rules = reactive({ platform: "Any", max_minutes: null, budget: 0, currency: "USD",
  minimum_discount: 0, allow_purchase: false, owned_only: true, genres: [], avoid_genres: [] });
const tracking = reactive({ source_id: "", game_id: "", status: "PLAYING", completion_date: "" });
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
  manual.platform = game.platform || "PC"; manual.genres = game.tags?.slice(0, 10) || [];
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
  try { consent.value = await api(legacyMode.value ? "/sources/legacy" : "/sources", "POST", legacyMode.value ? { origin: origin.value.trim(), api_key: legacyKey.value, acknowledge_unrestricted_key: legacyAcknowledged.value } : { origin: origin.value.trim(), scopes: connectionScopes(includeProgress.value) });
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
    { status: tracking.status, completion_date: tracking.completion_date ? Math.floor(new Date(tracking.completion_date).getTime() / 1000) : null });
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
    achievementName.value = ""; await loadAchievements(); }
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
    <header class="topbar"><div class="wordmark"><span class="brand-dice" aria-hidden="true">⚄</span><div>GAME <b>NIGHT</b><small>BY UNNAMED TRACKING</small></div></div>
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
          <span class="avatar"><img v-if="avatarUrls[person.id]" :src="avatarUrls[person.id]" :alt="person.display_name + ' avatar'" /><template v-else>{{ initials(person.display_name) }}</template></span><span><strong>{{ person.display_name }}{{ person.id === me.id ? ' · You' : '' }}</strong><small>{{ person.id === room.host_id ? 'Host · ' : '' }}{{ !person.active ? 'Away' : person.spectating ? 'Watching · Add games to play' : person.ready ? 'Games ready' : 'Adding games' }}</small></span>
          <button v-if="isHost && person.id !== me.id && person.active" class="icon-button" :aria-label="'Choose ' + person.display_name + ' as host'" @click="transferTarget = person">♛</button></div></div>
        <nav class="tabs" aria-label="Game-night sections"><button v-for="item in [{id:'night',label:'Game night'},{id:'games',label:'My games'},{id:'rules',label:'My rules'},{id:'connections',label:'Connections'},{id:'tracking',label:'Tracking'}]" :key="item.id" :aria-current="tab === item.id ? 'page' : undefined" @click="tab = item.id">{{ item.label }}</button></nav>
        <section v-if="tab === 'night'">
          <div class="mode-strip"><button v-for="mode in modes" :key="mode.id" :class="{ chosen: room.mode === mode.id }" :disabled="!isHost || busy" @click="perform({operation:'mode',mode:mode.id})"><strong>{{ mode.name }}</strong><span>{{ mode.description }}</span></button></div>
          <details class="price-note"><summary>Price filters paused</summary><p>Prices are unavailable, so budgets and discounts are not checked. Ownership and each person's purchase consent still apply. Confirm any costs before buying.</p></details><details v-if="isHost" class="room-options"><summary>Room host settings</summary><label class="check"><input type="checkbox" :checked="room.matching.title_fallback" @change="perform({operation:'matching',matching:{...room.matching,title_fallback:$event.target.checked}})" /> Match normalized titles across app IDs</label><label class="check"><input type="checkbox" :checked="room.matching.platform_aliases" @change="perform({operation:'matching',matching:{...room.matching,platform_aliases:$event.target.checked}})" /> Treat platform aliases such as PC and Windows alike</label><label class="check"><input type="checkbox" :checked="room.matching.skip_empty" @change="perform({operation:'matching',matching:{...room.matching,skip_empty:$event.target.checked}})" /> People without games spectate without blocking the pool</label><p class="fine">These settings preserve personal rules and vetoes. Different platforms still need everyone's crossplay confirmation.</p></details>
          <section v-if="room.selected" class="winner" aria-live="polite"><span class="eyebrow">THE GROUP HAS SPOKEN</span><h2><button class="game-title" @click="openGame(room.selected)">{{ room.selected.title }}</button></h2><p>{{ room.selected.price_status === 'unavailable' ? 'Purchase may be required · Price unknown' : 'Everyone has access · No purchase required' }} · Your rules still apply</p><button class="secondary" :disabled="!isHost || busy" @click="roll(true)">Pick another</button></section>
          <div class="section-heading"><div><h2>{{ room.phase === 'voting' ? 'Vote for tonight' : 'Your shared possibilities' }}</h2><p>{{ room.pool.eligible.length }} eligible {{ room.pool.eligible.length === 1 ? 'game' : 'games' }} · {{ room.pool.excluded.length }} need attention</p></div>
            <button class="primary" :class="{ rolling }" :disabled="!isHost || busy || !room.pool.eligible.length" @click="roll(room.phase !== 'lobby')"><span aria-hidden="true">⚄</span> {{ rolling ? 'Finding your shortlist…' : room.phase === 'lobby' ? 'Make a shortlist' : 'Reroll shortlist' }}</button></div>
          <div v-if="!games.length" class="empty"><span class="empty-symbol" aria-hidden="true">✦</span><h3>A great night starts with a little overlap.</h3><p>Add the games you can play and confirm their player counts. Your group’s eligible games will appear here.</p><button class="primary" @click="tab = 'games'">Add your games</button></div>
          <div v-else class="game-grid"><article v-for="game in visibleGames" :key="game.key" class="game-card" :class="{ voted: me.vote === game.key }">
            <div class="cover" :style="{'--cover-hue': (game.title.charCodeAt(0) * 17) % 360}"><img v-if="artwork[game.key]" :src="artwork[game.key]" :alt="game.title + ' cover artwork'" /><div v-else class="cover-fallback"><span aria-hidden="true">✦</span><strong>{{ game.title }}</strong><small>GAME NIGHT</small></div><span class="cover-tag">{{ game.price_status === 'unavailable' ? 'PRICE UNKNOWN' : 'EVERYONE CAN PLAY' }}</span></div>
            <div class="card-body"><h3><button class="game-title" @click="openGame(game)">{{ game.title }}</button></h3><p class="cost">{{ game.price_status === 'unavailable' ? 'May need a purchase · Price unknown' : 'No extra spend' }} <span>· {{ game.access.length }} {{ game.access.length === 1 ? 'player' : 'players' }}</span></p><div class="tiny-avatars" aria-label="Players with access"><span v-for="person in game.access" :key="person.participant_id" :title="person.name"><img v-if="avatarUrls[person.participant_id]" :src="avatarUrls[person.participant_id]" :alt="person.name + ' avatar'" /><template v-else>{{ initials(person.name) }}</template></span></div>
              <details><summary>Why this works</summary><ul><li v-for="reason in game.reasons" :key="reason">{{ reason }}</li></ul><p class="fine">Compatibility is self-reported. {{ game.match_provenance === 'title_match' ? 'Matched by title; confirm the same game and edition.' : 'Matched by provider ID.' }}</p></details>
              <div class="card-actions"><button v-if="room.phase === 'voting'" class="secondary" :disabled="busy" @click="perform({operation:'vote',key:game.key})">{{ me.vote === game.key ? '✓ Your vote' : 'Vote' }} · {{ game.votes || 0 }}</button><button class="quiet" :disabled="busy" @click="perform({operation:'veto',key:game.key})">Veto</button></div></div></article></div>
          <div v-if="games.length > 6" class="pagination"><button class="quiet" :disabled="gamePage === 1" @click="gamePage--; loadArtwork()">Previous</button><span>{{ gamePage }} / {{ Math.ceil(games.length / 6) }}</span><button class="quiet" :disabled="gamePage * 6 >= games.length" @click="gamePage++; loadArtwork()">Next</button></div><div v-if="me.vetoes.length" class="veto-bar"><span>Your vetoes</span><button class="pill" v-for="veto in me.vetoes" :key="veto" :disabled="busy" @click="perform({operation:'clear-veto',key:veto})">Undo veto · {{ room.pool.excluded.find(game => game.key === veto)?.title || veto.replace(/^(title|steam):/, '') }}</button></div><button v-if="room.phase === 'voting'" class="primary finish" :disabled="!isHost || busy" @click="perform({operation:'finalize'})">Choose the group’s pick →</button>
          <details class="panel exclusions" v-if="room.pool.excluded.length"><summary>Why {{ room.pool.excluded.length }} games are excluded</summary><article v-for="game in room.pool.excluded.slice(0,100)" :key="game.key"><strong>{{ game.title }}</strong><button v-if="me.vetoes.includes(game.key)" class="quiet" :disabled="busy" @click="perform({operation:'clear-veto',key:game.key})">Undo veto</button><ul><li v-for="reason in game.excluded_reasons" :key="reason">{{ reason }}</li></ul></article></details>
          <details v-if="room.history.length" class="panel"><summary>Tonight's selection history</summary><p v-for="(event,index) in room.history" :key="index">Round {{ event.round }} · {{ event.title || event.titles?.join(', ') }} · {{ event.event }}</p></details>
        </section>
        <section v-if="tab === 'games'" class="two-column">
          <div class="panel"><div class="eyebrow">BRING SOMETHING TO THE TABLE</div><h2>Your playable games</h2><p>No account needed when the owner allows guests. These entries are labeled self-reported.</p>
            <div v-if="me.manual.length" class="manual-list"><article v-for="game in me.manual" :key="game.key"><div><strong>{{ game.title }}</strong><small>{{ game.platform }} · {{ game.min_players }}–{{ game.max_players }} players · Self-reported</small></div><button class="quiet" @click="perform({operation:'remove-manual',key:game.key})" :aria-label="'Remove ' + game.title">×</button></article></div>
            <form @submit.prevent="saveManual"><label>Game title<input v-model="manual.title" maxlength="200" required placeholder="What can you play tonight?" /></label><div class="fields"><label>Platform<select v-model="manual.platform"><option v-for="platform in platformChoices" :key="platform">{{ platform }}</option></select></label><label>Steam app ID <small>Optional exact match</small><input v-model="manual.steam" inputmode="numeric" placeholder="e.g. 550" /></label></div><div class="fields"><label>Minimum players<input v-model.number="manual.min_players" type="number" min="1" max="32" required /></label><label>Maximum players<input v-model.number="manual.max_players" type="number" min="1" max="32" required /></label></div><label>Typical play time (minutes)<input v-model.number="manual.duration_minutes" type="number" min="1" max="1440" placeholder="Unknown" /></label><GenrePicker v-model="manual.genres" :options="genreChoices" label="Genres" /><label class="check"><input v-model="manual.owned" type="checkbox" /> I own or already have access to this game</label><label class="check"><input v-model="manual.crossplay" type="checkbox" /> I confirm cross-platform play works for our group</label><button class="primary" :disabled="busy">Add playable game</button></form>
          </div><div class="panel"><h2>Your multiplayer library</h2><p>Owned multiplayer games are included automatically. Saved group-play details are ready to use. Only games missing player limits need confirmation; genres, duration and Steam ID are optional.</p><input v-model="search" @input="libraryPage = 1" aria-label="Search connected library" placeholder="Search your library" /><label class="check"><input v-model="multiplayerOnly" @change="libraryPage = 1" type="checkbox" /> Show detected multiplayer games</label><label class="check"><input v-model="ownedOnly" type="checkbox" /> Show owned games only</label><div class="library-list"><button v-for="game in visibleLibrary" :key="game.source_id + game.id" @click="annotateLibrary(game)"><strong>{{ game.title }}</strong><span>{{ multiplayer(game) === true ? 'Multiplayer' : multiplayer(game) === false ? 'Single-player' : 'Multiplayer unknown' }} · {{ game.owned ? 'Owned' : 'Wishlist' }} · {{ game.play_compatibility ? 'Saved player limits' : 'Confirm player limits' }} →</span></button></div><div v-if="library.length > 15" class="pagination"><button class="quiet" :disabled="libraryPage === 1" @click="libraryPage--">Previous</button><span>{{ libraryPage }} / {{ Math.ceil(library.length / 15) }}</span><button class="quiet" :disabled="libraryPage * 15 >= library.length" @click="libraryPage++">Next</button></div><p v-if="!library.length" class="fine">Connect and refresh an instance to bring in your games, or add a manual entry.</p><button class="secondary" @click="tab = 'connections'">Manage connections</button></div>
        </section>
        <section v-if="tab === 'rules'" class="panel rules"><div class="eyebrow">YOUR CALL. ALWAYS.</div><h2>Your personal rules</h2><p>The host can change the mode, but cannot change these rules or remove your vetoes.</p><form @submit.prevent="saveRules"><div class="fields"><label>Platform<select v-model="rules.platform"><option>Any</option><option v-for="platform in platformChoices" :key="platform">{{ platform }}</option></select></label><label>Maximum play time (minutes)<input v-model.number="rules.max_minutes" type="number" min="1" max="1440" placeholder="No limit" /></label></div><div class="fields"><GenrePicker v-model="rules.genres" :options="genreChoices" label="Preferred genres" /><GenrePicker v-model="rules.avoid_genres" :options="genreChoices" label="Excluded genres" /></div><details class="future-pricing"><summary>Budget and currency · Price filters paused</summary><div class="fields"><label>Purchase budget<input v-model.number="rules.budget" type="number" min="0" max="10000" step="0.01" /></label><label>Currency<select v-model="rules.currency"><option v-for="currency in currencies" :key="currency">{{ currency }}</option></select></label><label>Minimum discount (%)<input v-model.number="rules.minimum_discount" type="number" min="0" max="100" /></label></div><p class="fine">These preferences are saved for when verified prices become available.</p></details><label class="check"><input v-model="rules.owned_only" type="checkbox" /> Only games I already own or can access</label><label class="check"><input v-model="rules.allow_purchase" type="checkbox" /> I consent to considering a purchase within my budget</label><p class="fine">Purchase consent lets the group consider a game you do not own. Price filters are paused, and this never authorizes a purchase.</p><button class="primary" :disabled="busy">Save my rules</button></form><div v-if="me.vetoes.length"><h3>Your vetoes</h3><button class="pill" v-for="veto in me.vetoes" :key="veto" @click="perform({operation:'clear-veto',key:veto})">{{ veto.replace(/^(title|steam):/, '') }} · Remove ×</button></div></section>
        <section v-if="tab === 'connections'" class="two-column"><div class="panel"><div class="eyebrow">BRING YOUR OWN INSTANCE</div><h2>Connect your tracking app</h2><p>Sign in on your instance and approve only the access you want. Your password stays there. Write access starts unchecked.</p><form @submit.prevent="connect"><label>Your instance's HTTPS origin<input v-model="origin" type="url" required placeholder="https://your-tracker.example" /></label><label class="check"><input v-model="legacyMode" type="checkbox" /> Unsafe legacy API key · Older app versions</label><template v-if="legacyMode"><p class="fine">This key may grant unrestricted access to your account, including administration if you are an admin. The Activity operator stores it encrypted and uses it only for identity and library reads. Revoke it in your instance to end access.</p><label>Legacy API key<input v-model="legacyKey" type="password" autocomplete="off" required placeholder="utk_…" /></label><label class="check"><input v-model="legacyAcknowledged" type="checkbox" required /> I understand this key has broader access than scoped consent</label></template><label v-if="!legacyMode" class="check"><input v-model="includeProgress" type="checkbox" /> Request optional tracking and achievement access</label><p v-if="!legacyMode" class="fine">Library matching only requests identity and game reads. Progress access adds achievement reads and optional writes, reviewed again on your instance.</p><button class="primary" :disabled="busy || (legacyMode && !legacyAcknowledged)">{{ legacyMode ? 'Connect legacy library' : 'Review access on my instance →' }}</button></form><div v-if="consent" class="consent"><strong>{{ consent.state === 'pending' ? 'Your consent is waiting' : 'Connection ' + consent.state }}</strong><p>{{ consent.origin }}</p><button v-if="consent.state === 'pending'" class="secondary" @click="openConsent">Open consent in browser</button><p class="fine">Approve under your own account. Return here when you’re done.</p></div></div>
          <div class="panel"><h2>Your connections</h2><article v-for="source in sources" :key="source.id" class="source"><strong>{{ source.origin }}</strong><span class="pill">{{ source.state }}</span><p>{{ source.game_count }} games · {{ source.expires_at === null ? 'Until revoked' : 'Expires ' + new Date(source.expires_at * 1000).toLocaleString() }}<span v-if="source.credential_kind === 'legacy_api_key'"> · Unsafe legacy key · Library reads only</span></p><p class="fine">{{ source.scopes.join(' · ') }}</p><button class="secondary" :disabled="busy" @click="refreshSource(source)">Refresh library</button> <button class="quiet" :disabled="busy" @click="disconnectSource(source)">Disconnect</button></article><p v-if="!sources.length">You haven't connected an instance yet. Guest games still work when enabled by the owner.</p><p class="fine">An offline or revoked connection cannot prove current access. Guest data expires under the owner’s retention policy.</p></div></section>
        <section v-if="tab === 'tracking'" class="panel rules"><div class="eyebrow">YOUR PROGRESS, WITH YOUR APPROVAL</div><h2>Update your tracking</h2><p>These actions apply only to your own connected account. Provider achievement evidence remains separate from local self-reports.</p><label>Instance<select v-model="tracking.source_id" @change="tracking.game_id = ''; achievements = null"><option value="">Choose a connection</option><option v-for="source in sources" :value="source.id" :key="source.id">{{ source.origin }}</option></select></label><label>Game<select v-model="tracking.game_id" @change="achievements = null"><option value="">Choose your game</option><option v-for="game in writableGames" :value="game.id" :key="game.id">{{ game.title }}</option></select></label>
          <template v-if="tracking.game_id"><label class="check"><input v-model="writeConfirmed" type="checkbox" /> I approve these changes to my own tracking account</label><div class="fields"><label>Status<select v-model="tracking.status"><option v-for="item in ['BACKLOG','PLAYING','PLAYED','BEATEN','MASTERED','ON_HOLD','DROPPED','WISHLIST']" :key="item">{{ item }}</option></select></label><label>Completion date<input v-model="tracking.completion_date" type="date" /></label></div><button class="primary" :disabled="busy || !writeConfirmed || !writableSource?.scopes.includes('tracking.write')" @click="updateTracking">Update my tracking</button><p v-if="!writableSource?.scopes.includes('tracking.write')" class="fine">Tracking writes need fresh consent on your instance.</p><hr /><button class="secondary" :disabled="busy || !writableSource?.scopes.includes('achievements.read')" @click="loadAchievements">Load achievements</button><div v-if="achievements"><article v-for="achievement in achievements.achievements" :key="achievement.id" class="achievement"><div><strong>{{ achievement.name }}</strong><small>Provider-synced: {{ achievement.unlocked ? 'Unlocked' : 'Locked' }} · Local report: {{ achievement.local_report ? achievement.local_report.unlocked ? 'Unlocked' : 'Locked' : 'None' }}</small></div><button class="secondary" :disabled="busy || !writeConfirmed || !writableSource?.scopes.includes('achievements.write')" @click="reportAchievement(achievement)">Toggle local report</button></article><label>Manual achievement<input v-model="achievementName" maxlength="500" placeholder="Describe your achievement" /></label><button class="secondary" :disabled="busy || !writeConfirmed || !achievementName || !writableSource?.scopes.includes('achievements.write')" @click="reportAchievement(null)">Save manual self-report</button><p class="fine">Local reports are self-reported, never provider-verified.</p></div></template></section>
      </template>
    </main><footer><span>UNNAMED TRACKING / GAME NIGHT</span><span>Everyone gets a say.</span></footer>
  </div>
</template>

<style>
:root{font-family:Inter,ui-sans-serif,system-ui,sans-serif;color:#eeeef4;background:#11121b;font-synthesis:none;color-scheme:dark;--accent:#d9ec8c;--muted:#a6a7b9;--panel:#1b1d2b;--line:#343647}*{box-sizing:border-box}body{margin:0;background:radial-gradient(ellipse at 85% 0%,#34305055,transparent 45%),#11121b}button,input,select{font:inherit}button{cursor:pointer}button:disabled{cursor:not-allowed;opacity:.45}button:focus-visible,input:focus-visible,select:focus-visible,summary:focus-visible,a:focus-visible{outline:3px solid #d9ec8c;outline-offset:4px}button{border:0;border-radius:10px;padding:12px 16px;color:inherit;background:#333649;font-weight:650}input,select{width:100%;padding:12px 14px;background:#11131f;border:1px solid #46485d;border-radius:9px;color:#f3f3f9}input::placeholder{color:#83859b}label{display:flex;flex-direction:column;gap:8px;font-size:14px;font-weight:550;margin:16px 0}label small{color:var(--muted);font-weight:400}.check{flex-direction:row;align-items:center;font-weight:400;line-height:1.5}.check input{width:19px;height:19px;accent-color:var(--accent);flex-shrink:0}h1,h2,h3,p{margin-top:0}h1{font-size:clamp(29px,4vw,44px);letter-spacing:-1.5px;line-height:1.12;margin-bottom:14px}h2{font-size:24px;letter-spacing:-.7px;margin-bottom:10px}h3{font-size:18px}p{color:#b8b9ca;line-height:1.65;font-size:14px}small{font-size:12px}.app-shell{max-width:1280px;padding:0 32px;margin:auto}.topbar{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);min-height:94px;gap:16px}.wordmark{display:flex;gap:12px;font-size:19px;letter-spacing:2px;font-weight:450}.wordmark b{font-weight:850}.wordmark small{display:block;font-size:8px;letter-spacing:2.1px;color:var(--muted);margin-top:5px}.brand-dice{width:42px;height:42px;display:grid;place-items:center;background:var(--accent);border-radius:11px;color:#14151f;font-size:37px;line-height:1;transform:rotate(-8deg)}.live{color:var(--muted);font-size:11px;display:flex;align-items:center;gap:7px}.live i{width:6px;height:6px;border-radius:50%;background:var(--accent)}.live i.offline{background:#efb277}.intro{margin-top:42px;display:flex;justify-content:space-between;align-items:center;gap:20px}.eyebrow{font-size:10px;letter-spacing:2.2px;font-weight:750;color:var(--accent);margin-bottom:15px}.room-meta{display:flex;gap:8px}.pill{background:#272a3b;color:#c6c8dc;border:1px solid #3c3f53;border-radius:30px;padding:7px 11px;font-size:11px;white-space:nowrap}.roster{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0 30px}.person{display:flex;gap:10px;align-items:center;border:1px solid var(--line);border-radius:12px;padding:11px 15px;background:#1b1d2acc}.person strong{font-size:12px;display:block}.person small{display:block;color:var(--muted);margin-top:3px;font-size:10px}.avatar{border:1px solid #6a5d98;border-radius:50%;background:#54437d;font-size:12px;font-weight:700;width:32px;height:32px;display:grid;place-items:center}.person.away{opacity:.55}.icon-button{padding:5px;background:transparent}.tabs{display:flex;gap:5px;border-bottom:1px solid var(--line);padding-bottom:10px;margin-bottom:26px;overflow:auto}.tabs button{border-radius:7px;background:transparent;color:#aaacc2;font-size:13px;white-space:nowrap}.tabs button[aria-current]{background:#333342;color:#f1f2f7}.mode-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}.mode-strip button{text-align:left;background:#1c1f2d;border:1px solid var(--line);padding:18px}.mode-strip strong{display:block;margin-bottom:5px;font-size:15px}.mode-strip span{color:var(--muted);font-size:12px;font-weight:400}.mode-strip .chosen{border-color:#b6c873;background:#2b3025}.mode-strip .chosen strong{color:var(--accent)}.fine{font-size:11px;line-height:1.7;color:#999db4;margin:12px 0}.section-heading{display:flex;align-items:center;justify-content:space-between;gap:20px;margin:35px 0 20px}.section-heading h2{font-size:23px;margin:0 0 7px}.section-heading p{margin:0;font-size:12px}.primary{background:var(--accent);color:#22281b;padding:13px 18px;box-shadow:0 2px 0 #9dad63;font-size:13px}.primary span{font-size:20px;margin-right:6px}.secondary{background:#343346;border:1px solid #5a566b;font-size:12px}.quiet{background:transparent;color:#b8b5ce;font-size:12px}.game-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}.game-card{border-radius:15px;border:1px solid var(--line);overflow:hidden;background:var(--panel)}.game-card.voted{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}.cover{height:230px;position:relative;background:#302945}.cover img{width:100%;height:100%;object-fit:cover}.cover-fallback{height:100%;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;padding:25px;background:radial-gradient(circle at 10% 10%,hsl(var(--cover-hue) 35% 42%),transparent 65%),linear-gradient(135deg,#2c2948,#171a2b)}.cover-fallback>span{font-size:65px;color:#ffffff38}.cover-fallback strong{font-size:24px;font-weight:800;letter-spacing:-.7px;margin-top:10px}.cover-fallback small{letter-spacing:4px;font-size:8px;margin:12px;color:#ffffff70}.cover-tag{position:absolute;bottom:14px;left:14px;border:1px solid #d6e9a34d;border-radius:6px;background:#171e17e6;color:#d8ed9e;font-size:8px;padding:6px 9px;letter-spacing:1px}.card-body{padding:19px}.card-body h3{margin-bottom:7px;letter-spacing:-.4px}.cost{font-size:11px;color:#dde7b9}.cost span{color:var(--muted)}.tiny-avatars{display:flex;gap:5px;margin:12px 0 16px}.tiny-avatars span{font-size:9px;background:#3e3657;border:1px solid #655b7c;border-radius:50%;padding:6px}.card-body summary{font-size:12px;color:#bab7d0}.card-body ul{padding-left:20px;color:var(--muted);font-size:11px;line-height:1.7}.card-actions{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:15px}.finish{display:block;margin:25px auto}.empty{padding:60px 25px;border:1px dashed #555065;border-radius:15px;text-align:center;background:linear-gradient(120deg,#29243b44,#1b203144)}.empty p{max-width:430px;margin:0 auto 25px}.empty-symbol{font-size:55px;color:#8874b7;display:block;margin-bottom:17px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:15px;padding:26px;margin:18px 0}.panel summary{font-weight:650;font-size:14px;cursor:pointer}.panel p{margin-top:12px}.exclusions article{padding:20px 0;border-top:1px solid var(--line);font-size:13px}.exclusions ul{padding-left:20px;font-size:12px;line-height:1.6;color:var(--muted)}.two-column{display:grid;grid-template-columns:1.1fr 1fr;gap:22px}.fields{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:15px}.fields label{min-width:0}.manual-list article{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--line);padding:15px 0}.manual-list strong,.manual-list small{display:block}.manual-list small{color:var(--muted);margin-top:5px}.library-list{max-height:560px;overflow:auto;margin:18px 0}.library-list button{width:100%;text-align:left;display:flex;justify-content:space-between;gap:10px;background:transparent;border-bottom:1px solid var(--line);border-radius:0;font-size:12px;line-height:1.5}.library-list span{font-size:10px;color:var(--muted);font-weight:400;flex-shrink:0}.rules{max-width:800px;margin:auto}.rules>p{max-width:600px}.source{padding:20px 0;border-bottom:1px solid var(--line);overflow-wrap:anywhere}.source>strong{display:block;font-size:13px;margin-bottom:15px}.source p{font-size:12px}.consent{border:1px solid #a8b97688;background:#2b3025;padding:20px;border-radius:12px;margin-top:25px;overflow-wrap:anywhere}.notice{padding:14px 18px;border:1px solid #819b6366;color:#dbeabb;background:#293023;margin:15px 0;border-radius:10px;font-size:13px;display:flex;justify-content:space-between;align-items:center;gap:15px}.notice button{padding:0 5px;background:transparent;font-size:20px}.notice.error{border-color:#bb7880;color:#ffe1e6;background:#3b2430}.winner{padding:35px;border-radius:14px;border:1px solid #9faf6f;background:radial-gradient(ellipse at top right,#91a45333,transparent 60%),#272b20;margin:30px 0}.winner h2{font-size:38px;color:#e5efc8;letter-spacing:-1px}.winner p{font-size:12px}.achievement{padding:20px 0;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:15px;align-items:center}.achievement small{display:block;color:var(--muted);margin-top:7px}.launch-screen{position:relative;min-height:620px;padding:65px 0 40px;overflow:hidden}.launch-screen h1{font-size:clamp(44px,7vw,80px);line-height:1.02;letter-spacing:-3px;max-width:700px;position:relative;z-index:1}.launch-screen em{font-style:normal;color:var(--accent)}.launch-screen>p{max-width:420px;font-size:15px}.launch-detail{border-left:2px solid var(--accent);padding:10px 22px;margin:35px 0;max-width:460px;position:relative;z-index:1}.launch-detail strong{font-size:15px}.launch-detail p{font-size:12px;margin:8px 0}.launch-dice{position:absolute;right:40px;top:90px;width:280px;height:360px;background:linear-gradient(145deg,#775baf,#313058);border:1px solid #9c82c2;border-radius:40px;transform:rotate(13deg);display:grid;place-items:center;box-shadow:25px 25px 0 #211e35}.launch-dice span:first-child{font-size:260px;color:#c6b3e6;line-height:1}.launch-dice span:last-child{position:absolute;right:-25px;top:-35px;font-size:90px;color:var(--accent);transform:rotate(-13deg)}.trust-line{color:#9398a7;font-size:10px;letter-spacing:1px}footer{display:flex;justify-content:space-between;color:#84879a;font-size:9px;letter-spacing:1px;padding:35px 0;border-top:1px solid var(--line);margin-top:50px}.skip{position:absolute;left:15px;top:-50px;background:var(--accent);color:#111;padding:12px;z-index:10}.skip:focus{top:10px}hr{border:0;border-top:1px solid var(--line);margin:30px 0}.rolling span{display:inline-block;animation:turn 1s infinite}@keyframes turn{to{transform:rotate(360deg)}}@media(max-width:850px){.app-shell{padding:0 20px}.game-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.two-column{grid-template-columns:1fr}.launch-dice{right:-100px;opacity:.25}.intro{align-items:flex-start}.section-heading{align-items:flex-start}.launch-screen{min-height:600px}.live{max-width:150px;text-align:right}}@media(max-width:540px){.app-shell{padding:0 14px}.topbar{min-height:76px}.wordmark{font-size:15px}.brand-dice{width:34px;height:34px;font-size:30px}.live{font-size:9px;max-width:115px}.intro{display:block;margin-top:30px}.room-meta{margin-top:17px}.mode-strip{gap:7px}.mode-strip button{padding:14px 10px}.mode-strip span{font-size:10px}.section-heading{display:block}.section-heading button{margin-top:15px;width:100%}.game-grid{grid-template-columns:1fr}.cover{height:240px}.panel{padding:20px}.fields{gap:10px}.tabs button{font-size:12px;padding:12px 10px}.roster{gap:7px}.person{padding:9px}.launch-screen h1{font-size:51px;letter-spacing:-2px}.launch-screen{padding-top:55px}.launch-dice{right:-160px}.achievement{display:block}.achievement button{margin-top:12px}footer{font-size:8px;gap:15px}}@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
/* Compact controls keep the current task in view inside Discord. */
.topbar{min-height:58px}.brand-dice{width:30px;height:30px;font-size:27px}.wordmark{font-size:15px}.intro{margin-top:18px;gap:12px}.intro h1{font-size:26px;margin-bottom:5px}.intro .eyebrow,.intro>div>p{display:none}.roster{gap:7px;margin:12px 0}.person{padding:7px 10px}.tabs{position:sticky;top:0;z-index:2;background:#171923;padding:5px 0;margin-bottom:14px}.tabs button{padding:10px 12px}.mode-strip button{padding:10px 12px}.mode-strip strong{margin-bottom:2px}.price-note,.room-options,.future-pricing{font-size:12px;color:var(--muted);margin:10px 0}.price-note summary,.room-options summary,.future-pricing summary{cursor:pointer}.section-heading{margin:17px 0 13px}.section-heading h2{font-size:19px}.cover{height:120px}.cover-fallback>span{font-size:32px}.cover-fallback strong{font-size:18px}.cover-fallback small{display:none}.card-body{padding:12px}.card-body h3{font-size:16px}.cost{margin:6px 0}.tiny-avatars{margin:7px 0}.card-actions{margin-top:9px}.empty{padding:25px 20px}.empty-symbol{font-size:30px;margin-bottom:10px}.empty p{margin-bottom:15px}.panel{padding:18px;margin:10px 0}label{margin:11px 0;gap:6px;font-size:12px}input,select{padding:9px 11px}.fields{gap:12px}.manual-list{max-height:180px;overflow:auto}.manual-list article{padding:9px 0}.library-list{max-height:350px;margin:12px 0}.library-list button{display:block}.library-list span{display:block}.pagination{display:flex;align-items:center;justify-content:center;gap:12px;font-size:11px;margin:12px 0}.veto-bar{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin:15px 0;font-size:11px}.exclusions article{padding:12px 0}.winner{padding:20px;margin:15px 0}.winner h2{font-size:27px}.finish{margin:15px auto}footer{padding:12px 0;margin-top:18px}.modal-backdrop{position:fixed;inset:0;background:#090b16b8;z-index:20;display:grid;place-items:center;padding:20px}.host-confirm{width:min(460px,100%);background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:24px}.host-confirm button{min-height:44px}.host-confirm{color:inherit}.host-confirm::backdrop{background:#090b16b8}.notice{padding:9px 12px;margin:10px 0}.room-meta{flex-wrap:wrap}.game-grid{gap:12px}@media(max-width:600px){.game-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.section-heading{display:flex}.section-heading button{width:auto;margin-top:0}.room-meta{margin-top:6px}.intro{margin-top:12px}.cover{height:95px}.cover-tag{font-size:7px;left:8px;bottom:8px}.card-body{padding:10px}.card-actions{flex-wrap:wrap;gap:5px}.topbar{min-height:52px}.panel{padding:15px}.fields{gap:9px}.intro h1{font-size:24px}.person{padding:6px 8px}.avatar{width:26px;height:26px}.tabs button{padding:9px 10px}}@media(max-width:380px){.game-grid{grid-template-columns:1fr}.fields{grid-template-columns:1fr}.room-meta .pill{font-size:9px}.section-heading{display:block}.section-heading button{width:100%;margin-top:10px}}
.avatar{overflow:hidden;flex:none;aspect-ratio:1}.avatar img,.tiny-avatars img{width:100%;height:100%;object-fit:cover;border-radius:50%;display:block}.tiny-avatars span{display:grid;place-items:center;width:26px;height:26px;min-width:26px;aspect-ratio:1;padding:0;overflow:hidden;flex:none}.game-title{padding:0;border-radius:3px;background:transparent;color:inherit;font:inherit;line-height:inherit;text-align:left;text-decoration:underline;text-decoration-color:#777485;text-underline-offset:4px}.game-title:hover{text-decoration-color:var(--accent)}
</style>

