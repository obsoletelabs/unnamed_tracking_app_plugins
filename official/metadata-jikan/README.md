# MyAnimeList Metadata Provider

Uses public Plugin API v1.1.1. Install its .utp through Plugin Manager and grant its declared permissions. Credentials are configured in the host-rendered provider settings and use the declared system or personal scope. Saved secrets stay hidden.

Search returns identities independently of metadata and artwork. Metadata is requested for the current top three; artwork starts after selection. Background refresh uses the same metadata contract for episodes, airing and relationships with its own bounded retry policy.

Build unsigned previews with `python tools/build_packages.py`. Preview installation requires explicit consent; signed releases use the existing publication workflow.
