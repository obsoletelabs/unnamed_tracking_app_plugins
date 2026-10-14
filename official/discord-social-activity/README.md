# Game Night Discord Activity (preview)

An independently packaged Discord Activity for Unnamed Tracking App. It uses
Plugin API **v1.1.12** public-app infrastructure and the updated Discord Bot
Notifications identity adapter. It imports no host modules and has no database,
network sockets, bot token or OAuth client secret of its own.

## What works

- Verified Discord OAuth identity and live Activity instance membership.
- Shared persisted rooms, individual inputs, host transfer and reconnect recovery.
- User-approved connections to independent HTTPS tracking instances.
- Guest games and explicit self-reported multiplayer compatibility annotations.
- Strict, balanced and discovery modes, personal hard platform/genre/time rules.
- A shortlist of up to three games, one vote per participant, personal vetoes,
  selection and rerolls. Ties use a random draw among tied eligible games.
- Imported cover artwork where available, readable fallbacks, eligibility reasons.
- Public Steam cover fallback and title details with Steam/own tracking-page links.
- Verified Discord avatars and circular participant thumbnails.
- Saved group-play presets from connected libraries, with manual confirmation for
  unknown multiplayer counts; entry-specific genres reset after adding a game.
- Room-host matching settings, personal undo-veto controls, and spectators for
  participants with no games. Host transfer requires a separate confirmation.
- Native Discord invitation controls and optional verified DM/group-DM rooms.
- Automatic owned multiplayer contributions; one participant can supply missing
  player limits for the room directly from the exclusion list. Saved/manual
  limits also supply missing counts without repeated entry. Personal access,
  known platform-specific limits, rules and crossplay consent remain separate.
- Own-account tracking changes and explicitly local achievement reports when the
  participant grants the appropriate write scopes.
- Responsive layout, keyboard controls and reduced-motion support.

Current purchase offers are unavailable in the host. Price, budget and discount
filters are paused. Strict still requires everyone to own the game; balanced and
discovery allow a participant to consider an unowned game only with their own
purchase consent and owned-only rule disabled. Unknown prices are labeled and
never reported as free or within budget. No action authorizes a purchase.
Wishlist entries are never treated as ownership. Compatibility annotations are
self-reported, not provider verification; title matches need edition confirmation.

## Configure

1. Install both preview packages using the host's explicit unsigned-development
   package review. No trusted signed release is currently published for this plugin.
2. Grant the Activity `integrations.public_app` and `plugin.storage` globally.
   Grant the bot `integrations.identity_provider` explicitly, alongside its existing
   permissions. Neither grant is implied by `api.full`.
3. Configure the bot token/server using the bot administrator page. Add the same
   application's ID and OAuth client secret under **Discord Activity sign-in**.
   Existing notification destinations retain their configuration and proof.
4. Enable integration access on the Activity host. Enable guests if desired.
5. Configure Discord Activity URL mappings:
   `/` → `HOST/api/public-apps/official.discord-social-activity/app/`
   and `/api` → `HOST/api`. Enable Activities for the tested platforms. Keep a
   redirect URI configured for the Embedded App SDK OAuth flow.
6. On each source instance, enable integrations and approve the Activity host's
   exact HTTPS origin. Participants sign in on that source and approve their own
   scopes/expiry; write scopes default to unchecked.
7. Launch from the Discord App Launcher in the bot's configured server. Connect
   an instance or add manual games, confirm compatibility, then shortlist and vote.

For private-channel rooms, explicitly enable **Allow Activities in DMs and group
DMs** in the bot's Activity settings. Discord must also allow user installation
and private-channel launch for your application/testers. The adapter validates
Discord's `pc` location and connected user list; enabling DMs does not allow
Activities in other guilds. See the complete
[operator/player setup guide](../../wiki/docs/examples/discord-game-night.md).

Public sessions are separate external principals, not host accounts. Credentials
for connected instances remain encrypted in the host broker, and never enter this
plugin or the browser. Removing a source connection forgets its broker credential;
revoke it in the source instance's Connected apps to invalidate the grant there too.

Users may explicitly choose **Until revoked** instead of timed access. Remembered
links belong to the verified Discord identity and are reused on reconnect while
their credentials remain valid. The first connection always needs consent; a
Discord username or display name alone never links an application account.

For an older source without the delegation API, the Activity operator can enable
**Allow unsafe legacy API-key connections** in Integration access. The participant
must select legacy mode and acknowledge the broad key. The host encrypts it and
uses only fixed identity/library GET requests. Legacy connections cannot write
tracking or achievements and do not expose imported artwork; public Steam cover
fallback still applies. Disconnect the connection and revoke the key on the old
instance when finished. Legacy clients do not require upgrading the old instance.

Source administrators may optionally allow consent requests from any HTTPS origin.
Library connections request only identity and game reads by default. Participants
can choose optional progress access before connecting; the source still presents
tracking and achievement writes unchecked for explicit approval. Unused history,
media and custom-list capabilities are not requested by Game Night.
This registers requesters without individual origin setup; it never approves a
user's data. Individually disabled origins stay blocked. Central Activity hosting
can connect independent source instances through this same broker and consent
boundary. Operator approval, personal rules and personal vetoes remain distinct.

Game titles use normalized case, spacing and punctuation by default. Steam IDs
are optional; edition ambiguity still requires human confirmation. Platform
aliases and empty-library spectators can be configured by the current room host.
Unknown player limits need one room confirmation; they are never invented.
Store metadata is informational and cannot override personal rules.

## Build and test

```sh
npm install
npm run build:activity
npm run check:activity
python -m pytest tests/test_discord_activity.py tests/test_discord_activity_identity.py
python tools/build_packages.py
```

Source is under `ui/`; compiled assets are under `frontend/` and included in the
validated `.utp`. The builder preserves historical published packages. Test the
actual preview package against the matching host branch before deployment.

The Activity stores bounded room inputs/votes using public storage CAS. Rooms
expire under the host retention policy; its background worker clears expired
rooms. There is no persistent Discord Gateway connection, custom chat command or
notification delivery in the Activity. Those remain the bot's responsibilities.
