"""TVDB v4 authentication, series search and official franchise relationships."""

import time
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderFailure, ProviderHttp, exact_identity, external_id, operation, provider_values, register

PROVIDER_ID = "official.metadata-tvdb.tvdb"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "TVDB", "identifier_namespace": "tvdb", "media_types": ["tv_show"],
    "metadata_resources": ["entity", "relations"],
    "operations": {"search": "search", "metadata": "metadata", "media": "media", "health": "health"},
    "configuration": [
        {"key": "api_key", "label": "TVDB API key", "scope": "both"},
        {"key": "pin", "label": "Subscriber PIN (when required)", "scope": "user", "required": False},
    ],
}


def client(values):
    credentials = provider_values(PROVIDER_ID, ("api_key",))
    http = ProviderHttp(values["request"], "tvdb", min_gap=0.2)
    response = http("https://api4.thetvdb.com/v4/login", method="POST", body={
        "apikey": credentials["api_key"], **({"pin": credentials["pin"]} if credentials.get("pin") else {}),
    })
    token = (response.get("data") or {}).get("token")
    if not token:
        raise ProviderFailure("invalid_configuration")

    def get(path, **params):
        response = http("https://api4.thetvdb.com/v4" + path + ("?" + urlencode(params) if params else ""),
                        headers={"Authorization": "Bearer " + token})
        if response.get("status") == "failure":
            raise ProviderFailure("unavailable")
        return response.get("data")
    return get


def identity(item):
    identity_id = str(item.get("tvdb_id") or item["id"])
    year = str(item.get("year") or item.get("firstAired") or "")
    return {"provider": PROVIDER_ID, "external_id": identity_id, "title": item["name"],
            "media_type": "tv_show", "provider_ids": {"tvdb": identity_id},
            "year": int(year[:4]) if year[:4].isdigit() else None}


@operation
def search(values):
    work = values["request"]
    items = client(values)("/search", query=work["query"], type="series", limit=work.get("limit", 20)) or []
    return {"candidates": [identity(item) for item in items if item.get("name") and item.get("tvdb_id")]}


@operation
def metadata(values):
    work = values["request"]
    get = client(values)
    identity_id = external_id(values["candidate"], PROVIDER_ID, "tvdb")
    if identity_id is None:
        found = exact_identity([identity(entry) for entry in
                                (get("/search", query=values["candidate"]["title"], type="series", limit=20) or [])
                                if entry.get("name") and entry.get("tvdb_id")], values["candidate"])
        if found is None:
            return {}
        identity_id = found["external_id"]
    item = get(f"/series/{identity_id}/extended") or {}
    if work.get("resource") == "relations":
        groups = item.get("lists") or []
        group = next((entry for entry in groups if entry.get("isOfficial")), next(iter(groups), None))
        if group is None:
            return {"metadata": {"relations": []}}
        entities = (get(f"/lists/{group['id']}/extended") or {}).get("entities") or []
        ids = [entry["seriesId"] for entry in entities if entry.get("seriesId") and str(entry["seriesId"]) != identity_id][:work.get("limit", 20)]
        offset = int(work.get("cursor") or 0)
        related = []
        for related_id in ids[offset:offset + 3]:
            entry = get(f"/series/{related_id}") or {}
            if entry.get("name"):
                related.append({"candidate": identity(entry), "relation": "franchise", "poster_url": entry.get("image")})
        return {"metadata": {"relations": related, "relation_group": group.get("name")},
                "next_cursor": str(offset + 3) if offset + 3 < len(ids) else None}
    return {"metadata": {
        "title": item.get("name"), "description": item.get("overview"), "release_date": item.get("firstAired") or None,
        "episode_runtime_minutes": item.get("averageRuntime"), "genres": [entry["name"] for entry in item.get("genres", [])],
        "provider_ids": {"tvdb": identity_id},
        "links": [{"label": "TVDB", "url": "https://thetvdb.com/series/" + item["slug"]}] if item.get("slug") else [],
    }}


@operation
def media(values):
    identity_id = external_id(values["candidate"], PROVIDER_ID, "tvdb")
    if identity_id is None:
        return {}
    item = client(values)(f"/series/{identity_id}/extended") or {}
    url = item.get("image")
    return {"assets": [{"kind": "poster", "url": url}] if url else []}


def health(values):
    result = search({"request": {**values["request"], "query": "The Office", "limit": 1}})
    return result if result.get("failure") else {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
