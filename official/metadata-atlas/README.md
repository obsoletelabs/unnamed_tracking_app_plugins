# Atlas Metadata Provider

Search and enrich games, anime, movies and TV shows from an [Atlas](https://github.com/obsoletelabs/unnamed_tracking_metadata) server. Atlas can merge Steam, IGDB, TMDB and curated sources into one canonical record, while the app combines Atlas with its other providers using the user's provider ranking. Uses public Plugin API v1.1.15 (search, metadata, media, health).

## Configure

Install its .utp through Plugin Manager and grant the declared permissions, then set, in the host-rendered provider settings (system or personal scope):

| Setting | Meaning |
| --- | --- |
| **Atlas server URL** | Root of your Atlas node, e.g. `https://atlas.example.org` or `http://192.168.1.20:8000`. A path prefix is allowed (`https://host/atlas`). No credentials, query or fragment. |
| **Atlas API token** | A token with the `read` scope (`atlas token --name tracker --scopes read`). Write-only and encrypted by the host. |

Use your own server, a LAN mirror or a public one; the plugin contacts only the configured URL. Egress is governed by the `network.outbound` grant, so the administrator chooses the destination.

## Behaviour

- **Search** is filtered to the requested media type and returns lightweight candidates with Atlas ID plus linked identifiers (`steam`, `igdb`, `tmdb`, ...) so the host can cross-link them.
- **Metadata** is fetched by Atlas ID. A candidate without one is looked up by its other provider identifiers or exact title and year, and is only accepted on a certain match (`crosswalk` or `exact`). Anything uncertain returns no metadata rather than a guess.
- **Metadata fields** are mapped by media type to the app's provider-neutral contract. Games include developer, publisher, series, features, platforms and multiplayer facts. Movies include director, studio, runtime, writers and production countries. Anime includes studios, format, episode count and themes. TV shows include creators, episode count and episode runtime; networks and season count remain visible as provider custom details. All types can include release date, description, tags, genres, languages, alternate titles, age rating, links, scores, provider IDs and bounded Atlas custom values. Invalid or missing fields are omitted. Provider ordering in the app determines the default winner when sources disagree; fields no other provider supplies still complement the result.
- **Achievements**: the plugin declares the `achievements` metadata resource and returns Atlas's game achievement definitions (name, description, hidden flag, global percentage, HTTPS icon, stable ID), never anyone's progress. Non-game records never request the game achievement endpoint. The host stores definitions without changing progress and can match linked source IDs.
- **Media** lists only artwork Atlas has already downloaded and verified, as public `<server>/media/<hash>` links. For movies, anime and TV, Atlas key art is exposed as a poster. The app downloads it itself under its public-network rules, so artwork is only fetched when the Atlas server is publicly reachable.
- Merged Atlas IDs keep working: a record merged into another is returned under its current ID.
- Failures are typed (`not_configured`, `invalid_configuration` for a bad URL or rejected token, `rate_limited`, `unavailable`); remote bodies and the token are never retained.
- Personal data is never sent. Only titles, years and provider IDs go to the server.

Build development packages with `python tools/build_packages.py`. Unsigned previews require explicit installation consent; signed publication uses the existing release workflow.
