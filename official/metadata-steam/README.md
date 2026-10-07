# Steam Metadata Provider

Uses Plugin API v1.1.1 provider registration and permission-checked actions. The host manages sessions, ranking, canonical fields and selection. The plugin talks to Steam through `network.request`.

Steam storefront search and app details require no API key. Steam library import and achievements retain their separate account configuration in the host.

Search returns lightweight identities. Metadata is a separate operation. Artwork is requested only for a selected entity. API authentication failures, outages and rate limits produce safe typed failures.

Build with `python tools/build_packages.py` and test with `python -m pytest`. Local preview packages are unsigned and require explicit development installation consent. Published signed packages are produced by the repository's existing release workflow; no private key is included.
