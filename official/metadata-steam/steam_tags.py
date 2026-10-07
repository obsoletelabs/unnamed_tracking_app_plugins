"""Pure Steam player-tag parsing and genre selection."""

import json
import re

MAX_TAGS = 12
MIN_TOP_VOTES = 20

NON_GENRE_TAGS = frozenset(
    {
        # who plays it
        "singleplayer",
        "multiplayer",
        "co-op",
        "pvp",
        "pve",
        "split screen",
        "massively multiplayer",
        "online pvp",
        "local multiplayer",
        "cross-platform multiplayer",
        # how it is controlled and where it runs
        "controller",
        "vr",
        "vr only",
        "steam deck",
        "remote play",
        "mouse only",
        "touch friendly",
        "gamepad",
        "keyboard",
        # what Steam adds around it
        "steam achievements",
        "steam cloud",
        "steam trading cards",
        "steam workshop",
        "includes level editor",
        "moddable",
        "mod",
        "workshop",
        "early access",
        "free to play",
        "demo",
        "software",
        "utilities",
        "game development",
        # opinions, not descriptions
        "great soundtrack",
        "good soundtrack",
        "soundtrack",
        "beautiful",
        "masterpiece",
        "replay value",
        "relaxing",
        "funny",
        "cute",
        # content warnings and ratings
        "violent",
        "gore",
        "blood",
        "nudity",
        "sexual content",
        "mature",
        "family friendly",
        "kids",
        # how it looks
        "2d",
        "3d",
    }
)
# any tag containing one of these is dropped too (Online Co-Op, Local Co-Op,
# Co-op Campaign, Full controller support, Local Multiplayer ...)
_NON_GENRE_PARTS = ("co-op", "coop", "controller", "multiplayer")

_TAG_MODAL = re.compile(r"InitAppTagModal\(\s*\d+,\s*(\[.*?\]),\s*\[", re.S)

def is_genre_tag(name: str) -> bool:
    """False for the tags that describe modes, controls, features or opinions."""
    lowered = name.strip().lower()
    if not lowered or lowered in NON_GENRE_TAGS:
        return False
    return not any(part in lowered for part in _NON_GENRE_PARTS)


def parse_tags(html: str) -> list[tuple[str, int]]:
    """The (tag, votes) pairs on a store page, most voted first."""
    match = _TAG_MODAL.search(html)
    if not match:
        return []
    try:
        raw = json.loads(match.group(1))
    except ValueError:
        return []
    tags: list[tuple[str, int]] = []
    for entry in raw:
        name = entry.get("name") if isinstance(entry, dict) else None
        if isinstance(name, str) and name.strip():
            votes = entry.get("count")
            tags.append((name.strip(), votes if isinstance(votes, int) else 0))
    return sorted(tags, key=lambda tag: -tag[1])


def pick_genre_tags(player_tags: list[tuple[str, int]], official_genres: list[str]) -> list[str]:
    """The player tags that are genres, most voted first, then any official Steam
    genre they did not already include. A game players have barely tagged keeps
    just its official genres."""
    chosen: list[str] = []
    seen: set[str] = set()

    def add(name: str) -> None:
        key = name.strip().lower()
        if key and key not in seen:
            seen.add(key)
            chosen.append(name.strip())

    if player_tags and player_tags[0][1] >= MIN_TOP_VOTES:
        kept = [name for name, _ in player_tags if is_genre_tag(name)]
        for name in kept[:MAX_TAGS]:
            add(name)
    for name in official_genres:
        add(name)
    return chosen


