"""RetroAchievements catalogue capabilities; account progress stays in the host integration."""

import time
from urllib.parse import urlencode

from sdk.metadata_provider import ProviderHttp, external_id, normalized_title, operation, provider_values, register

PROVIDER_ID = "official.metadata-retroachievements.retroachievements"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "RetroAchievements", "media_types": ["game"],
    "identifier_namespace": "retroachievements",
    "operations": {"search": "search", "metadata": "metadata", "health": "health"},
    "configuration": [{"key": "api_key", "label": "RetroAchievements Web API key", "scope": "both"}],
}
CONSOLES = (1, 2, 3, 4, 7, 8, 11, 12, 15, 18, 21)


def get(values, endpoint, **params):
    credentials = provider_values(PROVIDER_ID, ("api_key",))
    return ProviderHttp(values["request"], "retroachievements", min_gap=0.3)(
        "https://retroachievements.org/API/" + endpoint + "?" + urlencode({
            "y": credentials["api_key"], **params,
        }), headers={"User-Agent": "unnamed-tracking-app/1.0"},
    )


@operation
def search(values):
    work = values["request"]
    candidates = []
    query = normalized_title(work["query"])
    offset = int(work.get("cursor") or 0)
    for console in CONSOLES[offset:offset + 1]:
        items = get(values, "API_GetGameList.php", i=console)
        for item in items:
            if not item.get("Title") or query not in normalized_title(item["Title"]):
                continue
            candidates.append({
                "provider": PROVIDER_ID, "external_id": str(item["ID"]), "title": item["Title"],
                "media_type": "game", "provider_ids": {"retroachievements": str(item["ID"])},
                "platforms": [item["ConsoleName"]] if item.get("ConsoleName") else [],
            })
            if len(candidates) >= work.get("limit", 20):
                return {"candidates": candidates}
    return {"candidates": candidates, "next_cursor": str(offset + 1) if offset + 1 < len(CONSOLES) else None}


@operation
def metadata(values):
    identity = external_id(values["candidate"], PROVIDER_ID, "retroachievements")
    if identity is None:
        return {}
    item = get(values, "API_GetGame.php", i=identity)
    return {"metadata": {
        "title": item.get("Title"), "developer": item.get("Developer"), "publisher": item.get("Publisher"),
        "tags": [item["ConsoleName"]] if item.get("ConsoleName") else [],
        "platforms": [item["ConsoleName"]] if item.get("ConsoleName") else [],
        "provider_ids": {"retroachievements": identity},
        "links": [{"label": "RetroAchievements", "url": f"https://retroachievements.org/game/{identity}"}],
    }}


@operation
def health(values):
    get(values, "API_GetConsoleIDs.php")
    return {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
