"""TMDB movie/TV/anime capabilities with separate search, metadata and media requests."""

import time
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderHttp, exact_identity, external_id, metadata_page, operation, provider_values, register

PROVIDER_ID = "official.metadata-tmdb.tmdb"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "TMDB", "identifier_namespace": "tmdb",
    "media_types": ["movie", "tv_show", "anime"],
    "metadata_resources": ["entity", "episodes", "airing", "relations", "recommendations"],
    "operations": {"search": "search", "metadata": "metadata", "media": "media", "health": "health"},
    "configuration": [{"key": "api_key", "label": "TMDB API key", "scope": "both"}],
}


def get(values, path, **params):
    credentials = provider_values(PROVIDER_ID, ("api_key",))
    return ProviderHttp(values["request"], "tmdb", min_gap=0.1)(
        "https://api.themoviedb.org/3" + path + "?" + urlencode({**params, "api_key": credentials["api_key"]}),
    )


def domain(work):
    return "movie" if work["media_type"] == "movie" else "tv"


def identity(item, work):
    release = item.get("release_date") or item.get("first_air_date")
    return {"provider": PROVIDER_ID, "external_id": str(item["id"]),
            "title": item.get("title") or item.get("name"), "media_type": work["media_type"],
            "year": int(release[:4]) if release else None, "provider_ids": {"tmdb": str(item["id"])}}


@operation
def search(values):
    work = values["request"]
    result = get(values, "/search/" + domain(work), query=work["query"], page=int(work.get("cursor") or 1))
    # Anime is an explicit TV genre; generic TV results must not pollute anime searches.
    items = result.get("results", [])
    if work["media_type"] == "anime":
        items = [item for item in items if 16 in item.get("genre_ids", [])]
    return {"candidates": [identity(item, work) for item in items[:work.get("limit", 20)]
                           if item.get("title") or item.get("name")],
            "next_cursor": str(result.get("page", 1) + 1) if result.get("page", 1) < result.get("total_pages", 1) else None}


def resolve(values):
    candidate = values["candidate"]
    identity_id = external_id(candidate, PROVIDER_ID, "tmdb")
    if identity_id:
        return identity_id
    result = get(values, "/search/" + domain(values["request"]), query=candidate["title"])
    found = exact_identity([identity(item, values["request"]) for item in result.get("results", [])], candidate)
    return found["external_id"] if found else None


@operation
def metadata(values):
    work = values["request"]
    identity_id = resolve(values)
    if identity_id is None:
        return {}
    kind = domain(work)
    resource = work.get("resource", "entity")
    if resource == "recommendations":
        result = get(values, f"/{kind}/{identity_id}/recommendations", page=int(work.get("cursor") or 1))
        return {"metadata": {"relations": [{"candidate": identity(item, work), "relation": "Recommended",
                                           "group": "recommendation",
                                           "poster_url": "https://image.tmdb.org/t/p/w342" + item["poster_path"] if item.get("poster_path") else None}
                                          for item in result.get("results", [])[:work.get("limit", 20)]]},
                "next_cursor": str(result.get("page", 1) + 1) if result.get("page", 1) < result.get("total_pages", 1) else None}
    if resource == "relations":
        item = get(values, f"/{kind}/{identity_id}")
        collection = item.get("belongs_to_collection") if kind == "movie" else None
        if not collection:
            return {"metadata": {"relations": []}}
        group = get(values, f"/collection/{collection['id']}")
        return metadata_page(work, "relations", [
            {"candidate": identity(entry, work), "relation": "Collection",
             "poster_url": "https://image.tmdb.org/t/p/w342" + entry["poster_path"] if entry.get("poster_path") else None}
            for entry in sorted(group.get("parts", []), key=lambda entry: entry.get("release_date") or "9999")
            if str(entry["id"]) != identity_id
        ], {"relation_group": group.get("name")})
    if work.get("resource") == "episodes" and kind == "tv":
        season = work.get("season_number") or 1
        data = get(values, f"/tv/{identity_id}/season/{season}")
        return metadata_page(work, "episodes", [
            {"episode_number": item["episode_number"], "season_number": item.get("season_number"),
             "title": item.get("name"), "description": item.get("overview"), "air_date": item.get("air_date") or None,
             "runtime_minutes": item.get("runtime"),
             "still_url": "https://image.tmdb.org/t/p/w780" + item["still_path"] if item.get("still_path") else None}
            for item in data.get("episodes", [])
        ], {"provider_ids": {"tmdb": identity_id}})
    item = get(values, f"/{kind}/{identity_id}", append_to_response="credits,external_ids")
    release = item.get("release_date") or item.get("first_air_date")
    crew = (item.get("credits") or {}).get("crew") or []
    ids = {"tmdb": identity_id}
    external = item.get("external_ids") or {}
    if item.get("imdb_id") or external.get("imdb_id"):
        ids["imdb"] = item.get("imdb_id") or external["imdb_id"]
    if external.get("tvdb_id"):
        ids["tvdb"] = str(external["tvdb_id"])
    return {"metadata": {
        "title": item.get("title") or item.get("name"), "release_date": release or None,
        "description": item.get("overview"), "runtime_minutes": item.get("runtime"),
        "episode_runtime_minutes": next(iter(item.get("episode_run_time", [])), None),
        "director": next((entry["name"] for entry in crew if entry.get("job") == "Director"), None),
        "writer": next((entry["name"] for entry in crew if entry.get("job") in {"Writer", "Screenplay"}), None),
        "creators": [entry["name"] for entry in item.get("created_by", [])],
        "studios": [entry["name"] for entry in item.get("production_companies", [])],
        "genres": [entry["name"] for entry in item.get("genres", [])],
        "countries": [entry["name"] for entry in item.get("production_countries", [])],
        "languages": [entry.get("english_name") or entry["name"] for entry in item.get("spoken_languages", [])],
        "scores": {"tmdb": item["vote_average"] * 10} if item.get("vote_average") is not None else {},
        "provider_ids": ids, "links": [{"label": "TMDB", "url": f"https://www.themoviedb.org/{kind}/{identity_id}"}],
        "seasons": [{"season_number": season["season_number"], "title": season.get("name"),
                     "episode_count": season.get("episode_count"), "air_date": season.get("air_date") or None}
                    for season in item.get("seasons", [])][:100],
        "airing": {"status": "completed" if item.get("status") == "Ended" else "ongoing" if item.get("in_production") else "unknown",
                   "is_airing": item.get("in_production"), "total_episodes": item.get("number_of_episodes")}
        if kind == "tv" else None,
    }}


@operation
def media(values):
    identity_id = resolve(values)
    if identity_id is None:
        return {}
    result = get(values, f"/{domain(values['request'])}/{identity_id}/images")
    return {"assets": [{"kind": kind, "url": "https://image.tmdb.org/t/p/original" + entry["file_path"],
                        "width": entry.get("width") or None, "height": entry.get("height") or None}
                       for category, kind in (("posters", "poster"), ("backdrops", "banner"), ("logos", "logo"))
                       for entry in result.get(category, [])[:60] if entry.get("file_path")][:200]}


def health(values):
    result = search({"request": {**values["request"], "query": "The Matrix", "limit": 1, "media_type": "movie"}})
    return result if result.get("failure") else {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
