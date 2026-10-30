# RetroAchievements Metadata Provider

Uses public Plugin API v1.1.1. Install its .utp through Plugin Manager and grant the declared permissions. Configure credentials in the host-rendered provider settings, selecting the plugin-declared system or personal scope. Secrets are write-only and encrypted by the host.

Search returns lightweight identities. Metadata is requested separately for the current top three. Interactive operations are bounded without retries; background operations may pace and retry within their separate budget. Missing credentials, invalid credentials, rate limits and outages return typed failures.

Build development packages with `python tools/build_packages.py`. Unsigned previews require explicit installation consent; the existing release workflow produces signed publication packages.

## Console coverage

Search walks one RetroAchievements game system per cursor page. `CONSOLE_NAMES` in
`plugin.py` lists 80 systems (including Game Boy Advance, Dreamcast and PSP, which
were previously missing); the original eleven keep their order so saved cursors still
resume. Events and hubs are excluded. A stale or out-of-range cursor ends the search
instead of wrapping, and results lacking a `ConsoleName` use the mapped system name.
Systems RetroAchievements adds later need an entry in the table.
