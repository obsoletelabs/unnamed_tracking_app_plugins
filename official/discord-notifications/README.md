# Discord Notifications

Maintained official provider for owner-specific Discord webhooks using the generic
plugin-owned notification provider contract. This is a new identity,
`official.discord-notifications`; legacy example credentials/consent are never moved.

Install the package and grant `notification_providers.register` and
`notification_providers.deliver`, plus the plugin's declared storage, outbound
network and settings capabilities. Enable the plugin, then open the plugin-owned
Discord Webhook settings page under **Account → Settings**. Enter a webhook URL,
save it, and use **Send test** to verify the destination.

The webhook URL is stored in the plugin's private storage namespace and is never
sent to the host notification coordinator. The host stores only generic routing
metadata and an opaque configuration reference. The plugin performs the Discord
HTTP request itself through its declared `network.outbound` capability.

Each webhook is PUBLIC. The notification coordinator therefore supplies only the
public projection allowed for that destination. Explicit destination preferences
do not promote trust or permit account details, watch history, ratings, security
messages or recovery tokens.

The plugin validates HTTPS Discord webhook URLs, disables Discord mention parsing,
keeps credentials out of notification payloads and maps bounded network failures
to the host's normal retry/result contract. The provider advertises its destination
kind, privacy level, capabilities and settings UI; no Discord-specific transport or
credential handling is required in the host application.

Test: `python -m pytest tests/test_discord_notifications.py -q`.
Build: `python tools/build_packages.py` (isolated preview packages).
Actual host/runtime lifecycle acceptance is separate from unit tests. No external
webhook credentials are bundled. This source is initially an explicit catalogue
preview pending paired acceptance and reviewed signed promotion.
