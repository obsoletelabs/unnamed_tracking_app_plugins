"""Selected-entity retro artwork with separate developer and personal credential scopes."""

import time
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderHttp, normalized_title, operation, provider_values, register

PROVIDER_ID = "official.metadata-screenscraper.screenscraper"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "ScreenScraper", "media_types": ["game"],
    "operations": {"media": "media", "health": "health"},
    "configuration": [
        {"key": "devid", "label": "Developer ID", "scope": "system", "secret": False},
        {"key": "devpassword", "label": "Developer password", "scope": "system"},
        {"key": "ssid", "label": "Account name", "scope": "user", "secret": False},
        {"key": "sspassword", "label": "Account password", "scope": "user"},
    ],
}


def get(values, endpoint, **params):
    credentials = provider_values(PROVIDER_ID, ("devid", "devpassword", "ssid", "sspassword"))
    return ProviderHttp(values["request"], "screenscraper", min_gap=1)(
        "https://www.screenscraper.fr/api2/" + endpoint + "?" + urlencode({
            **credentials, "softname": "unnamed-tracking-app", "output": "json", **params,
        }), headers={"User-Agent": "unnamed-tracking-app/1.0"},
    )


@operation
def media(values):
    candidate = values["candidate"]
    data = get(values, "jeuRecherche.php", recherche=candidate["title"])
    entries = (data.get("response") or {}).get("jeux") or []
    names = {normalized_title(title) for title in [candidate["title"], *candidate.get("alternate_titles", [])]}
    item = next((item for item in entries if any(normalized_title(entry.get("text", "")) in names
                                                for entry in item.get("noms", []))), None)
    if item is None:
        return {"assets": []}
    kinds = {"box-2D": "key_art", "ss": "screenshot", "wheel": "logo", "fanart": "hero"}
    return {"assets": [{"kind": kinds[entry["type"]], "url": entry["url"]}
                       for entry in item.get("medias", [])
                       if entry.get("type") in kinds and entry.get("url")][:200]}


@operation
def health(values):
    get(values, "ssuserInfos.php")
    return {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
