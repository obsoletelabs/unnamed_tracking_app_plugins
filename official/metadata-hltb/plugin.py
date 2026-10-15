"""Best-effort HowLongToBeat enrichment; its unofficial endpoint may reject requests."""

import math
import re
import time

from sdk.metadata_provider import (
    ProviderFailure, ProviderHttp, external_id, normalized_title, operation, register,
)

PROVIDER_ID = "official.metadata-hltb.hltb"
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "HowLongToBeat", "media_types": ["game"],
    "identifier_namespace": "hltb", "operations": {"metadata": "metadata", "health": "health"},
}
SITE = "https://howlongtobeat.com"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": SITE + "/", "Origin": SITE,
}
TIME_FIELDS = {
    "time_to_beat_hours": "comp_main",
    "time_to_beat_extras_hours": "comp_plus",
    "time_to_beat_completionist_hours": "comp_100",
    "time_to_beat_all_hours": "comp_all",
}


def lookup(work, title):
    terms = re.sub(r"[^\w\s]", " ", title).split()
    if not terms:
        return []
    http = ProviderHttp(work, "hltb", min_gap=0.5)
    body = {
        "searchType": "games", "searchTerms": terms,
        "searchPage": 1, "size": 5, "searchOptions": {
            "games": {"userId": 0, "platform": "", "sortCategory": "popular",
                      "rangeCategory": "main", "rangeTime": {"min": None, "max": None},
                      "gameplay": {"perspective": "", "flow": "", "genre": "", "difficulty": ""},
                      "rangeYear": {"min": "", "max": ""}, "modifier": ""},
            "users": {"sortCategory": "postcount"}, "lists": {"sortCategory": "follows"},
            "filter": "", "sort": 0, "randomizer": 0,
        },
        "useCache": True,
    }
    for attempt in range(2):
        initialized = http(
            SITE + "/api/search/site/init?t=" + str(int(time.time() * 1000)),
            headers=BROWSER_HEADERS,
        )
        token = initialized.get("token") if isinstance(initialized, dict) else None
        if not isinstance(token, str) or not token or len(token) > 2048 or "\r" in token or "\n" in token:
            raise ProviderFailure("invalid_response")
        try:
            response = http(
                SITE + "/api/search/site", method="POST", body=body,
                headers={**BROWSER_HEADERS, "X-Auth-Token": token},
            )
        except ProviderFailure as exc:
            if exc.status == 403 and attempt == 0:
                continue
            raise
        if not isinstance(response, dict) or not isinstance(response.get("data"), list):
            raise ProviderFailure("invalid_response")
        return [item for item in response["data"] if isinstance(item, dict)]
    raise ProviderFailure("unavailable")


def hours(seconds):
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)):
        return None
    if not math.isfinite(seconds) or seconds <= 0:
        return None
    result = round(seconds / 3600, 1)
    return result if 0 < result <= 99_999.9 else None


@operation
def metadata(values):
    candidate = values["candidate"]
    identity = external_id(candidate, PROVIDER_ID, "hltb")
    entries = lookup(values["request"], candidate["title"])
    if identity:
        matches = [item for item in entries if str(item.get("game_id")) == identity]
    else:
        wanted = normalized_title(candidate["title"])
        matches = [item for item in entries if normalized_title(item.get("game_name", "")) == wanted]
    if len(matches) != 1:
        return {}
    match = matches[0]
    identifier = str(match.get("game_id", ""))
    if not identifier.isdecimal() or int(identifier) <= 0:
        return {}
    times = {field: value for field, source in TIME_FIELDS.items()
             if (value := hours(match.get(source))) is not None}
    return {"metadata": {**times, "provider_ids": {"hltb": identifier}}} if times else {}


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
