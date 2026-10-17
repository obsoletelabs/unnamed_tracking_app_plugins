"""Sync problems as one evolving notification story per Jellyfin account (Plugin API 1.1.14).

An account that needs attention opens a story; a different problem revises it, and the next
successful sync resolves it. The host owns recipients, routing, privacy and history; this module
only declares the event type and publishes events for the subscribed account. A host or grant
that cannot take the story falls back to the earlier single message, and a notification problem
never blocks sync recovery.
"""

from __future__ import annotations

import hashlib
import time

from sdk.notification_stories import (
    CONTRACT_VERSION,
    publish_for_user,
    register_canonical_type_for_user,
)
from sdk.plugin_protocol import request

EVENT_TYPE = "official.jellyfin-media-sync.sync-attention"
STORY_PREFIX = "sync:"
ACCOUNTS_ROUTE = "/plugins/official.jellyfin-media-sync/accounts"
REGISTRATION = {
    "contract_version": CONTRACT_VERSION,
    "event_type": EVENT_TYPE,
    "label": "Jellyfin sync needs attention",
    "description": "A Jellyfin account cannot sync until its problem is fixed.",
    "story_key_prefix": STORY_PREFIX,
    "grouping": {"strategy": "key", "merge": "digest"},
    "lifecycle": {
        "contract_version": CONTRACT_VERSION,
        "event_type": EVENT_TYPE,
        "phases": [
            {"id": "attention", "label": "Needs attention", "severity": "warning"},
            {"id": "resolved", "label": "Syncing again", "terminal": True},
        ],
        "initial_phases": ["attention"],
        "transitions": [
            {"from_phase": "attention", "to_phase": "attention"},
            {"from_phase": "attention", "to_phase": "resolved"},
        ],
    },
    "facts": [
        {"key": "account", "label": "Account", "kind": "text"},
        {"key": "server", "label": "Server", "kind": "text", "required": False},
    ],
}


def _digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()[:32]


def _event(account: dict, server_name: str, phase: str, summary: str, event_id: str) -> dict:
    facts = [
        {"key": "account", "label": "Account", "value": {"kind": "text", "value": str(account["name"])[:200]}}
    ]
    if server_name:
        facts.append({"key": "server", "label": "Server",
                      "value": {"kind": "text", "value": server_name[:200]}})
    content = {
        "title": "Jellyfin sync needs attention" if phase == "attention" else "Jellyfin sync resumed",
        "summary": summary,
        "facts": facts,
        "actions": [{
            "id": "open_accounts", "label": "Open Jellyfin accounts",
            "target": {"kind": "host_route", "path": ACCOUNTS_ROUTE},
        }],
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "event_type": EVENT_TYPE,
        "event_id": event_id,
        "occurred_at": int(time.time()),
        "story": {"key": STORY_PREFIX + account["id"], "phase": phase},
        # Only one account's problems ever share a digest.
        "grouping_key": _digest("sync", account["id"]),
        "content": content,
    }


def _legacy(user: str, summary: str) -> None:
    request(
        "tasks.request",
        "tasks.background",
        {
            "user_id": user,
            "method": "notifications.send",
            "capability": "notifications.send",
            "payload": {"title": "Jellyfin sync needs attention", "body": summary},
        },
    )


def _publish(user: str, event: dict) -> None:
    register_canonical_type_for_user(user, REGISTRATION)
    publish_for_user(user, event, registration=REGISTRATION)


def report_problem(user: str, account: dict, server_name: str, summary: str) -> None:
    """Open or revise the account's story; raises only when neither route could deliver."""
    event = _event(account, server_name, "attention", summary,
                   _digest("attention", account["id"], summary))
    try:
        _publish(user, event)
    except (RuntimeError, ValueError, OSError):
        _legacy(user, summary)


def report_recovered(user: str, account: dict, server_name: str) -> None:
    """Resolve the story. Nothing to continue (earlier plain message) is not an error."""
    event = _event(account, server_name, "resolved",
                   "Synchronisation completed successfully again.",
                   _digest("resolved", account["id"], str(int(time.time()))))
    _publish(user, event)
