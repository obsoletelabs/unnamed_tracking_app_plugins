# Discord Bot Notifications

Private direct-message notifications using a dedicated Discord bot.

**Host requirement:** this preview uses the generic plugin-owned notification provider contract in Plugin API 1.1.6. Deploy the paired host destination-verification change (PR #71) before installing this plugin. Older hosts reject provider registration and the plugin will repeatedly restart.

## Per-account destinations

Use **Settings → Administration → Notifications** to configure **Discord account DM** with a dedicated bot token and server ID. These credentials belong to the plugin and are revision-bound separately from legacy native configuration. The token is write-only. This uses the provider's declared server fields, with no Discord-specific host settings.

In **Settings → Account → Notifications**, add one **Discord account DM** destination per exact Discord username in that server. Enrollment resolves a single Discord ID and remains PRIVATE; ordinary notifications work immediately, without a code. Changing the username or server configuration invalidates host proof and queued work. Merely renaming the Discord account does not change its saved target.

For SECURE delivery, separately approve the critical `notification_providers.sensitive` permission, then request and enter the host-generated code from that account's DM. Only the host confirms proof for that exact destination revision. Codes expire after ten minutes. Recovery delivery additionally requires the destination's explicit **Allow recovery messages** choice. This grant exposes verification codes and approved security/recovery content to this plugin; review it accordingly. Without the grant normal PRIVATE delivery still works.

Each attempt sends to exactly one account; missing, retired, changed or differently owned mappings fail instead of broadcasting. Temporary Discord/gateway failures are reported to the host retry queue. Oversized messages fail rather than truncating recovery secrets. The core owns all delivery state.

### Existing bot migration

The existing grouped **Discord Bot DM** provider and its native dashboard/account linking remain working as PRIVATE compatibility routes. Plugin link verification is not host SECURE proof. Existing links and tokens are retained and never automatically promoted or copied to the new provider. Configure the new per-account provider, explicitly activate and verify each desired account, then disable the old grouped provider to avoid receiving duplicate ordinary notices. Removing one new destination erases its plugin target into an opaque revision tombstone and leaves other accounts and legacy links intact. Reinstall requires fresh activation/configuration; old credentials cannot be reclaimed.

## Legacy setup

1. Create a dedicated bot application in the Discord Developer Portal. Keep its bot token private; never paste it into a chat or commit it to a repository.
2. Invite the bot to the Discord server that contains the users who want to link their accounts. Enable the **Server Members Intent** if Discord requires it for member search.
3. In **Settings → Administration → Discord Bot Notifications**, enter the bot token and that server's numeric ID. The plugin validates the credentials against Discord before saving. The token is write-only and is never returned by the status action.
4. Users can **Link for PRIVATE notifications** by username without a verification code. Optional legacy profile verification does not promote notification trust. The legacy grouped route remains PRIVATE.
5. For individual routes, configure **Discord account DM** under **Settings → Administration → Notifications**, then add one destination per username under **Settings → Account → Notifications**. Normal PRIVATE notifications work immediately. For SECURE/recovery delivery, complete the host-issued destination challenge, opt into recovery and grant the provider its separate high-risk permission.
6. Choose each destination under **Notification types**. The host applies trust, preferences, administrative policy and disclosure before handing approved content to the plugin.

Username enrollment resolves one exact member of the configured Discord server and stores its stable Discord ID. Zero or ambiguous matches are refused. Users may need to permit server-member DMs. Discord profile/account verification is not required for ordinary PRIVATE notifications.

## PUBLIC server channels

Administrators load the **Allowed notification channels and server users** directory in Discord bot administration. Text and announcement channels can be allowed individually. The member picker searches the loaded page; **Load more server users** retrieves the next page of up to 1,000 members. Administrators can link a selected Discord member to their own signed-in app account as PRIVATE; this does not change another app user's identity or prove access.

Configure the separate **Discord server channel** provider in **Administration → Notifications** using its bot token and server ID. Users then choose an allowed default channel in their Discord account settings and add a **Discord server channel** destination in **Account → Notifications**. Leave the destination's channel-ID field blank to use that selected default, or enter an allowed channel ID explicitly. Each destination retains its own channel: changing the default cannot reroute existing work. Per-type notification settings select which messages go to it.

Channels are always **PUBLIC**, including private Discord channels. Core PUBLIC release projections and generic tests may be delivered; private/security/recovery content cannot. Explicit richer media consent retains the host's field allowlist and never promotes trust. The plugin checks the administrator allowlist, server membership and text/announcement type at enrollment and each send. Removing a channel from the allowlist stops future deliveries immediately. The bot requires **View Channel** and **Send Messages**, including category/channel overrides. **Embed Links** enables rich notification cards. When Discord rejects a card with HTTP 403, the plugin tries the same approved content once as text in the same channel/DM, with automatic URL embeds and mentions disabled. Broader access failures still fail; rate limits, network errors and ambiguous server failures use the core retry policy without a second immediate send. Directory listing does not prove it can post.

Tokens remain write-only plugin storage; generic server configurations are separately revision-bound. Administrative channel/member discovery is not exposed to ordinary users; users see only allowed channels. Installations, user ownership, destination revisions and server revisions must match for every delivery. Deleted destinations retain target-free tombstones.

## Bot dashboard

The administrator page deliberately exposes as much non-secret Discord information as the bot can safely discover. It can show:

- bot username, global display name, Discord ID, avatar and verification state;
- a generated OAuth2 bot invite URL and the intents the plugin expects (`GUILDS` and `GUILD_MEMBERS`);
- Discord API health and measured plugin-side request time;
- server name, ID, icon, description, owner ID and vanity code;
- approximate total and online member counts;
- server verification level, boost tier/count, preferred locale and NSFW level;
- enabled Discord server features;
- AFK, system, rules and public-update channel IDs and related server settings when Discord exposes them;
- explicit-content filtering, default notification behavior, MFA level and widget state;
- the bot's server nickname, join time, pending state and assigned roles;
- the permissions calculated from the bot's effective server roles;
- the last successful user test DM and last successful notification delivery time for each linked account.

The dashboard never displays the bot token. Refreshing the dashboard re-queries Discord rather than relying on stale cached identity data.

## Security and behavior

- The bot token is stored in this plugin's private storage namespace, never returned to the frontend after saving, and can be cleared by an administrator. Treat the plugin's data volume as sensitive and back it up accordingly.
- Link codes expire after ten minutes and failed verification attempts are capped. The verification code is stored only as a hash.
- The legacy grouped provider remains PRIVATE and cannot receive verification/security/recovery content. The per-account provider becomes SECURE only after independent host proof and requires a separate high-risk handoff grant.
- The plugin sends DMs only to accounts linked by the same host account; PRIVATE enrollment does not require verification. Each account can be unlinked independently, and notifications are sent to every account that remains linked. It disables Discord mention parsing in sent messages.
- The bot needs only the server access required by this integration. Member discovery uses the Discord member list and therefore may require the Server Members Intent. Keep the token dedicated to this integration and rotate it if exposed.
- Discord API calls use the plugin's declared `network.outbound` capability through the bounded host gateway. The plugin owns the external Discord network calls and credentials.
- Notification bodies are bounded before sending and the bot does not interpret notification text as mentions.
- User links are scoped by the authenticated host user ID inside plugin storage; the host does not receive the Discord credential or own the Discord account mapping.

The plugin declares its PRIVATE account and PUBLIC channel providers, fields, features, privacy and configuration/delivery actions through the existing generic provider API. The host does not need Discord-specific credential handling or delivery code.

The native link page now supports **Link for PRIVATE notifications** without receiving a code. Optional legacy profile proof does not upgrade destination trust. For recovery use the separate **Discord account DM** destination in Account → Notifications, host verification, recovery opt-in and the high-risk delivery grant. The administrator must configure its revision-bound server fields in Admin → Notifications. DMs use native rich cards; Discord does not render email HTML. This independent preview keeps its existing publisher and update policy.

All DMs use native rich cards with spaced paragraphs, an emphasized verification code and a short **here** action link. HTTP delivery does not show the bot as online: persistent Discord Gateway presence is deferred until the host exposes an approved WebSocket transport with connection/heartbeat/reconnect lifecycle. Direct sockets are unavailable in the isolated plugin runtime.


Text fallback uses spaced paragraphs and named links (View notification, Reset
your password, Accept invitation or Verify destination). It reserves room for a
complete action rather than truncating its URL. Local previews keep their local
URL; deployed notifications use the host-resolved notification URL. An action too
long to fit is omitted whole with a prompt to open the app.
