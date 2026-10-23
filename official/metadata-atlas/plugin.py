"""Atlas metadata provider: merged, cross-provider media records from a self-hosted Atlas node."""

import re
import time
from urllib.parse import quote, urlencode, urlsplit

from sdk.metadata_provider import ProviderFailure, ProviderHttp, external_id, operation, provider_values, register

PROVIDER_ID = "official.metadata-atlas.atlas"
MEDIA_TYPES = ("game", "anime", "movie", "tv_show")
DECLARATION = {
    "provider_id": PROVIDER_ID, "name": "Atlas", "identifier_namespace": "atlas",
    "media_types": list(MEDIA_TYPES),
    "metadata_resources": ["entity", "achievements"],
    "operations": {"search": "search", "metadata": "metadata", "media": "media", "health": "health"},
    "configuration": [
        {"key": "base_url", "label": "Atlas API URL", "scope": "both", "secret": False},
        {"key": "public_base_url", "label": "Public Atlas URL (optional)", "scope": "both", "required": False, "secret": False},
        {"key": "api_token", "label": "Atlas API token (read scope)", "scope": "both"},
    ],
}
ASSET_KINDS = {"key_art", "banner", "logo", "icon", "screenshot", "hero", "poster"}
ATLAS_ID = re.compile(r"^atlas:[0-9a-z]{26}$")
# Only methods that identify a game with certainty are used to fill in a missing Atlas ID.
CONFIDENT_MATCHES = {"crosswalk", "exact"}


def base_url(values):
    """The configured server root. Only a plain http(s) origin plus optional path prefix is accepted."""
    raw = (values.get("base_url") or "").strip().rstrip("/")
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password \
            or parts.query or parts.fragment:
        raise ProviderFailure("invalid_configuration")
    return raw


def public_base_url():
    """A browser-reachable Atlas root for artwork and links, defaulting to the API URL."""
    values = provider_values(PROVIDER_ID, ("base_url",))
    return base_url({"base_url": values.get("public_base_url") or values.get("base_url")})


def call(values, path, **options):
    credentials = provider_values(PROVIDER_ID, ("base_url", "api_token"))
    data = ProviderHttp(values["request"], "atlas")(
        base_url(credentials) + "/api/v2" + path,
        headers={"Authorization": "Bearer " + credentials["api_token"], "Accept": "application/json"},
        **options,
    )
    if not isinstance(data, dict):
        raise ProviderFailure("invalid_response")
    return data


def candidate(record, media_type="game"):
    media_type = record.get("media_type") if record.get("media_type") in MEDIA_TYPES else media_type
    ids = {"atlas": record["id"], **{key: str(value) for key, value in (record.get("provider_ids") or {}).items()
                                   if key != "atlas"}}
    year = int(record["release_date"][:4]) if record.get("release_date") else None
    return {"provider": PROVIDER_ID, "external_id": record["id"], "title": record["title"],
            "media_type": media_type, "provider_ids": ids, "year": year}


@operation
def search(values):
    work = values["request"]
    media_type = work.get("media_type", "game")
    if media_type not in MEDIA_TYPES:
        raise ProviderFailure("invalid_response")
    query = urlencode({"q": work["query"], "limit": min(int(work.get("limit", 20)), 50), "type": media_type})
    data = call(values, "/games?" + query)
    return {"candidates": [candidate(record, media_type) for record in data.get("results", [])
                            if record.get("id") and record.get("title")
                            and record.get("media_type", media_type) == media_type]}


def texts(value, limit, size):
    """Up to `limit` distinct short strings; anything else from the server is ignored."""
    seen, out = set(), []
    for item in value if isinstance(value, list) else []:
        text = item.strip() if isinstance(item, str) else ""
        if text and len(text) <= size and text.casefold() not in seen:
            seen.add(text.casefold())
            out.append(text)
    return out[:limit]


def group_play(game):
    """Atlas's standard multiplayer fields (players_min, players_max, crossplay), only when valid.

    Atlas allows larger player counts than the host stores (1-32): anything outside is dropped, and
    an inconsistent range is dropped as a whole. Unknown stays unset; nothing is guessed."""
    values = game.get("custom") if isinstance(game.get("custom"), dict) else {}

    def count(key):
        value = values.get(key)
        return value if isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 32 else None

    low, high = count("players_min"), count("players_max")
    if low is not None and high is not None and low > high:
        low = high = None
    out = {"players_min": low, "players_max": high}
    if values.get("crossplay") in ("yes", "no", "partial"):
        out["crossplay"] = values["crossplay"]
    return out


def _custom(record):
    value = record.get("custom")
    return value if isinstance(value, dict) else {}


def _count(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 100_000 else None


def _join_texts(value, limit, size, total):
    values = texts(value if isinstance(value, list) else [value], limit, size)
    out = []
    length = 0
    for item in values:
        addition = len(item) + (2 if out else 0)
        if length + addition > total:
            break
        out.append(item)
        length += addition
    return ", ".join(out)


def patch(record):
    """Map Atlas's type-labelled fields to the app's provider-neutral media contract."""
    media_type = record.get("media_type", "game")
    if media_type not in MEDIA_TYPES:
        return {}
    custom = _custom(record)
    title = record.get("title")
    age_rating = record.get("age_rating") if isinstance(record.get("age_rating"), str) else None
    website = record.get("website") if isinstance(record.get("website"), str) else ""
    scores = {name: record[key] for name, key in (("critic", "critic_score"), ("user", "user_score"))
              if isinstance(record.get(key), int) and not isinstance(record.get(key), bool)
              and 0 <= record[key] <= 100}
    tags = (record.get("tags") if isinstance(record.get("tags"), list) else []) + (
        record.get("themes") if isinstance(record.get("themes"), list) else [])
    out = {
        "title": title, "release_date": record.get("release_date"),
        "description": record.get("description"),
        "tags": texts(tags, 128, 128),
        "genres": texts(record.get("genres"), 128, 128),
        "languages": texts(record.get("languages"), 64, 128),
        "alternate_titles": [name for name in texts(record.get("aliases"), 21, 512) if name != title][:20],
        "age_rating": age_rating.strip()[:64] if age_rating else None,
        "links": [{"label": "Website", "url": website}] if website.startswith("https://") and len(website) <= 500
        and not any(c.isspace() for c in website) else [],
        "scores": scores,
        "custom": custom_values(record, media_type),
        "provider_ids": candidate(record, media_type)["provider_ids"],
    }
    if record.get("release_date"):
        out["year"] = int(record["release_date"][:4])

    if media_type == "game":
        out.update({
            "developer": record.get("developer"), "publisher": record.get("publisher"),
            "series": record.get("series"), "features": record.get("features") or [],
            "platforms": record.get("platforms") or [], **group_play(record),
        })
    elif media_type == "movie":
        out["director"] = record.get("developer")
        out["studios"] = texts([record.get("publisher")], 64, 256)
        out["runtime_minutes"] = _count(custom.get("runtime_minutes"))
        out["writer"] = _join_texts(custom.get("writer"), 16, 512, 512) or None
        out["countries"] = texts(custom.get("production_countries"), 64, 128)
    elif media_type == "anime":
        out["studios"] = texts([record.get("developer")], 64, 256)
        custom_format = custom.get("format")
        out["format"] = (custom_format.strip() if isinstance(custom_format, str) and 0 < len(custom_format.strip()) <= 64
                         else (texts(record.get("platforms"), 1, 64) or [None])[0])
        out["episode_count"] = _count(custom.get("episode_count"))
        out["tags"] = texts(tags + (record.get("features") or []), 128, 128)
        if record.get("series"):
            out["custom"] = {**out["custom"], "franchise": record["series"]}
    else:  # tv_show
        out["creators"] = texts([record.get("developer")], 64, 512)
        network = texts([record.get("publisher")], 1, 256)
        out["episode_count"] = _count(custom.get("episode_count"))
        out["episode_runtime_minutes"] = _count(custom.get("episode_runtime_minutes"))
        if network:
            out["custom"] = {**out["custom"], "network": network[0]}
        if record.get("series"):
            out["custom"] = {**out["custom"], "franchise": record["series"]}
    return {key: value for key, value in out.items() if value not in (None, "", [], {})}


def custom_values(record, media_type="game"):
    """Forward bounded fields Atlas exposes that have no typed app equivalent for this media type."""
    values = _custom(record)
    promoted = {
        "game": {"players_min", "players_max", "crossplay"},
        "movie": {"runtime_minutes", "writer", "production_countries"},
        "anime": {"format", "episode_count"},
        "tv_show": {"episode_count", "episode_runtime_minutes"},
    }.get(media_type, set())
    out = {}
    for key, value in values.items():
        if key in promoted or len(out) >= 32:
            continue
        if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", key):
            continue
        if isinstance(value, (bool, int)) or (isinstance(value, float) and value == value and abs(value) != float("inf")):
            out[key] = value
        elif isinstance(value, str) and 0 < len(value) <= 500:
            out[key] = value
        elif isinstance(value, list) and 0 < len(value) <= 50 and all(
                isinstance(item, str) and 0 < len(item) <= 200 for item in value):
            out[key] = value
    return out


def resolve(values, selected):
    """Find the Atlas record for a candidate that only carries other providers' identifiers."""
    item = {key: value for key, value in {
        "title": selected.get("title"),
        "release_date": f"{selected['year']}-01-01" if selected.get("year") else None,
        "media_type": selected.get("media_type", "game"),
        "provider_ids": {key: value for key, value in (selected.get("provider_ids") or {}).items()
                         if key != "atlas" and re.fullmatch(r"[a-z0-9._-]{1,50}", key)} or None,
    }.items() if value}
    if not item:
        return None
    data = call(values, "/resolve", method="POST", body={"items": [item], "include_view": True})
    result = (data.get("results") or [{}])[0]
    return result.get("game") if result.get("method") in CONFIDENT_MATCHES else None


def locate(values, selected):
    """The matching Atlas record, constrained to the selected media type."""
    identity = external_id(selected, PROVIDER_ID, "atlas")
    if identity and not ATLAS_ID.match(identity):
        return None
    try:
        record = call(values, "/games/" + quote(identity, safe=":")) if identity else resolve(values, selected)
        expected_type = selected.get("media_type", "game")
        if record and record.get("media_type", "game") != expected_type:
            return None
        return record
    except ProviderFailure as exc:
        if exc.status == 404:
            return None
        raise


def achievement_catalogue(values, game):
    """Atlas's achievement definitions (names, descriptions, rarity); never anyone's progress.

    Icons are Atlas's own verified copies, offered through its public /media path like artwork, so the
    host downloads them itself under its public-network rules. Hidden entries arrive redacted from Atlas
    and are forwarded as they come, flagged hidden."""
    try:
        data = call(values, "/games/" + quote(game["id"], safe=":") + "/achievements")
    except ProviderFailure as exc:
        if exc.status == 404:
            return {}
        raise
    root = public_base_url()
    items, seen = [], set()
    for entry in data.get("results", []):
        name = entry.get("name")
        identity = entry.get("id")
        if not isinstance(name, str) or not 0 < len(name.strip()) <= 200:
            continue
        if not isinstance(identity, str) or not 0 < len(identity) <= 200 or identity in seen:
            continue
        seen.add(identity)
        item = {"name": name.strip(), "external_id": identity, "hidden": entry.get("hidden") is True}
        if isinstance(entry.get("description"), str) and entry["description"].strip():
            item["description"] = entry["description"].strip()[:2000]
        percent = entry.get("global_percent")
        if isinstance(percent, (int, float)) and not isinstance(percent, bool) and 0 <= percent <= 100:
            item["global_percent"] = float(percent)
        for source, target in (("icon_url", "icon_url"), ("locked_icon_url", "locked_icon_url")):
            digest = (entry.get(source) or "").rsplit("/", 1)[-1] if isinstance(entry.get(source), str) else ""
            if re.fullmatch(r"[0-9a-f]{64}", digest):
                item[target] = f"{root}/media/{digest}"
        if entry.get("kind") in ("progression", "missable", "win_condition"):
            item["kind"] = entry["kind"]
        if entry.get("tier") in ("bronze", "silver", "gold"):
            item["tier"] = entry["tier"]
        points = entry.get("points")
        if isinstance(points, int) and not isinstance(points, bool) and 0 <= points <= 100_000:
            item["points"] = points
        ids = entry.get("external_ids") if isinstance(entry.get("external_ids"), dict) else {}
        source_ids = {k: v for k, v in ids.items() if isinstance(k, str) and re.fullmatch(r"[a-z0-9][a-z0-9._-]{0,127}", k)
                      and isinstance(v, str) and 0 < len(v) <= 512}
        if source_ids:
            item["source_ids"] = dict(list(source_ids.items())[:8])
        items.append(item)
    return {"achievements": items[:2000]} if items else {}


@operation
def metadata(values):
    selected = values["candidate"]
    media_type = selected.get("media_type", "game")
    if media_type not in MEDIA_TYPES:
        return {}
    record = locate(values, selected)
    if not record or not record.get("title"):
        return {}
    if values["request"].get("resource") == "achievements":
        if media_type != "game":
            return {}
        found = achievement_catalogue(values, record)
        return {"metadata": found} if found else {}
    result = patch(record)
    identity = record.get("id")
    if isinstance(identity, str) and ATLAS_ID.fullmatch(identity):
        root = public_base_url()
        result["links"] = [
            {"label": "Atlas record", "url": f"{root}/game/{quote(identity, safe=':')}"},
            *result.get("links", []),
        ]
    return {"metadata": result}


@operation
def media(values):
    """Artwork Atlas has already downloaded and verified, served from its public /media path."""
    selected = values["candidate"]
    media_type = selected.get("media_type", "game")
    if media_type not in MEDIA_TYPES:
        return {"assets": []}
    record = locate(values, selected)
    identity = record and record.get("id")
    if not identity or not ATLAS_ID.match(identity):
        return {"assets": []}
    root = public_base_url()
    try:
        data = call(values, "/games/" + quote(identity, safe=":") + "/artwork")
    except ProviderFailure as exc:
        if exc.status == 404:
            return {"assets": []}
        raise
    assets = []
    for item in data.get("results", []):
        digest = (item.get("media_url") or "").rsplit("/", 1)[-1]
        if item.get("kind") in ASSET_KINDS and re.fullmatch(r"[0-9a-f]{64}", digest):
            kind = item["kind"]
            if media_type != "game" and kind == "key_art":
                kind = "poster"
            asset = {"kind": kind, "url": f"{root}/media/{digest}", "priority": min(len(assets) * 10, 10000)}
            asset.update({k: item[k] for k in ("width", "height") if isinstance(item.get(k), int) and item[k] > 0})
            assets.append(asset)
    return {"assets": assets[:200]}


def health(values):
    result = search({"request": {**values["request"], "query": "portal", "limit": 1}})
    return result if result.get("failure") else {"health": "healthy"}


def main():
    register(DECLARATION)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
