# Discord Webhook Notifications

Maintained Discord webhook delivery through the generic provider contract (rich delivery needs Plugin API 1.1.14).
Deploy the paired host provider/settings change before installing this release.

## Setup

1. Install the plugin and approve its provider, storage and outbound-network grants.
2. Open the host's notification settings and enable Discord Webhook for your account.
3. Add a destination using the generated configuration form. Enter a label and an
   ordinary Discord text-channel webhook URL. Multiple destinations are supported.
4. Choose notification types and use **Send test notification** to exercise the
   configured credentials through the core dispatcher.

Webhooks remain PUBLIC. Default media announcements contain public release facts.
Each destination revision can separately opt into the richer followed-media
projection; this does not permit account identifiers, watch history, ratings or
security content. Critical urgency is not supported by this provider.

## Configuration and delivery

The plugin declares its fields, destination kind and features; the host renders
them with shared controls. The plugin validates and stores its own webhook tokens
under opaque installation/destination IDs and revisions. Credentials are never
returned to forms, action results, lifecycle records or host notification rows.
Editing retains an omitted saved URL, invalidates pending work and clears previous
media consent. Removal deletes the URL and retains only a revision tombstone.

Only exact HTTPS discord.com/discordapp.com webhook paths are accepted, without
userinfo, alternate ports, query parameters or fragments. The plugin uses its own
bounded network grant and renders only core-approved content with mentions disabled.
Empty successful Discord responses are accepted; rate limits and server/network
failures are retryable, while invalid/revoked webhook responses fail permanently.
Core owns delivery state, leases, retries, preferences and routing checks.

## Rich batches and editable story messages (host Plugin API 1.1.14)

The webhook declares presentation capabilities (`rich_embeds`, edits, up to 8 digest items,
4 images, link actions) and an `edit` action. Canonical deliveries are laid out by
`sdk/discord_embeds.py` within Discord's hard limits: at most 10 embeds and 6,000 characters
per message, 256/4,096 characters for title/description and 25 fields of 256/1,024 characters.
Truncation is deterministic, a cut description always ends with the live story link, mentions
never notify (`allowed_mentions` parses nothing) and only http(s) links survive. Webhooks cannot
carry buttons, so actions are listed as links in the embed.

Messages are created with `?wait=true`; Discord's message id is returned to the host as the opaque
reference. A later story revision edits that message (`PATCH .../messages/{id}`) while the host
decides it is eligible; a deleted message (HTTP 404/403) is reported as `gone` and the host
sends a selective follow-up instead. Webhook messages cannot be replied to, so follow-ups are
standalone. A reference only works with the webhook that created it. The host-owned test message
keeps the minimal payload. Rate limits (429) and 5xx/network errors are retryable; other errors
fail without blocking other providers. Release order: host (Plugin API 1.1.14) first, then this
package.

## Migration and testing

This release requires explicit enrollment. Historical protected webhook secrets
are not transferred to plugin storage, and automatic update is disabled for this
transition. Old packages remain immutable and notification history is retained.

Standalone source and generated-package tests cover field validation, installation
separation, revision races, secret removal, malformed URLs, approved content and
HTTP failure handling. No production Discord credential is required by those tests.
