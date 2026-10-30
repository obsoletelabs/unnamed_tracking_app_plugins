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
# RetroAchievements game-system IDs (events and hubs are not games and are excluded). The first
# eleven keep their original order so a cursor saved by an earlier version still resumes correctly.
CONSOLE_NAMES = {
    1: "Mega Drive", 2: "Nintendo 64", 3: "SNES", 4: "Game Boy", 7: "NES", 8: "PC Engine",
    11: "Master System", 12: "PlayStation", 15: "Game Gear", 18: "Nintendo DS", 21: "PlayStation 2",
    5: "Game Boy Advance", 6: "Game Boy Color", 9: "Sega CD", 10: "32X", 13: "Atari Lynx",
    14: "Neo Geo Pocket", 16: "GameCube", 17: "Atari Jaguar", 19: "Wii", 20: "Wii U", 22: "Xbox",
    23: "Magnavox Odyssey 2", 24: "Pokemon Mini", 25: "Atari 2600", 26: "DOS", 27: "Arcade",
    28: "Virtual Boy", 29: "MSX", 30: "Commodore 64", 31: "ZX81", 32: "Oric", 33: "SG-1000",
    34: "VIC-20", 35: "Amiga", 36: "Atari ST", 37: "Amstrad CPC", 38: "Apple II", 39: "Saturn",
    40: "Dreamcast", 41: "PlayStation Portable", 42: "Philips CD-i", 43: "3DO", 44: "ColecoVision",
    45: "Intellivision", 46: "Vectrex", 47: "PC-8000/8800", 48: "PC-9800", 49: "PC-FX",
    50: "Atari 5200", 51: "Atari 7800", 52: "X68K", 53: "WonderSwan", 54: "Cassette Vision",
    55: "Super Cassette Vision", 56: "Neo Geo CD", 57: "Fairchild Channel F", 58: "FM Towns",
    59: "ZX Spectrum", 60: "Game & Watch", 61: "Nokia N-Gage", 62: "Nintendo 3DS",
    63: "Watara Supervision", 64: "Sharp X1", 65: "TIC-80", 66: "Thomson TO8", 67: "PC-6000",
    68: "Sega Pico", 69: "Mega Duck", 70: "Zeebo", 71: "Arduboy", 72: "WASM-4", 73: "Arcadia 2001",
    74: "Interton VC 4000", 75: "Elektor TV Games Computer", 76: "PC Engine CD",
    77: "Atari Jaguar CD", 78: "Nintendo DSi", 79: "TI-83", 80: "Uzebox",
}
CONSOLES = tuple(CONSOLE_NAMES)


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
    if not 0 <= offset < len(CONSOLES):
        # An unknown or stale cursor ends the search instead of wrapping around.
        return {"candidates": [], "next_cursor": None}
    for console in CONSOLES[offset:offset + 1]:
        items = get(values, "API_GetGameList.php", i=console)
        for item in items:
            if not item.get("Title") or query not in normalized_title(item["Title"]):
                continue
            candidates.append({
                "provider": PROVIDER_ID, "external_id": str(item["ID"]), "title": item["Title"],
                "media_type": "game", "provider_ids": {"retroachievements": str(item["ID"])},
                "platforms": [item.get("ConsoleName") or CONSOLE_NAMES[console]],
            })
            if len(candidates) >= work.get("limit", 20):
                # Keep the cursor so the remaining consoles stay searchable.
                break
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
