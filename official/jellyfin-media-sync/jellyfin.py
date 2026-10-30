"""Jellyfin JSON client and bounded, credential-free media normalization."""

from __future__ import annotations

import json
import math
import re
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from sdk.plugin_protocol import request

SUPPORTED_TYPES = {"Movie", "Series", "Episode"}
# Jellyfin keeps ONE access token per (user, DeviceId): signing in again with the same
# DeviceId revokes the token an earlier sign-in received. Every connection therefore signs in
# under its own DeviceId (see device_id), and only credentials issued before that change
# keep sending the shared legacy value.
LEGACY_DEVICE_ID = "utp-jellyfin"
CLIENT_TEMPLATE = (
    'MediaBrowser Client="Unnamed Tracking", Device="Media Sync", DeviceId="{}", Version="0.0.1"'
)
FIELDS = (
    "ProviderIds,Overview,Genres,Tags,Studios,People,ProductionLocations,MediaStreams"
)


class SyncError(ValueError):
    """Public, sanitized failure classification used for bounded retries."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "configuration",
        retry_after: int = 0,
        status: int = 0,
    ):
        super().__init__(message)
        self.code, self.retry_after, self.status = code, retry_after, status


def device_id(identity: str) -> str:
    """Stable, per-connection Jellyfin DeviceId so sign-ins never revoke one another."""
    return LEGACY_DEVICE_ID + "-" + identity


def server_url(value: Any) -> str:
    if not isinstance(value, str):
        raise SyncError("Enter a Jellyfin server URL.")
    value = value.strip()
    try:
        parts = urlsplit(value)
        _ = parts.port
    except ValueError:
        raise SyncError("The server URL or port is invalid.") from None
    if (
        parts.scheme not in {"https", "http"}
        or not parts.hostname
        or parts.username
        or parts.password
        or parts.query
        or parts.fragment
        or "\\" in value
        or any(c.isspace() or ord(c) < 32 for c in value)
        or '"' in value
    ):
        raise SyncError("Use an HTTP(S) URL without credentials, query or fragment.")
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", "")
    )


def api(
    server: dict,
    token: str | None,
    path: str,
    *,
    query: dict | None = None,
    method: str = "GET",
    body: dict | None = None,
    device: str = LEGACY_DEVICE_ID,
) -> Any:
    client = CLIENT_TEMPLATE.format(device)
    headers = {"Authorization": client + (f', Token="{token}"' if token else "")}
    payload = {
        "url": server_url(server["url"]) + path,
        "headers": headers,
        "method": method,
    }
    if query:
        payload["url"] += "?" + urlencode(query)
    if body is not None:
        payload["body"] = body
    result = request("network.request", "network.outbound", payload)
    code = result.get("status", 0)
    if not 200 <= code < 300:
        if code in {401, 403}:
            raise SyncError(
                "Jellyfin no longer accepts the saved credential. Reconnect the account "
                "(or ask an administrator to replace the server key)."
                if token and code == 401
                else "Jellyfin refused access. Replace the credential or check library access.",
                code="authentication",
                status=code,
            )
        if result.get("code") == "certificate_untrusted":
            raise SyncError(
                "Certificate warning: configure the host to trust this server's CA before syncing.",
                code="certificate",
            )
        raise SyncError(
            "Jellyfin is unavailable. Your saved progress will resume.",
            # 408 is a gateway or proxy giving up on a slow server, not a bad request.
            code="transient"
            if code in {0, 408, 429} or code >= 500
            else "configuration",
            retry_after=result.get("retry_after_seconds", 0),
            status=code,
        )
    return result.get("data")


def token_value(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._-]{8,512}", value):
        raise SyncError("Jellyfin returned an invalid credential.")
    return value


def timestamp(value: Any) -> int | None:
    if not value:
        return None
    if not isinstance(value, str):
        raise SyncError(
            "Jellyfin returned an invalid playback timestamp.", code="remote_data"
        )
    try:
        return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())
    except (ValueError, OverflowError):
        raise SyncError(
            "Jellyfin returned an invalid playback timestamp.", code="remote_data"
        ) from None


def integer(value: Any, *, maximum: int = 10**16) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 <= value <= maximum
    ):
        raise SyncError(
            "Jellyfin returned invalid progress or episode numbers.", code="remote_data"
        )
    return value


def playback(row: dict) -> dict:
    user = row.get("UserData")
    if not isinstance(user, dict) or not isinstance(user.get("Played"), bool):
        raise SyncError(
            "Jellyfin omitted valid user playback data; this page was not finalized.",
            code="remote_data",
        )
    ticks = integer(user.get("PlaybackPositionTicks", 0))
    runtime = integer(0 if row.get("RunTimeTicks") is None else row["RunTimeTicks"])
    percent = user.get("PlayedPercentage")
    if percent is None:
        percent = min(100, 100 * ticks / runtime) if runtime else None
    if percent is not None and (
        isinstance(percent, bool)
        or not isinstance(percent, (int, float))
        or not math.isfinite(percent)
        or not 0 <= percent <= 100
    ):
        raise SyncError("Jellyfin returned an invalid percentage.", code="remote_data")
    return {
        "position_ticks": ticks,
        "runtime_ticks": runtime or None,
        "percentage": percent,
        "play_count": integer(user.get("PlayCount", 0), maximum=10**9),
        "last_played_at": timestamp(user.get("LastPlayedDate")),
    }


def texts(value: Any) -> list[str]:
    return (
        [v[:256] for v in value[:50] if isinstance(v, str)]
        if isinstance(value, list)
        else []
    )


def normalized(row: dict, server: dict, mapping: str) -> dict:
    if not isinstance(row, dict) or row.get("Type") not in SUPPORTED_TYPES - {
        "Episode"
    }:
        raise SyncError(
            "Jellyfin returned an unsupported root item.", code="remote_data"
        )
    external = row.get("Id")
    title = row.get("Name")
    if (
        not isinstance(external, str)
        or not 1 <= len(external) <= 256
        or not isinstance(title, str)
        or not title.strip()
    ):
        raise SyncError(
            "Jellyfin returned an item without a valid identity or title.",
            code="remote_data",
        )
    user_data = playback(row)
    tags = texts(row.get("Tags"))
    genres = texts(row.get("Genres"))
    anime = any(
        re.search(r"\banime\b|\banimation japonaise\b", t, re.I)
        for t in [*tags, *genres]
    )
    kind = (
        mapping
        if mapping != "auto"
        else "anime"
        if anime
        else "movie"
        if row["Type"] == "Movie"
        else "tv_show"
    )
    year = row.get("ProductionYear")
    year = (
        year
        if isinstance(year, int) and not isinstance(year, bool) and 1 <= year <= 9999
        else None
    )
    ids = row.get("ProviderIds", {})
    ids = (
        {
            k.lower(): str(v)[:256]
            for k, v in ids.items()
            if isinstance(k, str)
            and re.fullmatch(r"[a-zA-Z0-9._-]{1,50}", k)
            and isinstance(v, (str, int))
        }
        if isinstance(ids, dict)
        else {}
    )
    images = row.get("ImageTags", {})
    # TMDB movie and TV identifiers use separate namespaces. Collection IDs
    # are retained as metadata, but the host never uses them for title matching.
    if kind == "anime" and ids.get("tmdb"):
        ids["tmdb.movie" if row["Type"] == "Movie" else "tmdb.tv"] = ids.pop("tmdb")
    images = images if isinstance(images, dict) else {}
    base = server["url"] + "/Items/" + quote(external, safe="") + "/Images/"
    poster = base + "Primary" if images.get("Primary") else None
    backdrops = row.get("BackdropImageTags", [])
    people = row.get("People", [])
    people = (
        [p for p in people[:100] if isinstance(p, dict)]
        if isinstance(people, list)
        else []
    )
    studios = row.get("Studios", [])
    streams = row.get("MediaStreams", [])
    streams = (
        [stream for stream in streams[:30] if isinstance(stream, dict)]
        if isinstance(streams, list)
        else []
    )
    technical = [
        {
            key: value
            for key, value in stream.items()
            if key
            in {
                "Type",
                "Codec",
                "Language",
                "Width",
                "Height",
                "Channels",
                "BitRate",
                "IsDefault",
                "IsForced",
            }
            and isinstance(value, (str, int, bool))
            and (not isinstance(value, str) or len(value) <= 100)
        }
        for stream in streams
    ]
    metadata = {
        "description": str(row.get("Overview") or "")[:20000],
        "premiere_date": str(row.get("PremiereDate") or "")[:10]
        or (f"{year:04}-01-01" if year else None),
        "studios": texts([s.get("Name") for s in studios if isinstance(s, dict)])
        if isinstance(studios, list)
        else [],
        "countries": texts(row.get("ProductionLocations")),
        "tags": tags,
        "languages": texts(
            list(
                dict.fromkeys(
                    stream.get("Language")
                    for stream in streams
                    if isinstance(stream.get("Language"), str)
                )
            )
        ),
        "media_streams": technical,
        "date_precision": "day"
        if row.get("PremiereDate")
        else "year"
        if year
        else None,
        "age_rating": str(row.get("OfficialRating") or "")[:20],
        "director": ", ".join(
            str(p.get("Name", "")) for p in people if p.get("Type") == "Director"
        )[:200],
        "writer": ", ".join(
            str(p.get("Name", "")) for p in people if p.get("Type") == "Writer"
        )[:200],
        "creators": texts(
            [p.get("Name") for p in people if p.get("Type") in {"Director", "Creator"}]
        ),
        "people": [
            {
                "name": str(p.get("Name", ""))[:256],
                "role": str(p.get("Role", ""))[:256],
                "type": str(p.get("Type", ""))[:50],
            }
            for p in people
        ],
        "backdrop_url": base + "Backdrop/0" if backdrops else None,
        "artwork": {
            kind: base + kind
            for kind in ("Logo", "Thumb", "Banner", "Art")
            if images.get(kind)
        },
        "community_rating": row.get("CommunityRating"),
        "format": "Movie" if row["Type"] == "Movie" and kind == "anime" else None,
    }
    rating = row["UserData"].get("Rating")
    if (
        isinstance(rating, (int, float))
        and not isinstance(rating, bool)
        and 0 <= rating <= 10
    ):
        metadata["rating_overall"] = rating
    result = {
        "external_id": external,
        "media_type": kind,
        "title": title[:500],
        "genres": [v[:128] for v in genres],
        "runtime_minutes": min(100000, (user_data["runtime_ticks"] or 0) // 600000000)
        or None,
        "poster_url": poster,
        "played": row["UserData"]["Played"],
        "in_progress": user_data["position_ticks"] > 0,
        "provider_ids": ids,
        "release_year": year,
        "metadata": metadata,
        "playback": user_data,
        "remote_type": row["Type"],
    }
    # Keep only JSON values; invalid third-party metadata cannot leak into SQL.
    try:
        json.dumps(result, allow_nan=False)
    except (TypeError, ValueError):
        raise SyncError(
            "Jellyfin returned malformed metadata.", code="remote_data"
        ) from None
    return result
