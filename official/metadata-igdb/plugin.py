"""IGDB v4 provider with plugin-owned Twitch authentication and request pacing."""

import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderFailure, ProviderHttp, exact_identity, external_id, operation, provider_values, register

PROVIDER_ID = "official.metadata-igdb.igdb"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "IGDB", "identifier_namespace": "igdb",
    "media_types": ["game"],
    "operations": {"search": "search", "metadata": "metadata", "media": "media", "health": "health"},
    "configuration": [
        {"key": "client_id", "label": "Twitch client ID", "scope": "system", "secret": False},
        {"key": "client_secret", "label": "Twitch client secret", "scope": "system"},
    ],
}


def games(values, query):
    credentials = provider_values(PROVIDER_ID, ("client_id", "client_secret"))
    http = ProviderHttp(values["request"], "igdb", min_gap=0.35)
    try:
        token = http("https://id.twitch.tv/oauth2/token?" + urlencode({
            **credentials, "grant_type": "client_credentials",
        }), method="POST").get("access_token")
    except ProviderFailure as exc:
        if exc.status in {400, 401, 403}:
            raise ProviderFailure("invalid_configuration") from exc
        raise
    if not token:
        raise ProviderFailure("invalid_configuration")
    return http("https://api.igdb.com/v4/games", method="POST", text_body=query,
                headers={"Client-ID": credentials["client_id"], "Authorization": "Bearer " + token,
                         "Content-Type": "text/plain"})


@operation
def search(values):
    work = values["request"]
    # JSON quoting prevents a query from injecting IGDB's query language.
    query = json.dumps(work["query"], ensure_ascii=False)
    data = games(values, f"search {query}; fields name,first_release_date,alternative_names.name,platforms.name; limit {work.get('limit', 20)};")
    return {"candidates": [
        {"provider": PROVIDER_ID, "external_id": str(item["id"]), "title": item["name"],
         "media_type": "game", "provider_ids": {"igdb": str(item["id"])},
         "year": datetime.fromtimestamp(item["first_release_date"], timezone.utc).year
         if item.get("first_release_date") else None,
         "alternate_titles": [entry["name"] for entry in item.get("alternative_names", [])][:20],
         "platforms": [entry["name"] for entry in item.get("platforms", [])][:32]}
        for item in data if item.get("name") and item.get("id") is not None
    ]}


def details(values, fields):
    identity = external_id(values["candidate"], PROVIDER_ID, "igdb")
    if not identity:
        found = search({"request": {**values["request"], "query": values["candidate"]["title"]}})
        if found.get("failure"):
            failure = found["failure"]
            raise ProviderFailure(failure["code"], failure.get("retry_after_seconds"))
        matched = exact_identity(found.get("candidates", []), values["candidate"])
        identity = matched["external_id"] if matched else None
    if not identity or not identity.isdecimal():
        return None
    data = games(values, f"fields {fields}; where id = {int(identity)}; limit 1;")
    return data[0] if data else None


@operation
def metadata(values):
    item = details(values, "name,summary,first_release_date,genres.name,platforms.name,involved_companies.company.name,involved_companies.developer,involved_companies.publisher,collection.name,franchises.name,alternative_names.name,url")
    if item is None:
        return {}
    companies = item.get("involved_companies", [])
    release = datetime.fromtimestamp(item["first_release_date"], timezone.utc).date() if item.get("first_release_date") else None
    return {"metadata": {
        "title": item.get("name"), "description": item.get("summary"),
        "release_date": release.isoformat() if release else None, "year": release.year if release else None,
        "developer": next((entry["company"]["name"] for entry in companies if entry.get("developer")), None),
        "publisher": next((entry["company"]["name"] for entry in companies if entry.get("publisher")), None),
        "series": (item.get("collection") or {}).get("name") or next((entry["name"] for entry in item.get("franchises", [])), None),
        "genres": [entry["name"] for entry in item.get("genres", [])],
        "tags": [entry["name"] for entry in item.get("genres", [])],
        "platforms": [entry["name"] for entry in item.get("platforms", [])],
        "alternate_titles": [entry["name"] for entry in item.get("alternative_names", [])][:20],
        "provider_ids": {"igdb": str(item["id"])},
        "links": [{"label": "IGDB", "url": item["url"]}] if item.get("url") else [],
    }}


@operation
def media(values):
    item = details(values, "cover.url,screenshots.url,artworks.url")
    if item is None:
        return {}
    assets = []
    for kind, entries in (("key_art", [item.get("cover") or {}]),
                          ("screenshot", item.get("screenshots", [])),
                          ("hero", item.get("artworks", []))):
        for entry in entries:
            url = entry.get("url")
            if url:
                assets.append({"kind": kind, "url": ("https:" + url if url.startswith("//") else url).replace("t_thumb", "t_original")})
    return {"assets": assets[:200]}


def health(values):
    result = search({"request": {**values["request"], "query": "Portal", "limit": 1}})
    return result if result.get("failure") else {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
