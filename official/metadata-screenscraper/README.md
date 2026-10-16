# ScreenScraper Metadata Provider

Uses public Plugin API v1.1.1. Install its .utp through Plugin Manager and grant the declared permissions. Configure credentials in the host-rendered provider settings, selecting the plugin-declared system or personal scope. Secrets are write-only and encrypted by the host.

ScreenScraper provides artwork only: it is requested after selection and matched to the selected entity by exact normalized title. Interactive operations are bounded without retries; background operations may pace and retry within their separate budget. Missing credentials, invalid credentials, rate limits and outages return typed failures.

Build development packages with `python tools/build_packages.py`. Unsigned previews require explicit installation consent; the existing release workflow produces signed publication packages.
