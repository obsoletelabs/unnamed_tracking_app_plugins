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
4. Each user opens **Settings → Account → Discord Bot Notifications**, enters their exact Discord username, and requests a link code. The bot DMs a short-lived code to the matching server member. Enter the code to prove control of that Discord account. Repeat these steps to link additional Discord accounts; each account is verified separately, and private notifications routed to this provider are sent to every linked account.
5. Open **Settings → Preferences → Notifications → Your providers**. Under **Discord Bot Notifications**, add the **Discord Bot DM** destination, then enable the provider for your account.
6. Under **Notification types**, expand the types you want and enable routing to the new Discord destination. The host's normal dispatcher still applies its privacy policy and your per-type preferences before invoking the plugin.

A username is only used to locate one exact match inside the configured server. The plugin refuses zero or ambiguous matches. The linked Discord user ID is saved after verification, so later username changes do not silently redirect notifications. The bot must be able to create DMs with linked users; users may need to allow direct messages from server members.

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
- The plugin sends only to Discord accounts individually verified and linked by the same host account. Each account can be unlinked independently, and notifications are sent to every account that remains linked. It disables Discord mention parsing in sent messages.
- The bot needs only the server access required by this integration. Member discovery uses the Discord member list and therefore may require the Server Members Intent. Keep the token dedicated to this integration and rotate it if exposed.
- Discord API calls use the plugin's declared `network.outbound` capability through the bounded host gateway. The plugin owns the external Discord network calls and credentials.
- Notification bodies are bounded before sending and the bot does not interpret notification text as mentions.
- User links are scoped by the authenticated host user ID inside plugin storage; the host does not receive the Discord credential or own the Discord account mapping.

The plugin advertises its generic private notification provider, destination kind, privacy level, storage/network requirements and UI actions itself. The host does not need Discord-specific credential handling or delivery code.
