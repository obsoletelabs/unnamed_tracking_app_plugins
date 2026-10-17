# MyAnimeList Metadata Provider

Uses public Plugin API v1.1.1. Install its .utp through Plugin Manager and grant its declared permissions. Jikan's public API needs no credentials, so the provider declares no configuration.

Search returns identities independently of metadata and artwork. Metadata is requested for the current top three; artwork starts after selection. Background refresh uses the same metadata contract for episodes and airing with its own bounded retry policy.

Build unsigned previews with `python tools/build_packages.py`. Preview installation requires explicit consent; signed releases use the existing publication workflow.
