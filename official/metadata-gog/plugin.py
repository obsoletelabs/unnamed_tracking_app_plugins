"""GOG public catalogue search and product metadata, without account credentials."""

import time
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderHttp, external_id, operation, register

PROVIDER_ID = "official.metadata-gog.gog"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "GOG", "media_types": ["game"],
    "identifier_namespace": "gog",
    "operations": {"search": "search", "metadata": "metadata", "health": "health"},
}


@operation
def search(values):
    work = values["request"]
    data = ProviderHttp(work, "gog", min_gap=0.2)(
        "https://catalog.gog.com/v1/catalog?" + urlencode({
            "query": "like:" + work["query"], "limit": work.get("limit", 20),
            "order": "desc:trending",
        }), headers={"User-Agent": "unnamed-tracking-app/1.0"},
    )
    return {"candidates": [
        {"provider": PROVIDER_ID, "external_id": str(item["id"]), "title": item["title"],
         "media_type": "game", "provider_ids": {"gog": str(item["id"])},
         "year": int(item["releaseDate"][:4]) if item.get("releaseDate") else None}
        for item in data.get("products", [])[:work.get("limit", 20)]
        if item.get("title") and item.get("id") is not None
    ]}


@operation
def metadata(values):
    identity = external_id(values["candidate"], PROVIDER_ID, "gog")
    if identity is None:
        return {}
    data = ProviderHttp(values["request"], "gog", min_gap=0.2)(
        f"https://api.gog.com/products/{identity}?expand=description",
        headers={"User-Agent": "unnamed-tracking-app/1.0"},
    )
    return {"metadata": {
        "title": data.get("title"), "description": (data.get("description") or {}).get("lead"),
        "provider_ids": {"gog": identity},
        "links": [{"label": "GOG", "url": data["links"]["product_card"]}]
        if (data.get("links") or {}).get("product_card") else [],
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
