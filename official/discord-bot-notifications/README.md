# Discord Bot Notifications

Private direct-message notifications using a dedicated Discord bot.

## Setup

1. Create a dedicated bot application in the Discord Developer Portal. Keep its bot token private; never paste it into a chat or commit it to a repository.
2. Invite the bot to the Discord server that contains the users who want to link their accounts. Enable the **Server Members Intent** if Discord requires it for member search.
3. In **Settings → Administration → Discord Bot Notifications**, enter the bot token and that server's numeric ID. The plugin validates the credentials against Discord before saving. The token is write-only and is never returned by the status action.
4. Each user opens **Settings → Account → Discord Bot Notifications**, enters their exact Discord username, and requests a link code. The bot DMs a short-lived code to the matching server member. Enter the code to prove control of that Discord account.
5. Enable the plugin-owned **Discord Bot DM** destination in the host's notification routing settings. The host's normal notification dispatcher applies user preferences and privacy policy before invoking the plugin.

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
- the last successful user test DM and last successful notification delivery time for the current linked account.

The dashboard never displays the bot token. Refreshing the dashboard re-queries Discord rather than relying on stale cached identity data.

## Security and behavior

- The bot token is stored in this plugin's private storage namespace, never returned to the frontend after saving, and can be cleared by an administrator. Treat the plugin's data volume as sensitive and back it up accordingly.
- Link codes expire after ten minutes and failed verification attempts are capped. The verification code is stored only as a hash.
- Notifications are private destinations, not secure/recovery destinations. Secure security alerts and recovery messages are intentionally not routed through this provider.
- The plugin sends only to the Discord account verified by the same host account. It disables Discord mention parsing in sent messages.
- The bot needs only the server access required by this integration. Member discovery uses the Discord member list and therefore may require the Server Members Intent. Keep the token dedicated to this integration and rotate it if exposed.
- Discord API calls use the plugin's declared `network.outbound` capability through the bounded host gateway. The plugin owns the external Discord network calls and credentials.
- Notification bodies are bounded before sending and the bot does not interpret notification text as mentions.
- User links are scoped by the authenticated host user ID inside plugin storage; the host does not receive the Discord credential or own the Discord account mapping.

The plugin advertises its generic private notification provider, destination kind, privacy level, storage/network requirements and UI actions itself. The host does not need Discord-specific credential handling or delivery code.
