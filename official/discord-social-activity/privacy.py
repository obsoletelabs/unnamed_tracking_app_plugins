"""Remove Activity-owned room data without touching tracking libraries."""

import copy


def scrub_room(saved: dict, actor_id: str, *, purge: bool, source_id: str | None = None) -> dict | None:
    room = copy.deepcopy(saved)
    person = room.get("participants", {}).get(actor_id)
    if person is None:
        return room
    if purge:
        del room["participants"][actor_id]
        if not room["participants"]:
            return None
        for field in ("player_limits", "group_approvals"):
            room[field] = [entry for entry in room.get(field, []) if entry.get("confirmed_by") != actor_id]
    else:
        person["library"] = [game for game in person.get("library", []) if source_id and game.get("source_id") != source_id]
        person["connected"] = bool(person["library"])
        person["active"] = False
        person["vote"] = None
    # Cached results embed names, avatars and library contributions.
    room["shortlist"], room["selected"], room["history"], room["phase"] = [], None, [], "lobby"
    for member in room["participants"].values():
        member["vote"] = None
    if room.get("host_id") == actor_id and purge:
        room["host_id"] = next(iter(room["participants"]), None)
    room["revision"] = room.get("revision", 0) + 1
    return room
