 # Discord Bot Notifications

Private direct-message notifications using a dedicated Discord bot.

## Setup

1. Create a dedicated bot application in the Discord Developer Portal. Keep its bot token private; never paste it into a chat or commit it to a repository.
2. Invite the bot to the Discord server that contains the users who want to link their accounts. Enable the **Server Members Intent** if Discord requires it for member search.
3. In **Settings → Administration → Discord Bot Notifications**, enter the bot token and that server's numeric ID. The plugin validates both before saving. The token is write-only in the UI and is never returned by its status action.
4. Each user opens **Settings → Account → Discord Bot Notifications**, enters their exact Discord username, and requests a link code. The bot DMs a short-lived code to the matching server member. Enter the code to prove control of that Discord account.
5. Enable **Discord Bot DM** in the host's notification routing settings. The host's normal notification dispatcher applies user preferences and privacy policy before the plugin sends anything.

A username is only used to locate one exact match inside the configured server. The plugin refuses zero or ambiguous matches. The linked Discord user ID is saved after verification, so later username changes do not silently redirect notifications. The bot must be able to create DMs with linked users; users may need to allow direct messages from server members.

## Security and behavior

- The bot token is stored in this plugin's private storage namespace, never returned to the frontend after saving, and can be cleared by an administrator. Treat the plugin's data volume as sensitive and back it up accordingly.
- Link codes expire after ten minutes and link initiation is rate-limited per host account. Failed codes do not create a link.
- Notifications are private destinations, not secure/recovery destinations. Secure security alerts and recovery messages are intentionally not routed through this provider.
- The plugin sends only to the Discord account verified by the same host account. It disables Discord mention parsing in sent messages.
- The bot needs only the server access needed to find members and create/send DMs. Keep its token dedicated to this integration and rotate it if exposed.
- Discord API calls use the host's bounded outbound gateway; redirects are refused and network egress must allow discord.com.

This provider requires the paired host support for the discord_bot_dm transport. Installing the package without that host contract will not register a working DM destination.
