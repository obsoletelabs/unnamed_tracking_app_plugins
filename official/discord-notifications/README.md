# Discord Notifications

Maintained official provider for owner-specific Discord webhooks, consuming the
host's Plugin API 1.1.2 protected provider contract. This is a new identity,
`official.discord-notifications`; legacy example credentials/consent are never moved.

Install the package and grant `notification_providers.register` and
`notification_providers.deliver`. An administrator must allow existing runtime
Discord egress. Enable the plugin, then open **Account → Notifications → Discord**
in a compatible host to enroll each webhook. Choose notification types and use
**Send test notification**. Configuration belongs to the host, not a plugin page.

Each webhook is PUBLIC. Default release announcements use public facts. Explicit
confirmation on each destination allows its richer followed-media announcement;
that does not promote trust or permit account details, watch history, ratings,
security messages or recovery tokens. Webhook tokens remain host-encrypted and
never enter this plugin's inputs, files or storage. Removing a destination erases
its secret while preserving history. Reinstallation requires new enrollment.

The renderer returns only `title`, `body`, `event_at` and `link` field references.
The host builds a bounded embed, disables mentions, rejects redirects and owns
retries/failure state. Current implementation supports ordinary webhook channels,
not forum thread creation, DMs, attachments, artwork, Critical urgency or raw payloads.
Delivery confirmation uses Discord's `wait=true` option; see the
[official webhook documentation](https://docs.discord.com/developers/resources/webhook).

Test: `python -m pytest tests/test_discord_notifications.py -q`.
Build: `python tools/build_packages.py` (isolated preview packages).
Actual host/runtime lifecycle acceptance is separate from unit tests. No external
webhook credentials are bundled. This source is initially an explicit catalogue
preview pending paired acceptance and reviewed signed promotion.
