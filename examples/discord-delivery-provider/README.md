# External Discord Delivery Provider

This reference plugin registers `example.discord-delivery-provider.discord` with the core notification coordinator. Core decides which notifications are eligible, checks the user's provider setting and active grant, owns deduplication and retry state, and sends a minimized delivery DTO to the plugin's `deliver` action.

Permissions requested:

- `notification_providers.register`: register and remove the namespaced provider.
- `notification_providers.deliver`: receive eligible minimized delivery work.
- `plugin.storage`: store a Discord webhook in private, write-only runtime storage.

The runtime accepts only HTTPS `discord.com` or `discordapp.com` `/api/webhooks/` destinations and limits message content to Discord's 2,000-character bound. The plugin never logs or returns the webhook. Set `PLUGIN_RUNTIME_DISCORD_EGRESS=true` to enable the narrowly scoped runtime sender; outbound access remains disabled otherwise.

At startup, provider registration waits for the host gateway using bounded
backoff when the public gateway reports a temporary `unavailable` error. This
supports runtime-first startup and an app-only callback configuration without
requiring a manual retry. Permission, invalid-request and other permanent errors
are not retried. Registration is idempotent; this wait does not deliver messages.

Build all packages with `python tools/build_packages.py`. Local builds are intentionally unsigned and require the host's untrusted-package confirmation; release CI supplies the reviewed signing identity. Requires the host Plugin API v1 notification-provider capabilities introduced by the Phase 2 plugin-manager work.

## Notification contract 1.1.2

This example is a legacy shared PUBLIC webhook provider. The host supplies only approved public release facts, checks user opt-in and installation grants, and owns delivery attempts/retries. Generic UI actions cannot authorize Discord transport; invoking the delivery renderer manually does not send a message. Session anomalies and other security/private content are not sent to this destination. Per-webhook richer sharing consent and protected per-user configuration require the later destination API.

The legacy webhook is write-only through the host settings UI, but is readable by the plugin in its own storage. It is not a host-protected credential vault or proof of exclusive user control. No endpoint is promoted to SECURE by configuring a webhook. Keep real secrets out of renderer results and error text.
