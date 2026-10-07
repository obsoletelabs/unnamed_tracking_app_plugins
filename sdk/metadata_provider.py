"""Public Plugin API v1.1.1 metadata wire helpers, independent of the host source."""

from __future__ import annotations

import time
import math
import json
from typing import Any
from functools import wraps

from .plugin_protocol import GatewayRequestError, request


class ProviderFailure(RuntimeError):
    """Carry classifications without retaining remote bodies or credential-bearing URLs."""

    def __init__(self, code: str, retry_after: int | None = None, *, status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.retry_after = retry_after
        self.status = status

    def response(self) -> dict[str, Any]:
        failure: dict[str, Any] = {"code": self.code}
        if self.retry_after is not None:
            failure["retry_after_seconds"] = self.retry_after
        return {"failure": failure}


def configuration(provider_id: str) -> dict[str, str]:
    """The gateway derives the actor; plugins cannot request another user's credentials."""
    return request("metadata_providers.configuration", "metadata_providers.configuration",
                   {"provider_id": provider_id})["values"]


def network(url: str, **options: Any) -> Any:
    """One bounded mediated HTTP request; provider code chooses its retry policy."""
    options["headers"] = {"User-Agent": "unnamed-tracking-app/1.0", **options.get("headers", {})}
    response = request("network.request", "network.outbound", {"url": url, **options})
    status = response.get("status", 0)
    if status == 401:
        raise ProviderFailure("invalid_configuration", status=status)
    if status == 429:
        raise ProviderFailure("rate_limited", response.get("retry_after_seconds"), status=status)
    if not 200 <= status < 300:
        raise ProviderFailure("unavailable", status=status)
    return response.get("text") if options.get("response_format") == "text" else response.get("data")


def register(declaration: dict[str, Any]) -> None:
    """Registration retries gateway startup only; it never calls an external provider."""
    delay = 1
    while True:
        try:
            request("metadata_providers.register", "metadata_providers.register", declaration)
            return
        except GatewayRequestError as exc:
            if exc.code != "unavailable":
                raise
            time.sleep(delay)
            delay = min(delay * 2, 30)


class ProviderHttp:
    """Provider-owned pacing using the existing atomic plugin storage API.

    Interactive requests never wait longer than one second for a slot and never
    retry. Background requests may wait and retry within their own overall budget.
    No background worker reserves future slots ahead of an interactive request.
    """

    def __init__(self, work: dict[str, Any], namespace: str, *, min_gap: float = 0) -> None:
        self.background = work.get("policy") == "background"
        self.deadline = time.monotonic() + (24 if self.background else 7)
        self.key = "metadata/quota/" + namespace
        self.min_gap = min_gap

    def _pace(self) -> None:
        if not self.min_gap:
            return
        wait_deadline = min(self.deadline, time.monotonic() + (24 if self.background else 1))
        while time.monotonic() < wait_deadline:
            original = request("storage.get", "plugin.storage", {"key": self.key})["value"]
            next_at = float(original) if original else 0
            delay = max(0, next_at - time.time())
            if delay:
                if time.monotonic() + delay >= wait_deadline:
                    raise ProviderFailure("rate_limited", min(86400, math.ceil(delay)))
                time.sleep(delay)
                continue
            swapped = request("storage.compare_and_swap", "plugin.storage", {
                "key": self.key, "expected": original,
                "value": str(time.time() + self.min_gap),
            })["swapped"]
            if swapped:
                return
        raise ProviderFailure("rate_limited", 1)

    def __call__(self, url: str, **options: Any) -> Any:
        for attempt in range(3 if self.background else 1):
            self._pace()
            try:
                return network(url, **options)
            except ProviderFailure as exc:
                if exc.code not in {"rate_limited", "unavailable"}:
                    raise
                delay = exc.retry_after if exc.retry_after is not None else 2 ** attempt
                if exc.code == "rate_limited" and self.min_gap:
                    original = request("storage.get", "plugin.storage", {"key": self.key})["value"]
                    request("storage.compare_and_swap", "plugin.storage", {
                        "key": self.key, "expected": original,
                        "value": str(max(float(original or 0), time.time() + delay)),
                    })
                if not self.background or attempt == 2 or time.monotonic() + delay >= self.deadline:
                    raise
                time.sleep(delay)
        raise ProviderFailure("unavailable")


def provider_values(provider_id: str, required: tuple[str, ...]) -> dict[str, str]:
    values = configuration(provider_id)
    if any(not values.get(key) for key in required):
        raise ProviderFailure("not_configured" if not values else "invalid_configuration")
    return values


def external_id(candidate: dict[str, Any], provider_id: str, namespace: str) -> str | None:
    return candidate.get("provider_ids", {}).get(namespace) or (
        candidate.get("external_id") if candidate.get("provider") == provider_id else None
    )


def normalized_title(value: str) -> str:
    return "".join(character.casefold() for character in value if character.isalnum())


def exact_identity(candidates, selected):
    """Resolve a missing ID only when title and known year identify one result."""
    titles = {normalized_title(value) for value in
              [selected["title"], *selected.get("alternate_titles", [])]}
    matches = [item for item in candidates if
               normalized_title(item["title"]) in titles and
               (not selected.get("year") or item.get("year") == selected["year"])]
    return matches[0] if len(matches) == 1 else None


def metadata_page(work, key, entries, base=None):
    """Page canonical collections below the runtime's 64 KiB action result limit.

    Cursor offsets count actual entries, so variable-sized summaries never skip
    episodes. The host supplies the overall deadline and detects repeated cursors.
    """
    offset = int(work.get("cursor") or 0)
    if offset < 0:
        raise ProviderFailure("invalid_response")
    patch = dict(base or {})
    patch[key] = []
    response = {"metadata": patch}
    for entry in entries[offset:offset + 200]:
        patch[key].append(entry)
        if len(json.dumps(response, ensure_ascii=False).encode("utf-8")) > 48 * 1024:
            patch[key].pop()
            if not patch[key]:
                raise ProviderFailure("invalid_response")
            break
    next_offset = offset + len(patch[key])
    if next_offset < len(entries):
        response["next_cursor"] = str(next_offset)
    return response


def operation(callback):
    """Return bounded failure classifications at the provider boundary."""
    @wraps(callback)
    def invoke(values):
        try:
            return callback(values)
        except ProviderFailure as exc:
            return exc.response()
        except GatewayRequestError:
            return ProviderFailure("plugin_unavailable").response()
        except (ValueError, KeyError, TypeError):
            return ProviderFailure("invalid_response").response()
    return invoke
