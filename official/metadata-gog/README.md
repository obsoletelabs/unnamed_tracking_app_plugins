# GOG Metadata Provider

Uses public Plugin API v1.1.1. Install its .utp through Plugin Manager and grant the declared permissions. GOG's public catalogue needs no credentials, so the provider declares no configuration.

Search returns lightweight identities. Metadata is requested separately for the current top three. Interactive operations are bounded without retries; background operations may pace and retry within their separate budget. Rate limits and outages return typed failures.

Build development packages with `python tools/build_packages.py`. Unsigned previews require explicit installation consent; the existing release workflow produces signed publication packages.
