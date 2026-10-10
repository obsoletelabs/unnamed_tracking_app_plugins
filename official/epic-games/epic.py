"""Epic launcher protocol through bounded, host-mediated HTTP only."""

from __future__ import annotations

import base64
import json
import re
import time
from urllib.parse import parse_qs, quote, urlencode, urlsplit

from sdk.plugin_protocol import request

# Public launcher client credentials, not a player's account credentials.
CLIENT_ID = "34a02cf8f4414e29b15921876da36f9a"
CLIENT_SECRET = "daafbccc737745039dffe53d94fc76cf"
TOKEN_URL = "https://account-public-service-prod03.ol.epicgames.com/account/api/oauth/token"
LIBRARY_URL = "https://library-service.live.use1a.on.epicgames.com/library/api/public/items"
PLAYTIME_URL = "https://library-service.live.use1a.on.epicgames.com/library/api/public/playtime/account/{account}/all"
CATALOG_URL = "https://catalog-public-service-prod06.ol.epicgames.com/catalog/api/shared/namespace/{namespace}/bulk/items"
LOGIN_URL = "https://www.epicgames.com/id/login?" + urlencode(
    {
        "redirectUrl": "https://www.epicgames.com/id/api/redirect?"
        + urlencode(
            {
                "clientId": CLIENT_ID,
                "responseType": "code",
            }
        ),
    }
)
IDENTIFIER = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
MAX_TOKEN_LENGTH = 8192
NON_GAME = {"addons", "digitalextras", "plugins", "engines"}


class EpicError(ValueError):
    """Only fixed, safe messages may cross the action boundary."""


def code_from(raw):
    if not isinstance(raw, str) or len(raw) > 8192:
        raise EpicError("Paste the one-time code from Epic's sign-in page.")
    value = raw.strip().strip("\"'")
    if value.startswith("{"):
        try:
            data = json.loads(value)
            value = data.get("authorizationCode") or data.get("redirectUrl") or ""
        except (ValueError, AttributeError):
            value = ""
    if isinstance(value, str) and "code=" in value:
        value = parse_qs(urlsplit(value).query).get("code", [""])[0]
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{32}", value.strip()):
        raise EpicError("Paste the 32-character authorization code, its JSON page or redirect URL.")
    return value.strip()


def http(url, *, token=None, form=None):
    headers = {
        "User-Agent": "UELauncher/11.0.1-14907503+++Portal+Release-Live Windows/10.0.19041.1.256.64bit"
    }
    options = {}
    if token:
        headers["Authorization"] = "bearer " + token
    if form is not None:
        credentials = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        headers.update(
            Authorization="Basic " + credentials,
            **{"Content-Type": "application/x-www-form-urlencoded"},
        )
        options.update(method="POST", text_body=urlencode({**form, "token_type": "eg1"}))
    reply = request(
        "network.request", "network.outbound", {"url": url, "headers": headers, **options}
    )
    status = reply.get("status", 0)
    if status == 429:
        raise EpicError("Epic is busy. Wait a minute, then resume the import.")
    if status in {400, 401, 403} and (form is not None or status == 401):
        raise EpicError("Epic rejected this sign-in. Sign in on Epic again and paste a fresh code.")
    if not isinstance(status, int) or not 200 <= status < 300:
        raise EpicError(
            "Epic could not be reached or refused the request. Your saved import is retained."
        )
    return reply.get("data")


def token_pair(form):
    data = http(TOKEN_URL, form=form)
    if not isinstance(data, dict) or data.get("errorCode"):
        raise EpicError("Epic did not return a valid sign-in. Sign in again on Epic.")
    for key, label in (("access_token", "access token"), ("refresh_token", "refresh token")):
        value = data.get(key)
        if not isinstance(value, str) or not value:
            raise EpicError(
                f"Epic returned no valid {label}. Your previous connection is retained."
            )
        if len(value) > MAX_TOKEN_LENGTH or any(c.isspace() for c in value):
            raise EpicError(
                f"Epic returned an unsupported {label}. Your previous connection is retained."
            )
    if not isinstance(data.get("account_id"), str) or not re.fullmatch(
        r"[0-9a-fA-F]{32}", data["account_id"]
    ):
        raise EpicError("Epic returned an invalid account identity.")
    expiry = data.get("expires_in")
    if (
        isinstance(expiry, bool)
        or not isinstance(expiry, (int, float))
        or not 60 <= expiry <= 86400
    ):
        raise EpicError("Epic returned an invalid sign-in expiry.")
    return {
        "access_token": data["access_token"],
        "refresh_token": data["refresh_token"],
        "account_id": data["account_id"].lower(),
        "expires_at": time.time() + expiry,
        "display_name": str(data.get("displayName") or "Epic account")[:200],
    }


def library_page(session, cursor):
    data = http(
        LIBRARY_URL
        + "?"
        + urlencode(
            {
                "includeMetadata": "true",
                **({"cursor": cursor} if cursor else {}),
            }
        ),
        token=session["access_token"],
    )
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        raise EpicError("Epic returned an incomplete inventory. Availability has not changed.")
    records = []
    for row in data["records"]:
        if not isinstance(row, dict):
            raise EpicError("Epic returned an invalid inventory record. Resume later.")
        if row.get("namespace") == "ue" or row.get("sandboxType") == "PRIVATE":
            continue
        fields = [row.get(key) for key in ("namespace", "catalogItemId", "appName")]
        if not all(isinstance(value, str) and IDENTIFIER.fullmatch(value) for value in fields):
            raise EpicError(
                "Epic returned an incomplete inventory record. Availability has not changed."
            )
        records.append(dict(zip(("namespace", "catalogItemId", "appName"), fields)))
    metadata = data.get("responseMetadata")
    if not isinstance(metadata, dict):
        raise EpicError("Epic omitted inventory paging information. Availability has not changed.")
    cursor = metadata.get("nextCursor")
    if cursor is not None and (not isinstance(cursor, str) or len(cursor) > 2048):
        raise EpicError("Epic returned invalid inventory paging information.")
    return records, cursor or None


def playtime(session):
    data = http(PLAYTIME_URL.format(account=session["account_id"]), token=session["access_token"])
    if not isinstance(data, list):
        raise EpicError("Epic playtime is unavailable; recorded playtime will be retained.")
    values = {}
    for row in data:
        if not isinstance(row, dict):
            continue
        total, app = row.get("totalTime"), row.get("artifactId")
        if isinstance(app, str) and type(total) is int and 0 <= total <= 2_000_000_000:
            values[app] = max(values.get(app, 0), total)
    return values


def catalog(session, namespace, ids):
    query = urlencode(
        [("id", value) for value in ids]
        + [
            ("includeDLCDetails", "true"),
            ("includeMainGameDetails", "true"),
            ("country", "US"),
            ("locale", "en-US"),
        ]
    )
    data = http(
        CATALOG_URL.format(namespace=quote(namespace, safe="")) + "?" + query,
        token=session["access_token"],
    )
    if not isinstance(data, dict) or any(
        not isinstance(data.get(identity), dict) for identity in ids
    ):
        raise EpicError("Epic omitted catalogue entries. Resume to retry this batch.")
    return data


def game_item(record, metadata, played):
    categories = metadata.get("categories") or []
    if not isinstance(categories, list) or any(not isinstance(c, dict) for c in categories):
        raise EpicError("Epic returned unreadable game categories. Resume later.")
    if (
        metadata.get("mainGameItem")
        or {str(c.get("path", "")).lower().split("/", 1)[0] for c in categories} & NON_GAME
    ):
        return None
    title = metadata.get("title")
    if not isinstance(title, str) or not title.strip():
        raise EpicError("Epic omitted a game title. Resume to retry this batch.")
    identity = record["namespace"] + ":" + record["catalogItemId"]
    item = {"external_id": identity, "title": title[:500], "provider_ids": {"epic": identity}}
    for field, limit in (("description", 20000), ("developer", 200), ("publisher", 200)):
        value = metadata.get(field)
        if isinstance(value, str) and value.strip():
            item[field] = value[:limit]
    times = [played[app] for app in record["apps"] if app in played] if played is not None else []
    if times:
        item["playtime_seconds"] = max(times)
    return item
