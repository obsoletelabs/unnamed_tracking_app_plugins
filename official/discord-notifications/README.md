# Discord Webhook Notifications

Maintained Discord webhook delivery through the generic Plugin API 1.1.5 provider contract.
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

## Migration and testing

This release requires explicit enrollment. Historical protected webhook secrets
are not transferred to plugin storage, and automatic update is disabled for this
transition. Old packages remain immutable and notification history is retained.

Standalone source and generated-package tests cover field validation, installation
separation, revision races, secret removal, malformed URLs, approved content and
HTTP failure handling. No production Discord credential is required by those tests.
