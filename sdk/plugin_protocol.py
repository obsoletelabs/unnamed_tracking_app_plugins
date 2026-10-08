"""Plugin API v1 line protocol and public response helpers."""

from __future__ import annotations

import json
import sys
from typing import Any

API_CONTRACT_VERSION = "1.1.2"


class GatewayRequestError(RuntimeError):
    """Preserve optional public error codes while retaining RuntimeError compatibility."""

    def __init__(self, message: str, detail: Any = None) -> None:
        super().__init__(message)
        code = detail.get("code") if isinstance(detail, dict) else None
        self.code: str | None = code if isinstance(code, str) else None


def request(method: str, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Send a mediated request and preserve the host's public failure classification."""
    print(
        json.dumps(
            {
                "api_version": "v1",
                "method": method,
                "capability": capability,
                "payload": payload,
            }
        ),
        flush=True,
    )
    line = sys.stdin.readline()
    if not line:
        raise RuntimeError("plugin gateway closed the connection")
    response = json.loads(line)
    if response.get("error"):
        raise GatewayRequestError(str(response["error"]), response.get("error_detail"))
    return dict(response.get("payload", {}))


def route_response(body: Any, status_code: int = 200) -> dict[str, Any]:
    """Build the bounded JSON response expected by a Plugin API v1 route handler."""

    if status_code < 200 or status_code > 599:
        raise ValueError("plugin route status_code must be between 200 and 599")
    return {"status_code": status_code, "body": body}


def route_query_value(route_request: dict[str, Any], name: str) -> str | None:
    """Return the first host-normalized query value without parsing raw URLs."""

    query = route_request.get("query")
    if not isinstance(query, dict):
        return None
    values = query.get(name)
    if not isinstance(values, list) or not values or not isinstance(values[0], str):
        return None
    return values[0]
