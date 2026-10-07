# SteamGridDB Metadata Provider

Uses Plugin API v1.1.1 provider registration and permission-checked actions. The host manages sessions, ranking, canonical fields and selection. The plugin talks to SteamGridDB through `network.request`.

Configure an API key in the host's provider settings. System credentials can be supplied by an administrator; a user's own key takes precedence. Credentials are encrypted and write-only in the UI. Search and metadata work without this optional artwork provider.

Search returns lightweight identities. Metadata is a separate operation. Artwork is requested only for a selected entity. API authentication failures, outages and rate limits produce safe typed failures.

Build with `python tools/build_packages.py` and test with `python -m pytest`. Local preview packages are unsigned and require explicit development installation consent. Published signed packages are produced by the repository's existing release workflow; no private key is included.
