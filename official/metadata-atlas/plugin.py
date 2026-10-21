"""Atlas metadata provider: merged, cross-provider game records from a self-hosted Atlas node."""

import re
import time
from urllib.parse import quote, urlencode, urlsplit

from sdk.metadata_provider import ProviderFailure, ProviderHttp, external_id, operation, provider_values, register

PROVIDER_ID = "official.metadata-atlas.atlas"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "Atlas", "identifier_namespace": "atlas",
    "media_types": ["game"],
    "operations": {"search": "search", "metadata": "metadata", "media": "media", "health": "health"},
    "configuration": [
        {"key": "base_url", "label": "Atlas server URL", "scope": "both", "secret": False},
        {"key": "api_token", "label": "Atlas API token (read scope)", "scope": "both"},
    ],
}
ASSET_KINDS = {"key_art", "banner", "logo", "icon", "screenshot", "hero", "poster"}
ATLAS_ID = re.compile(r"^atlas:[0-9a-z]{26}$")
# Only methods that identify a game with certainty are used to fill in a missing Atlas ID.
CONFIDENT_MATCHES = {"crosswalk", "exact"}


def base_url(values):
    """The configured server root. Only a plain http(s) origin plus optional path prefix is accepted."""
    raw = (values.get("base_url") or "").strip().rstrip("/")
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password \
            or parts.query or parts.fragment:
        raise ProviderFailure("invalid_configuration")
    return raw


def call(values, path, **options):
    credentials = provider_values(PROVIDER_ID, ("base_url", "api_token"))
    data = ProviderHttp(values["request"], "atlas")(
        base_url(credentials) + "/api/v2" + path,
        headers={"Authorization": "Bearer " + credentials["api_token"], "Accept": "application/json"},
        **options,
    )
    if not isinstance(data, dict):
        raise ProviderFailure("invalid_response")
    return data


def candidate(game):
    ids = {"atlas": game["id"], **{key: str(value) for key, value in (game.get("provider_ids") or {}).items()
                                   if key != "atlas"}}
    year = int(game["release_date"][:4]) if game.get("release_date") else None
    return {"provider": PROVIDER_ID, "external_id": game["id"], "title": game["title"],
            "media_type": "game", "provider_ids": ids, "year": year}


@operation
def search(values):
    work = values["request"]
    data = call(values, "/games?" + urlencode({"q": work["query"], "limit": min(int(work.get("limit", 20)), 50)}))
    return {"candidates": [candidate(game) for game in data.get("results", []) if game.get("id") and game.get("title")]}


def texts(value, limit, size):
    """Up to `limit` distinct short strings; anything else from the server is ignored."""
    seen, out = set(), []
    for item in value if isinstance(value, list) else []:
        text = item.strip() if isinstance(item, str) else ""
        if text and len(text) <= size and text.casefold() not in seen:
            seen.add(text.casefold())
            out.append(text)
    return out[:limit]


def group_play(game):
    """Atlas's standard multiplayer fields (players_min, players_max, crossplay), only when valid.

    Atlas allows larger player counts than the host stores (1-32): anything outside is dropped, and
    an inconsistent range is dropped as a whole. Unknown stays unset; nothing is guessed."""
    values = game.get("custom") if isinstance(game.get("custom"), dict) else {}

    def count(key):
        value = values.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 32 else None

    low, high = count("players_min"), count("players_max")
    if low is not None and high is not None and low > high:
        low = high = None
    out = {"players_min": low, "players_max": high}
    if values.get("crossplay") in ("yes", "no", "partial"):
        out["crossplay"] = values["crossplay"]
    return out


def custom_values(game):
    """Atlas's other admin-defined fields as bounded provider custom values (the host contract, API 1.1.15).

    The multiplayer fields travel as their own typed fields, so they are left out here. Keys and values the
    host would reject are dropped one by one rather than failing the whole record."""
    values = game.get("custom") if isinstance(game.get("custom"), dict) else {}
    out = {}
    for key, value in values.items():
        if key in ("players_min", "players_max", "crossplay") or len(out) >= 32:
            continue
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", key):
            continue
        if isinstance(value, (bool, int)) or (isinstance(value, float) and value == value and abs(value) != float("inf")):
            out[key] = value
        elif isinstance(value, str) and 0 < len(value) <= 500:
            out[key] = value
        elif isinstance(value, list) and 0 < len(value) <= 50 and all(
                isinstance(item, str) and 0 < len(item) <= 200 for item in value):
            out[key] = value
    return out


def patch(game):
    title = game.get("title")
    age_rating = game.get("age_rating") if isinstance(game.get("age_rating"), str) else None
    website = game.get("website") if isinstance(game.get("website"), str) else ""
    scores = {name: game[key] for name, key in (("critic", "critic_score"), ("user", "user_score"))
              if isinstance(game.get(key), int) and not isinstance(game.get(key), bool) and 0 <= game[key] <= 100}
    out = {
        "title": title, "release_date": game.get("release_date"),
        "description": game.get("description"), "developer": game.get("developer"),
        "publisher": game.get("publisher"), "series": game.get("series"),
        # Atlas themes are descriptive labels, the closest the host contract has is tags
        "tags": texts((game.get("tags") or []) + (game.get("themes") or []), 128, 128),
        "genres": texts(game.get("genres"), 128, 128), "features": game.get("features") or [],
        "platforms": game.get("platforms") or [], "languages": texts(game.get("languages"), 64, 128),
        "alternate_titles": [name for name in texts(game.get("aliases"), 21, 512) if name != title][:20],
        "age_rating": age_rating.strip()[:64] if age_rating else None,
        "links": [{"label": "Website", "url": website}] if website.startswith("https://") and len(website) <= 500
        and not any(c.isspace() for c in website) else [],
        "scores": scores,
        **group_play(game),
        "custom": custom_values(game),
        "provider_ids": candidate(game)["provider_ids"],
    }
    if game.get("release_date"):
        out["year"] = int(game["release_date"][:4])
    return {key: value for key, value in out.items() if value not in (None, "", [], {})}


def resolve(values, selected):
    """Find the Atlas record for a candidate that only carries other providers' identifiers."""
    item = {key: value for key, value in {
        "title": selected.get("title"),
        "release_date": f"{selected['year']}-01-01" if selected.get("year") else None,
        "provider_ids": {key: value for key, value in (selected.get("provider_ids") or {}).items()
                         if key != "atlas" and re.fullmatch(r"[a-z0-9._-]{1,50}", key)} or None,
    }.items() if value}
    if not item:
        return None
    data = call(values, "/resolve", method="POST", body={"items": [item], "include_view": True})
    result = (data.get("results") or [{}])[0]
    return result.get("game") if result.get("method") in CONFIDENT_MATCHES else None


def locate(values, selected):
    """The Atlas record for a candidate: by Atlas ID when it has one, else by certain identity match."""
    identity = external_id(selected, PROVIDER_ID, "atlas")
    if identity and not ATLAS_ID.match(identity):
        return None
    try:
        return call(values, "/games/" + quote(identity, safe=":")) if identity else resolve(values, selected)
    except ProviderFailure as exc:
        if exc.status == 404:
            return None
        raise


@operation
def metadata(values):
    game = locate(values, values["candidate"])
    return {"metadata": patch(game)} if game and game.get("title") else {}


@operation
def media(values):
    """Artwork Atlas has already downloaded and verified, served from its public /media path."""
    selected = values["candidate"]
    identity = external_id(selected, PROVIDER_ID, "atlas")
    if not identity:
        game = locate(values, selected)
        identity = game and game.get("id")
    if not identity or not ATLAS_ID.match(identity):
        return {"assets": []}
    root = base_url(provider_values(PROVIDER_ID, ("base_url", "api_token")))
    try:
        data = call(values, "/games/" + quote(identity, safe=":") + "/artwork")
    except ProviderFailure as exc:
        if exc.status == 404:
            return {"assets": []}
        raise
    assets = []
    for item in data.get("results", []):
        digest = (item.get("media_url") or "").rsplit("/", 1)[-1]
        if item.get("kind") in ASSET_KINDS and re.fullmatch(r"[0-9a-f]{64}", digest):
            asset = {"kind": item["kind"], "url": f"{root}/media/{digest}", "priority": min(len(assets) * 10, 10000)}
            asset.update({k: item[k] for k in ("width", "height") if isinstance(item.get(k), int) and item[k] > 0})
            assets.append(asset)
    return {"assets": assets[:200]}


def health(values):
    result = search({"request": {**values["request"], "query": "portal", "limit": 1}})
    return result if result.get("failure") else {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
