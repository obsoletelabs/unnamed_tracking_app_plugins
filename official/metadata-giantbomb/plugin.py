"""Giant Bomb search identities and independent detail enrichment."""

import time
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderFailure, ProviderHttp, external_id, operation, provider_values, register

PROVIDER_ID = "official.metadata-giantbomb.giantbomb"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "GiantBomb", "identifier_namespace": "giantbomb",
    "media_types": ["game"],
    "operations": {"search": "search", "metadata": "metadata", "health": "health"},
    "configuration": [{"key": "api_key", "label": "Giant Bomb API key", "scope": "both"}],
}


def get(values, path, **params):
    credentials = provider_values(PROVIDER_ID, ("api_key",))
    data = ProviderHttp(values["request"], "giantbomb", min_gap=1)(
        "https://www.giantbomb.com/api/" + path + "?" + urlencode({
            **params, "format": "json", "api_key": credentials["api_key"],
        }), headers={"User-Agent": "unnamed-tracking-app/1.0"},
    )
    if data.get("status_code") == 100:
        raise ProviderFailure("invalid_configuration")
    if data.get("error") not in {None, "OK"}:
        raise ProviderFailure("unavailable")
    return data.get("results")


@operation
def search(values):
    work = values["request"]
    items = get(values, "search/", query=work["query"], resources="game",
                limit=work.get("limit", 20), field_list="id,name,original_release_date") or []
    return {"candidates": [
        {"provider": PROVIDER_ID, "external_id": str(item["id"]), "title": item["name"],
         "media_type": "game", "provider_ids": {"giantbomb": str(item["id"])},
         "year": int(item["original_release_date"][:4]) if item.get("original_release_date") else None}
        for item in items if item.get("name") and item.get("id") is not None
    ]}


@operation
def metadata(values):
    identity = external_id(values["candidate"], PROVIDER_ID, "giantbomb")
    if not identity or not identity.isdecimal():
        return {}
    item = get(values, f"game/3030-{int(identity)}/",
               field_list="id,name,deck,description,original_release_date,site_detail_url") or {}
    return {"metadata": {
        "title": item.get("name"), "description": item.get("deck") or item.get("description"),
        "release_date": item["original_release_date"][:10] if item.get("original_release_date") else None,
        "provider_ids": {"giantbomb": identity},
        "links": [{"label": "Giant Bomb", "url": item["site_detail_url"]}]
        if item.get("site_detail_url") else [],
    }}


def health(values):
    result = search({"request": {**values["request"], "query": "Portal", "limit": 1}})
    return result if result.get("failure") else {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
