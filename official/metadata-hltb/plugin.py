"""Best-effort HowLongToBeat enrichment; its unofficial endpoint may reject requests."""

import re
import time

from sdk.metadata_provider import ProviderHttp, normalized_title, operation, register

PROVIDER_ID = "official.metadata-hltb.hltb"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "HowLongToBeat", "media_types": ["game"],
    "identifier_namespace": "hltb", "operations": {"metadata": "metadata", "health": "health"},
}


def lookup(work, title):
    return ProviderHttp(work, "hltb", min_gap=0.5)(
        "https://howlongtobeat.com/api/search", method="POST", headers={
            "User-Agent": "Mozilla/5.0 (compatible; unnamed-tracking-app/1.0)",
            "Referer": "https://howlongtobeat.com/",
        }, body={
            "searchType": "games", "searchTerms": re.sub(r"[^\w\s]", " ", title).split(),
            "searchPage": 1, "size": 5, "searchOptions": {
                "games": {"userId": 0, "platform": "", "sortCategory": "popular",
                          "rangeCategory": "main", "rangeTime": {"min": None, "max": None},
                          "gameplay": {"perspective": "", "flow": "", "genre": ""}, "modifier": ""},
                "users": {"sortCategory": "postcount"}, "filter": "", "sort": 0, "randomizer": 0,
            },
        },
    ).get("data", [])


@operation
def metadata(values):
    candidate = values["candidate"]
    match = next((item for item in lookup(values["request"], candidate["title"])
                  if normalized_title(item.get("game_name", "")) == normalized_title(candidate["title"])), None)
    if match is None or not match.get("comp_main"):
        return {}
    return {"metadata": {"time_to_beat_hours": round(match["comp_main"] / 3600, 1),
                         "provider_ids": {"hltb": str(match["game_id"])}}}


@operation
def health(values):
    lookup(values["request"], "Portal")
    return {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
