# Discord Bot Notifications

PRIVATE direct messages, optional host-verified SECURE recovery, and PUBLIC channel notifications using a dedicated Discord bot.

**Host requirement:** use a host with Plugin API 1.1.11 for the current generic provider and native configuration UI. Older hosts may reject registration or lack the required settings integrations. The updated source requires the independent destination-status read permission; transport and secrets remain plugin-owned.

## Per-account destinations

Use **Settings → Administration → Notifications** to configure **Discord account DM** with a dedicated bot token and server ID. These credentials belong to the plugin and are revision-bound separately from legacy native configuration. The token is write-only. This uses the provider's declared server fields, with no Discord-specific host settings.

In **Settings → Account → Notifications**, add one **Discord account DM** destination per exact Discord username in that server. Enrollment resolves a single Discord ID and remains PRIVATE; ordinary notifications work immediately, without a code. Changing the username or server configuration invalidates host proof and queued work. Merely renaming the Discord account does not change its saved target.

For SECURE delivery, separately approve the critical `notification_providers.sensitive` permission, then request and enter the host-generated code from that account's DM. Only the host confirms proof for that exact destination revision. Codes expire after ten minutes. Recovery delivery additionally requires the destination's explicit **Allow recovery messages** choice. This grant exposes verification codes and approved security/recovery content to this plugin; review it accordingly. Without the grant normal PRIVATE delivery still works.

Each attempt sends to exactly one account; missing, retired, changed or differently owned mappings fail instead of broadcasting. Temporary Discord/gateway failures are reported to the host retry queue. Oversized messages fail rather than truncating recovery secrets. The core owns all delivery state.

### Existing bot migration

The first maintained release is prepared for the existing signed catalogue publication workflow under **Unnamed Tracking Official**, with automatic updates disabled. Until publication succeeds and the bot appears in the catalogue, source/unsigned previews are not a published release.

If you installed an independently signed preview, uninstall it and freshly install the official package. Reconfigure credentials, activate destinations and repeat host verification and recovery consent. Do not use replacement installation to retain proof across signing identities. Existing preview credentials or verification must not be silently transferred to the official publisher.

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
- The plugin sends DMs only to accounts linked by the same host account; PRIVATE enrollment does not require verification. Each per-account destination delivers only to its configured account. The legacy grouped provider broadcasts only to its remaining compatibility profile links. It disables Discord mention parsing in sent messages.
- The bot needs only the server access required by this integration. Member discovery uses the Discord member list and therefore may require the Server Members Intent. Keep the token dedicated to this integration and rotate it if exposed.
- Discord API calls use the plugin's declared `network.outbound` capability through the bounded host gateway. The plugin owns the external Discord network calls and credentials.
- Notification bodies are bounded before sending and the bot does not interpret notification text as mentions.
- User links are scoped by the authenticated host user ID inside plugin storage; the host does not receive the Discord credential or own the Discord account mapping.

The plugin declares its PRIVATE account and PUBLIC channel providers, fields, features, privacy and configuration/delivery actions through the existing generic provider API. The host does not need Discord-specific credential handling or delivery code.

The native link page now supports **Link for PRIVATE notifications** without receiving a code. Optional legacy profile proof does not upgrade destination trust. For recovery use the separate **Discord account DM** destination in Account → Notifications, host verification, recovery opt-in and the high-risk delivery grant. The administrator must configure its revision-bound server fields in Admin → Notifications. DMs use native rich cards; Discord does not render email HTML. The maintained release uses the registered **Unnamed Tracking Official** publisher and keeps **manual updates**.

All DMs use native rich cards with spaced paragraphs, an emphasized verification code and a short **here** action link. HTTP delivery does not show the bot as online: persistent Discord Gateway presence is deferred until the host exposes an approved WebSocket transport with connection/heartbeat/reconnect lifecycle. Direct sockets are unavailable in the isolated plugin runtime.


Text fallback uses spaced paragraphs and named links (View notification, Reset
your password, Accept invitation or Verify destination). It reserves room for a
complete action rather than truncating its URL. Local previews keep their local
URL; deployed notifications use the host-resolved notification URL. An action too
long to fit is omitted whole with a prompt to open the app.

## Trust, recovery and searchable selection

The account page reads actual destination trust from the host through the separate
`notification_destinations.read` permission (API 1.1.11). It shows PRIVATE and SECURE
destinations separately, with current password-reset routing readiness. Existing profile
links are collapsed as **Compatibility profile links**; their optional profile verification
does not make a notification destination SECURE. No destination addresses, host secrets,
challenge codes, notification content or other providers' destinations are returned by
this read API. Local Discord labels are added only from this plugin's matching actor and
destination revision. Failed refresh clears old trust badges.

Use **Verify DM and configure recovery** for the exact host destination. Complete its
host challenge, then enable **Allow recovery messages**. The separate sensitive-content
permission must be granted, and the administrator must enable the password-reset plugin.
The card explains missing proof, opt-in, permission, availability or routing. A verified
destination can still have recovery disabled. PUBLIC channels never receive reset secrets.
Host verification and recovery controls retain authority; this plugin cannot promote trust.

Administrators can use **Find bot servers**, search by name or ID, select the bot's server
or enter an ID manually. Discovery uses the entered write-only token or the stored native
compatibility token, and returns at most 100 servers per request, with explicit pagination.
It uses Discord's [Get Current User Guilds](https://docs.discord.com/developers/resources/user#get-current-user-guilds)
endpoint; large bot sharding is outside this single-server integration. Selecting a server
does not save until **Validate and save**. This section configures the directory and legacy
grouped provider; links open the separately revision-bound DM/channel provider settings in
Administration → Notifications. Changing those server settings retires previous destinations
and requires explicit reconfiguration and new host proof.

Channel allowlists, allowed user channels, members and destination/account cards support
name/ID search. Member search covers loaded pages; **Load more server users** expands the
directory. Bulk matching channel selection preserves hidden choices until an explicit save.
User channels remain administrator-allowed PUBLIC targets. Each existing destination keeps
its own target; selecting a default channel only affects future enrollment.

Version 0.1.1 is a manual update requiring API 1.1.11 and permission review. Earlier packages
and signing history remain immutable. Install/update the host before updating the bot.
