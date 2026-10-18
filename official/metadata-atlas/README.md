# Atlas Metadata Provider

Search and enrich games from an [Atlas](https://github.com/obsoletelabs/unnamed_tracking_metadata) server: one canonical record merged from Steam, IGDB, RAWG and curated sources, with the provider identifiers Atlas has linked to it. Uses public Plugin API v1.1.1 (search, metadata, media, health).

## Configure

Install its .utp through Plugin Manager and grant the declared permissions, then set, in the host-rendered provider settings (system or personal scope):

| Setting | Meaning |
| --- | --- |
| **Atlas server URL** | Root of your Atlas node, e.g. `https://atlas.example.org` or `http://192.168.1.20:8000`. A path prefix is allowed (`https://host/atlas`). No credentials, query or fragment. |
| **Atlas API token** | A token with the `read` scope (`atlas token --name tracker --scopes read`). Write-only and encrypted by the host. |

Use your own server, a LAN mirror or a public one; the plugin contacts only the configured URL. Egress is governed by the `network.outbound` grant, so the administrator chooses the destination.

## Behaviour

- **Search** returns lightweight candidates with Atlas ID plus linked store identifiers (`steam`, `igdb`, ...) so the host can cross-link them.
- **Metadata** is fetched by Atlas ID. A candidate without one is looked up by its other provider identifiers or exact title and year, and is only accepted on a certain match (`crosswalk` or `exact`). Anything uncertain returns no metadata rather than a guess.
- **Media** lists only artwork Atlas has already downloaded and verified, as public `<server>/media/<hash>` links. The app downloads them itself under its public-network rules, so artwork is only fetched when the Atlas server is publicly reachable.
- Merged Atlas IDs keep working: a record merged into another is returned under its current ID.
- Failures are typed (`not_configured`, `invalid_configuration` for a bad URL or rejected token, `rate_limited`, `unavailable`); remote bodies and the token are never retained.
- Personal data is never sent. Only titles, years and provider IDs go to the server.

Build development packages with `python tools/build_packages.py`. Unsigned previews require explicit installation consent; signed publication uses the existing release workflow.
