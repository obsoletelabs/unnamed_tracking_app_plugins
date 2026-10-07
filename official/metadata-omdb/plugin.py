"""OMDb lightweight identities and exact IMDb enrichment, with scoped API credentials."""

import re
import time
from datetime import datetime
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderFailure, ProviderHttp, external_id, operation, provider_values, register

PROVIDER_ID = "official.metadata-omdb.imdb"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "OMDb", "identifier_namespace": "imdb", "media_types": ["movie", "tv_show"],
    "operations": {"search": "search", "metadata": "metadata", "media": "media", "health": "health"},
    "configuration": [{"key": "api_key", "label": "OMDb API key", "scope": "both"}],
}


def clean(value):
    return value if value and value != "N/A" else None


def get(values, **params):
    credentials = provider_values(PROVIDER_ID, ("api_key",))
    data = ProviderHttp(values["request"], "omdb", min_gap=0.2)(
        "https://www.omdbapi.com/?" + urlencode({**params, "apikey": credentials["api_key"]}),
    )
    if data.get("Response") == "False":
        error = data.get("Error", "").lower()
        if "not found" in error:
            return {}
        raise ProviderFailure("invalid_configuration" if "api key" in error else
                              "rate_limited" if "limit" in error else "unavailable")
    return data


@operation
def search(values):
    work = values["request"]
    page = int(work.get("cursor") or 1)
    data = get(values, s=work["query"], type="movie" if work["media_type"] == "movie" else "series", page=page)
    candidates = [{"provider": PROVIDER_ID, "external_id": entry["imdbID"], "title": entry["Title"],
                   "media_type": work["media_type"], "year": int(entry["Year"][:4]) if re.match(r"\d{4}", entry.get("Year", "")) else None,
                   "provider_ids": {"imdb": entry["imdbID"]}}
                  for entry in data.get("Search", []) if entry.get("imdbID") and entry.get("Title")]
    return {"candidates": candidates[:work.get("limit", 20)],
            "next_cursor": str(page + 1) if page < 100 and int(data.get("totalResults") or 0) > page * 10 else None}


def entity(values):
    identity_id = external_id(values["candidate"], PROVIDER_ID, "imdb")
    return get(values, i=identity_id, plot="full") if identity_id else None


@operation
def metadata(values):
    item = entity(values)
    if not item:
        return {}
    release = None
    if clean(item.get("Released")):
        try:
            release = datetime.strptime(item["Released"], "%d %b %Y").date().isoformat()
        except ValueError:
            pass
    runtime = re.match(r"(\d+)", clean(item.get("Runtime")) or "")
    return {"metadata": {
        "title": clean(item.get("Title")), "release_date": release, "description": clean(item.get("Plot")),
        "runtime_minutes": int(runtime[1]) if runtime else None, "episode_runtime_minutes": int(runtime[1]) if runtime and values["request"]["media_type"] == "tv_show" else None,
        "director": clean(item.get("Director")), "writer": clean(item.get("Writer")),
        "countries": (clean(item.get("Country")) or "").split(", ") if clean(item.get("Country")) else [],
        "languages": (clean(item.get("Language")) or "").split(", ") if clean(item.get("Language")) else [],
        "genres": (clean(item.get("Genre")) or "").split(", ") if clean(item.get("Genre")) else [],
        "scores": {"imdb": float(item["imdbRating"]) * 10} if clean(item.get("imdbRating")) else {},
        "provider_ids": {"imdb": item["imdbID"]}, "links": [{"label": "IMDb", "url": f"https://www.imdb.com/title/{item['imdbID']}/"}],
    }}


@operation
def media(values):
    item = entity(values)
    url = clean((item or {}).get("Poster"))
    return {"assets": [{"kind": "poster", "url": url}] if url else []}


def health(values):
    result = search({"request": {**values["request"], "query": "The Matrix", "limit": 1, "media_type": "movie"}})
    return result if result.get("failure") else {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
