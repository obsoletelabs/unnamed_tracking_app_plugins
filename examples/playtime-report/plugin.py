from __future__ import annotations

import heapq
import json
import time

from sdk.plugin_protocol import request

PLAYTIME_KEYS = ("playtime_minutes", "total_playtime_minutes", "playtime")


def _number(game: dict, *keys: str) -> float:
    for key in keys:
        value = game.get(key)
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            pass
    return 0.0


def refresh(values: dict) -> dict:
    user_id = (values.get("_plugin_context") or {}).get("user_id")
    if not user_id:
        raise ValueError("An authenticated action context is required.")
    result = request("games.list", "games.read", {"limit": 500})
    games = list(result.get("games", result.get("items", [])))

    # Parse each game's playtime once; nlargest matches sorted(reverse=True)[:10], ties included.
    scored = [(_number(game, *PLAYTIME_KEYS), game) for game in games]
    total_minutes = sum(minutes for minutes, _ in scored)

    top_games = [
        {
            "name": str(game.get("name") or game.get("title") or "Unknown game"),
            "minutes": int(minutes),
        }
        for minutes, game in heapq.nlargest(10, scored, key=lambda pair: pair[0])
    ]

    request(
        "storage.put",
        "plugin.storage",
        {
            "key": f"users/{user_id}/latest-report",
            "value": json.dumps(
                {
                    "game_count": len(games),
                    "total_minutes": int(total_minutes),
                    "top_games": top_games,
                },
                sort_keys=True,
            ),
        },
    )
    return {"game_count": len(games), "total_minutes": int(total_minutes), "top_games": top_games}


def main() -> None:
    request("lifecycle.ready", "lifecycle.ready", {})
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
