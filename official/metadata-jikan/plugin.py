"""Public MyAnimeList data through Jikan; interactive calls never share a blocking retry queue."""

import time
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderHttp, external_id, operation, register

PROVIDER_ID = "official.metadata-jikan.mal"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "MyAnimeList", "identifier_namespace": "mal",
    "media_types": ["anime"],
    "metadata_resources": ["entity", "episodes", "airing"],
    "operations": {"search": "search", "metadata": "metadata", "media": "media", "health": "health"},
}


def get(work, path):
    return ProviderHttp(work, "jikan", min_gap=0.4)("https://api.jikan.moe/v4" + path)


def identity(item):
    return {"provider": PROVIDER_ID, "external_id": str(item["mal_id"]), "title": item["title"],
            "media_type": "anime", "year": item.get("year") or (item.get("aired") or {}).get("prop", {}).get("from", {}).get("year"),
            "provider_ids": {"mal": str(item["mal_id"])},
            "alternate_titles": list(dict.fromkeys(entry["title"] for entry in item.get("titles", []) if entry.get("title")))[:20]}


@operation
def search(values):
    work = values["request"]
    result = get(work, "/anime?" + urlencode({"q": work["query"], "limit": min(25, work.get("limit", 20)),
                                               "page": int(work.get("cursor") or 1)}))
    return {"candidates": [identity(item) for item in result.get("data", []) if item.get("title")],
            "next_cursor": str(int(work.get("cursor") or 1) + 1) if (result.get("pagination") or {}).get("has_next_page") else None}


def entity_id(values):
    return external_id(values["candidate"], PROVIDER_ID, "mal")


@operation
def metadata(values):
    work = values["request"]
    identity_id = entity_id(values)
    if identity_id is None:
        return {}
    if work.get("resource") == "episodes":
        result = get(work, f"/anime/{identity_id}/episodes?" + urlencode({"page": int(work.get("cursor") or 1)}))
        return {"metadata": {"episodes": [
            {"episode_number": item["mal_id"], "title": item.get("title"),
             "air_date": item["aired"][:10] if item.get("aired") else None}
            for item in result.get("data", []) if isinstance(item.get("mal_id"), int)
        ]}, "next_cursor": str(int(work.get("cursor") or 1) + 1) if (result.get("pagination") or {}).get("has_next_page") else None}
    item = get(work, f"/anime/{identity_id}/full").get("data") or {}
    candidate = identity(item)
    airing = {"status": "completed" if item.get("status") == "Finished Airing" else "ongoing" if item.get("airing") else "unknown",
              "is_airing": item.get("airing"), "total_episodes": item.get("episodes"),
              "aired_episodes": item.get("episodes") if item.get("status") == "Finished Airing" else None}
    if work.get("resource") == "airing":
        return {"metadata": {"airing": airing}}
    release = (item.get("aired") or {}).get("from")
    return {"metadata": {
        "title": candidate["title"], "year": candidate["year"], "release_date": release[:10] if release else None,
        "description": item.get("synopsis"), "episode_count": item.get("episodes"),
        "episode_runtime_minutes": int(item["duration"].split()[0]) if item.get("duration", "").split() and item["duration"].split()[0].isdigit() else None,
        "studios": [entry["name"] for entry in item.get("studios", [])],
        "genres": [entry["name"] for entry in item.get("genres", [])], "format": item.get("type"),
        "scores": {"mal": item["score"] * 10} if item.get("score") is not None else {},
        "provider_ids": candidate["provider_ids"], "alternate_titles": candidate["alternate_titles"],
        "links": [{"label": "MyAnimeList", "url": item["url"]}] if item.get("url") else [], "airing": airing,
    }}


@operation
def media(values):
    identity_id = entity_id(values)
    if identity_id is None:
        return {}
    item = get(values["request"], f"/anime/{identity_id}").get("data") or {}
    image = (item.get("images") or {}).get("jpg") or {}
    url = image.get("large_image_url") or image.get("image_url")
    return {"assets": [{"kind": "poster", "url": url}] if url else []}


def health(values):
    result = search({"request": {**values["request"], "query": "Naruto", "limit": 1}})
    return result if result.get("failure") else {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
