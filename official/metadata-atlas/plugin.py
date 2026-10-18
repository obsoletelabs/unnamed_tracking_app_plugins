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


def patch(game):
    out = {
        "title": game.get("title"), "release_date": game.get("release_date"),
        "description": game.get("description"), "developer": game.get("developer"),
        "publisher": game.get("publisher"), "series": game.get("series"),
        "tags": game.get("tags") or [], "features": game.get("features") or [],
        "platforms": game.get("platforms") or [],
        "provider_ids": candidate(game)["provider_ids"],
    }
    if game.get("release_date"):
        out["year"] = int(game["release_date"][:4])
    return {key: value for key, value in out.items() if value not in (None, "", [])}


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
