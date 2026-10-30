# Jellyfin Media Sync â€” official preview

This official preview is under test, with automatic package updates disabled.
The independently installable `official.jellyfin-media-sync` package is
separate from `example.jellyfin-media-sync`, which remains a demonstration.
There is no automatic conversion of the demo's private storage or permission grants.

An administrator adds servers and discovery keys on **Jellyfin servers** directly
under **Administration → Server management** in Settings, tests them, and approves
libraries. Personal connections live at **Account → Your Jellyfin accounts** and
the direct **Media → Jellyfin** sidebar entry. These placements require separate
consent for the administration and account settings areas. Loading and failed
configuration requests show a retry control and the host's access/runtime details;
administrator denial is shown only after a successful role check.
Music, books, Live TV and collections
are excluded. Explicit film/TV/anime mappings win over automatic anime tag/genre
detection. Anime films become a one-episode anime entry; season zero is supported.

On **Jellyfin**, each user connects multiple accounts using a password or Quick
Connect. A password is used once, never persisted. Alternatively, the administrator
can approve a specific remote identity for the shared discovery key. Users can narrow
approved libraries, choose automatic sync and merging, opt into error notifications,
and order accounts for Watch Now. All enabled accounts participate in sync.
Removing a credential retains configuration, item mappings and checkpoints.
Unnumbered episodes retain provider progress and enter review. Assign their real
season/episode numbers or leave them unnumbered; the plugin never fabricates numbers
or marks a partially numbered series complete. Missing runtimes remain unknown.

Sync imports all supported items, including unwatched titles, watched episodes,
position ticks, percentage, play counts and last-played timestamps. Provider IDs
and unique exact title/year matches merge into the user's existing media records.
Ambiguous matches and local watch-state changes enter a review queue. Notes,
ratings and manually locked metadata survive enrichment. Personal ratings are
imported only where absent. Jellyfin supplies descriptions, credits, genres,
studios, countries, languages, tags, dates, codec details, provider identities and
token-free artwork URLs. Year-only dates retain their precision in provider metadata.
Authenticated-only artwork may not display; tokens are never added to image URLs.

Optional **Playback Reporting** imports real individual viewing sessions through
that Jellyfin plugin's read-only user/day API. It requires an installed, active
Playback Reporting plugin and an elevated discovery credential. Choose a bounded
initial lookback (default 30 days, up to 3650). Without it, ordinary Jellyfin cannot
reconstruct earlier sessions from its aggregate counters; the plugin reports this
limitation and never invents past plays or timestamps. No new Jellyfin-side plugin
is required. Sync never changes Jellyfin watched state, ratings, files or media.

One supervised worker processes bounded pages and saves accepted checkpoints.
Host downtime, permission denial and restarts preserve progress. Backoff is bounded
and configurable; authentication/configuration failures wait for correction.
The next automatic run replaces the previous retry schedule, with no overlapping
per-account jobs. Disabling automatic sync stops future schedules; an active run
finishes. Full rescan starts a fresh census. Two successful censuses must miss an
item before its Watch Now link becomes unavailable; personal media is retained.

HTTP and untrusted certificates produce connection-test warnings. HTTPS always
uses host CA trust; there is no certificate-verification bypass. Base URLs may
include a reverse-proxy path; redirects are refused. Secrets stay in private
`plugin.storage` broker namespaces and are never returned by configuration/status
actions. This storage is access-controlled by the runtime, not an encrypted vault;
protect runtime backups accordingly. The plugin has no host database, filesystem,
environment or secret access. Native UI keeps the existing privileged permission
and requires normal user grants. Optional notification denial does not stop sync. With the opt-in, each account has one
notification story (Plugin API 1.1.14): a sync problem opens it, a different problem revises it and a
successful sync resolves it, with a link to the accounts page; hosts or grants without story support
receive the earlier single message.

Target: the current `plugin-manager` public API and Jellyfin 12.1.0. Manifest ranges
remain `^1.0.0`; compatibility detection is intentionally deferred. Provider-neutral
media enrichment and bounded JSON POST are host API additions, available equally
to all plugins. No plugin-specific host hook or trust bypass is used.

Build a validated preview with `python tools/build_packages.py`. Packages and
catalogue previews land under `.validation/`; published historical packages remain
immutable. The 0.0.1 preview is published through the reviewed official signing
identity; automatic updates remain disabled during validation. Unsigned local packages must
use the host's normal untrusted-package approval flow. Test signing keys are for
disposable integration tests only and never confer production trust.


Requires Plugin API v1.1.17 for declared page activation. The native bundle loads
when a contributed page is opened, rather than during unrelated library navigation.
Status polls read compact state every five seconds while syncing and every thirty
seconds while idle. Hidden pages pause requests; full configuration reloads when
review counts or completed syncs change, preserving unsaved preferences.

## Library changes during a scan

If items are added or removed while a scan is paginating, Jellyfin's total no
longer matches the saved cursor. The plugin classifies this as `library_changed`,
discards the stale cursor and restarts with a fresh generation on the next retry,
so no manual Rescan is needed. Repeated restarts back off (30 s doubling to one
hour) and are counted in `scan_restarts`, which resets after a completed scan.
Server outages and authentication failures keep their own bounded retry policy.
