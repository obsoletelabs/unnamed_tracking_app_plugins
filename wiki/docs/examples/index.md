# Working examples

Demonstrations live under `examples/`; official features live under `official/`.
Jellyfin has separate demo and official preview identities. Every maintained source has a
manifest, implementation, README, tests and support in the existing builder.
The catalogue is generated from their actual packages, not this table.

| Source | Scale / useful behavior | Tests |
| --- | --- | --- |
| [UI/API](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/ui-api) | Small reference: declarative page, setting, library action | examples, smoke, packaged worker, reference lifecycle |
| [Playtime Report](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/playtime-report) | Small demo: calculate/store user report | real plugins, smoke, package, reference lifecycle |
| [Recently Played Notifier](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/recently-played-notifier) | Small demo: library + notification | real plugins, smoke, reference lifecycle |
| [Metadata Curator](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/metadata-curator) | Small demo: setting + search + normalized state | real plugins, smoke, reference lifecycle |
| [Discord Delivery Provider](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/discord-delivery-provider) | Reference: core-coordinated delivery + write-only secret | domain plugins, smoke, package |
| [UI Playground](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/ui-playground) | Demo: iframe Vue pages/bridge; pinned CDN teaching limitation | examples, smoke, no secret echo |
| [Help Button](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/help-button) | Showcase: contributions, dialogs, overlays and native cleanup | help, native frontend, canonical packages |
| [Jellyfin Media Sync](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/jellyfin-media-sync) | Master server, approved user mapping, native episode completion and Watch Now | Jellyfin, native frontend, full host lifecycle/browser |
| [Scoped Document Viewer](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/scoped-document-viewer) | Feature demo: scoped sandboxed content reader | domain, document package, real browser, parity |
| [Session Manager](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/self-service-session-manager) | Privileged feature demo: own/admin session Settings/maps | session, routes, native UI, package |
| [Home Widgets](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/home-widgets) | Account-persisted widget choices/options, responsive layouts and embedded media demo | theme/widget contracts, signed host lifecycle and account isolation |
| [Shortcut Playground](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/shortcut-playground) | v1.1.x dynamic shortcuts and intentional Ctrl/Cmd+K conflict | native lifecycle, host permission enforcement, remapping and account isolation |
| [Blue Hour Palettes](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/tree/main/examples/theme-palettes) | Optional semantic light/dark palettes with personal copies and separate permission | package/source, palette grants, signed native/iframe acceptance and withdrawal |

Use the smallest example that teaches your requirement. Every real demo's README
describes configuration, grants and current host limitations. Screenshots for
document/native components are collected in [assets](../assets/screenshots/index.md);
browser-enabled host acceptance produces authenticated Plugin Manager evidence.

Old lifecycle/events/advanced source stubs are retired. Their original `.utp`
files and generated release histories remain immutable and downloadable. See
the [audit](../history/ecosystem-audit.md), not duplicate legacy source directories.
