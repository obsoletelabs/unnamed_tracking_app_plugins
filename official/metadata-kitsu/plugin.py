"""Kitsu search and canonical anime/episode enrichment."""

import time
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderHttp, external_id, operation, register

PROVIDER_ID = "official.metadata-kitsu.kitsu"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "Kitsu", "identifier_namespace": "kitsu",
    "media_types": ["anime"],
    "metadata_resources": ["entity", "episodes", "airing"],
    "operations": {"search": "search", "metadata": "metadata", "media": "media", "health": "health"},
}


def get(work, path):
    return ProviderHttp(work, "kitsu", min_gap=0.3)(
        "https://kitsu.io/api/edge" + path, headers={"Accept": "application/vnd.api+json"}
    )


def identity(item):
    attributes = item["attributes"]
    titles = attributes.get("titles") or {}
    return {"provider": PROVIDER_ID, "external_id": str(item["id"]), "media_type": "anime",
            "title": attributes.get("canonicalTitle") or next(iter(titles.values()), ""),
            "alternate_titles": list(dict.fromkeys(title for title in titles.values() if title))[:20],
            "year": int(attributes["startDate"][:4]) if attributes.get("startDate") else None,
            "provider_ids": {"kitsu": str(item["id"])}}


@operation
def search(values):
    work = values["request"]
    data = get(work, "/anime?" + urlencode({"filter[text]": work["query"], "page[limit]": min(20, work.get("limit", 20))}))
    return {"candidates": [identity(item) for item in data.get("data", []) if item.get("attributes", {}).get("canonicalTitle")]}


def entity(values):
    identity_id = external_id(values["candidate"], PROVIDER_ID, "kitsu")
    if not identity_id:
        return None
    return get(values["request"], "/anime/" + identity_id).get("data")


@operation
def metadata(values):
    work = values["request"]
    item = entity(values)
    if item is None:
        return {}
    if work.get("resource") == "episodes":
        offset = int(work.get("cursor") or 0)
        result = get(work, "/episodes?" + urlencode({"filter[mediaType]": "Anime", "filter[media_id]": item["id"], "page[limit]": 20, "page[offset]": offset}))
        episodes = [{"episode_number": entry["attributes"]["number"], "title": entry["attributes"].get("canonicalTitle"),
                     "description": entry["attributes"].get("synopsis"), "air_date": entry["attributes"].get("airdate"),
                     "runtime_minutes": entry["attributes"].get("length"), "still_url": (entry["attributes"].get("thumbnail") or {}).get("original")}
                    for entry in result.get("data", []) if isinstance(entry.get("attributes", {}).get("number"), int)]
        return {"metadata": {"episodes": episodes}, "next_cursor": str(offset + 20) if (result.get("links") or {}).get("next") else None}
    attributes = item["attributes"]
    return {"metadata": {
        "title": identity(item)["title"], "release_date": attributes.get("startDate"),
        "description": attributes.get("synopsis"), "episode_count": attributes.get("episodeCount"),
        "episode_runtime_minutes": attributes.get("episodeLength"), "format": attributes.get("subtype"),
        "provider_ids": identity(item)["provider_ids"], "alternate_titles": identity(item)["alternate_titles"],
        "airing": {"is_airing": attributes.get("status") == "current", "total_episodes": attributes.get("episodeCount"),
                   "status": {"current": "ongoing", "finished": "completed"}.get(attributes.get("status"), "unknown")},
    }}


@operation
def media(values):
    item = entity(values)
    attributes = (item or {}).get("attributes") or {}
    return {"assets": [{"kind": kind, "url": entry["original"]} for kind, entry in
                       (("poster", attributes.get("posterImage") or {}), ("banner", attributes.get("coverImage") or {})) if entry.get("original")]}


def health(values):
    result = search({"request": {**values["request"], "query": "Naruto", "limit": 1}})
    return result if result.get("failure") else {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
