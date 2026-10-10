# Official plugins

[Epic Games Library](epic-games/README.md), **0.0.1**, connects a personal Epic
account and imports games/playtime through Plugin API 1.1.3. It preserves manual
library state and resumes bounded inventory/catalogue/import steps after failure.
Its packaged sandbox UI uses narrow navigation, storage, network and game-write
permissions. Branch CI supplies an unsigned preview; signed publication uses
the existing protected official pipeline.

[Extended Session Manager](extended-session-manager/README.md) enhances the
built-in personal and administrator session pages with GeoIP, network, anomaly
details and maps. It retains the ID `example.self-service-session-manager` so
existing installations can update. New releases use the scoped official signer;
historical demo-signed archives keep their original identity. The successor-key
trust and expiry requirements are tracked in
[host issue #7](https://github.com/obsoletelabs/unnamed_tracking_app_2/issues/7).

[Unnamed Tracking PWA](pwa/README.md) is maintained official functionality,
currently **0.0.1**, published through the scoped official signing identity.

[Jellyfin Media Sync](jellyfin-media-sync/README.md) starts at **0.0.1**, an official
preview under test with the separate ID `official.jellyfin-media-sync`. Its release
uses that same reviewed official signing pipeline. Version 1.0 will follow
validation and an explicit release decision.

The separate [Jellyfin demo](../examples/jellyfin-media-sync/README.md) remains an
example. Official plugins are maintained user-facing features. Demonstrations
remain in `examples/` and use separate demo signing identities. Valid signature
and official status are distinct; every plugin still requires its declared
permissions, with no sandbox exemptions or special host APIs.

[Collector's Archive](collectors-archive/README.md), **0.0.1**, preserves Cards,
Sets and Bounties after their removal from the host. It is an unreleased source
preview, available in branch CI's `unsigned-dist` artifact. Its native pages use
the public host UI runtime, and its personal import preserves legacy identifiers,
artwork, prestige links, evidence, journals and point history without deleting
server originals. A signed production release requires the official publisher.

[Discord Bot Notifications](discord-bot-notifications/README.md) is an unreleased
paired preview for private direct messages. It registers a generic plugin-owned
PRIVATE notification destination and performs Discord API delivery inside the
plugin. The host supplies routing and privacy policy; it does not own Discord
credentials or a Discord-specific transport.
