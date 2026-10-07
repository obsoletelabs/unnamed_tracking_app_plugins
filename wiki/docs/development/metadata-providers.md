# Metadata provider plugins

The official metadata plugins consume the host's additive **Plugin API v1.1.1**
contract. The host owns discovery, ranking, deduplication, sessions, health UI,
enrichment scheduling and persistence. Plugins own external API communication,
authentication, parsing, provider mapping, pacing and retries.

## Install and configure

Build/install packages through the normal plugin workflow, review permissions
and enable them. Open the host's **Settings → Metadata/API** provider panel or
the plugin settings dialog. Administrators may configure system fields; each
user may configure their own fields. User overrides win over system fallback
for fields whose declaration permits both scopes. Values are encrypted and
write-only in UI/API reads; clearing a user value restores the system fallback.

The host reuses its original compact source tiles, colored badges, key buttons
and expandable forms. Tiles are discovered from enabled plugins and show live
health classifications. Administrators choose **System default**; **My account**
edits only their user scope. Existing account-import connections remain below
the metadata tiles. See the [host screenshots and workflow](https://github.com/obsoletelabs/unnamed_tracking_app_2/blob/feat/metadata-provider-orchestration/wiki/docs/integrations/metadata.md).

Old host metadata integration keys are not automatically transferred. Enter them
in the matching provider plugin's configuration. Account library/achievement
sync credentials remain in their existing account integration settings.

| Package | Media / capabilities | Credentials |
| --- | --- | --- |
| `metadata-steam` | Game search, metadata, selected CDN artwork | None for metadata; account sync uses separate Steam settings |
| `metadata-steamgriddb` | Selected game artwork | SteamGridDB API key, system/user |
| `metadata-gog` | Game catalogue search and metadata | None |
| `metadata-igdb` | Game search, metadata and artwork | Twitch client ID/secret, system |
| `metadata-giantbomb` | Game search, metadata and artwork | GiantBomb API key, system/user |
| `metadata-retroachievements` | Game search and metadata | RetroAchievements username/key, user |
| `metadata-screenscraper` | Selected game artwork | Developer ID/password and account ID/password |
| `metadata-hltb` | Game completion time | None; unofficial API can reject requests |
| `metadata-tvmaze` | TV search, metadata, seasons, episodes, airing and artwork | None |
| `metadata-anilist` | Anime search, metadata, episodes, airing, franchise/recommendations and artwork | None |
| `metadata-anizip` | Anime cross-IDs and primary episode details | None |
| `metadata-jikan` | MAL anime search, metadata, episodes, airing and artwork | None; Jikan availability/rate limits apply |
| `metadata-kitsu` | Anime search, metadata, episodes, airing and artwork | None |
| `metadata-tmdb` | Movie/TV/anime search, metadata, episodes, collections, recommendations and artwork | Optional TMDB API key, system/user |
| `metadata-omdb` | Movie/TV/anime IMDb search, metadata and poster | OMDb API key, system/user |
| `metadata-tvdb` | TV search, metadata, franchise relationships and poster | TVDB API key, system/user; optional subscriber PIN, user |

## Public wire contract

`tools/schemas/metadata-registration-v1.schema.json`, `metadata-request-v1.schema.json`
and `metadata-response-v1.schema.json` are exported from the host's public models.
The companion contains no host source imports. `sdk/metadata_provider.py` uses
the existing gateway protocol and can be packaged with ordinary official plugins.

Declare a namespaced provider ID, independent action IDs, media types, identifier
namespace and required configuration. Optional metadata resources identify
entity, episodes, airing, relations and recommendations. Episode sources declare
primary/fallback authority. Declare the required `metadata_providers.*` leaves,
network and storage permissions in the manifest and the matching action capabilities
in the UI document. Call `register(DECLARATION)` after startup.

Actions receive authenticated request context and, for enrichment, a canonical
candidate. Search returns lightweight candidates without metadata or artwork.
Metadata returns partial canonical fields, with scores on 0–100. Media returns
asset references only when the host selects an entity. Cross-ID lookup uses a
unique exact title and known year when an ID is missing; ambiguous titles remain
unresolved. Never manipulate library rows or watched state from a provider plugin.

Use `metadata_page` for large collections. It respects the runtime's 64 KiB
action-output limit, counts actual entries and preserves summaries across variable
page sizes. The host detects repeated cursors and applies one overall deadline.

`ProviderHttp` owns atomic provider pacing through `plugin.storage`. Interactive
requests wait at most one second for a slot and do not retry. Background work can
wait/retry within its own 24-second budget, honoring numeric or HTTP-date Retry-After
values mediated by the host. A background worker does not reserve future slots
ahead of interactive work. Provider failures retain classifications without
remote error bodies, URLs or secrets.

## Validation and limitations

Contract/unit fixtures verify mapping and failure behavior; they do not establish
live service success. `tools/check_metadata_live.py` uses actual installed `.utp`
packages on a disposable host. Its optional SteamGridDB flow checks absent,
invalid, user-scoped and system-scoped credentials. Credentials come from local
environment/configuration and are never printed. Keep preview output under ignored
`.validation/`; publication still uses the official signer and immutable histories.

Live development validation on 2026-10-07 observed:

- Steam, SteamGridDB and TVmaze: search/enrichment and selected artwork succeeded.
  SteamGridDB rejected invalid credentials and validated both credential scopes.
- AniList and Kitsu: progressive search, selected metadata and artwork succeeded.
  AniList rate limiting and Jikan timeouts did not discard other providers' data.
- AniZip: the corrected `anilist_id` mapping endpoint passed real health checks.
- GOG: public catalogue/metadata responses were reachable in direct live probes.
  The catalogue returns fuzzy matches; the host's title filter keeps unrelated
  products out of the displayed Portal 2 matches. The installed-package harness
  does not establish authenticated GOG account-import success.
- HowLongToBeat: its unofficial endpoint rejected requests; reported unavailable.
- IGDB, GiantBomb, RetroAchievements, ScreenScraper, OMDb and TVDB: missing
  credentials were verified; live authenticated success remains unverified.
- TMDB: signup/live authentication was intentionally skipped. Its optional
  implementation has contract coverage; no live success is claimed.

The host's eight-second interactive and 25-second background deadlines can return
partial long episode/franchise inventories under rate limiting. Prior fields remain
available, and later background refresh can fill missing fields.
