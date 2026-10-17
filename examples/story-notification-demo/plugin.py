"""Versioned story notifications through the public Plugin API 1.1.14 contract.

The plugin declares one canonical event type with a lifecycle, typed facts, a typed action and
a Markdown contribution, then publishes story events for the authenticated account. It never
chooses recipients, destinations or credentials; the host validates, stores, routes and delivers.
"""

from __future__ import annotations

import json
import time
from uuid import UUID

from sdk.notification_stories import (
    CONTRACT_VERSION,
    publish,
    register_canonical_type,
    story_action_context,
)
from sdk.plugin_protocol import request

EVENT_TYPE = "example.story-notification-demo.update"
STORY_PREFIX = "update:"
REGISTRATION = {
    "contract_version": CONTRACT_VERSION,
    "event_type": EVENT_TYPE,
    "label": "Story update demo",
    "description": "A demonstration update whose status evolves in one notification story.",
    "story_key_prefix": STORY_PREFIX,
    "grouping": {"strategy": "key", "merge": "digest"},
    "lifecycle": {
        "contract_version": CONTRACT_VERSION,
        "event_type": EVENT_TYPE,
        "phases": [
            {"id": "available", "label": "Available"},
            {"id": "installed", "label": "Installed", "terminal": True},
            {"id": "failed", "label": "Failed", "terminal": True, "severity": "error"},
        ],
        "initial_phases": ["available"],
        "transitions": [
            {"from_phase": "available", "to_phase": "available"},
            {"from_phase": "available", "to_phase": "installed"},
            {"from_phase": "available", "to_phase": "failed"},
        ],
    },
    "facts": [
        {"key": "version", "label": "Version", "kind": "text"},
        {"key": "size_mb", "label": "Download size (MB)", "kind": "integer", "required": False},
    ],
    "actions": [
        {
            "action_id": "acknowledge",
            "label": "Acknowledge",
            "input": {"version": {"type": "string", "max_length": 32}},
            "output": "message",
        }
    ],
    "renderers": [
        {
            "contract_version": CONTRACT_VERSION,
            "event_type": EVENT_TYPE,
            "surface": "chat",
            "kind": "markdown_template",
            "template": "**{title}** {fact_version}",
        }
    ],
}
PHASES = {"available": "is ready", "installed": "was installed", "failed": "could not be installed"}


def actor(values: dict) -> str:
    # This context is supplied by the authenticated host action boundary.
    try:
        return str(UUID((values.get("_plugin_context") or {}).get("user_id")))
    except (TypeError, ValueError, AttributeError):
        raise ValueError("An authenticated plugin action context is required") from None


def event(version: str, phase: str) -> dict:
    if phase not in PHASES:
        raise ValueError("Unknown update phase")
    if not isinstance(version, str) or not 1 <= len(version) <= 32 or not version.isprintable():
        raise ValueError("Enter a version of 1 to 32 characters")
    content = {
        "title": f"Version {version} {PHASES[phase]}",
        "summary": f"The demonstration update {version} {PHASES[phase]}.",
        "facts": [{"key": "version", "label": "Version", "value": {"kind": "text", "value": version}}],
    }
    if phase == "available":
        content["actions"] = [{
            "id": "ack", "label": "Acknowledge",
            "target": {"kind": "plugin_action", "action_id": "acknowledge", "input": {"version": version}},
        }]
    return {
        "contract_version": CONTRACT_VERSION,
        "event_type": EVENT_TYPE,
        "event_id": f"{version}:{phase}",
        "occurred_at": int(time.time()),
        "story": {"key": STORY_PREFIX + version, "phase": phase},
        "grouping_key": "demo-updates",
        "content": content,
    }


def send(values: dict, phase: str) -> dict:
    actor(values)
    version = values.get("version", "2.0.0")
    register_canonical_type(REGISTRATION)
    result = publish(event(version, phase), registration=REGISTRATION)
    # Acknowledgement means accepted by the core, never final delivery to any destination.
    return {"accepted": result.get("created") is True, "notification_id": result.get("notification_id")}


def announce(values: dict) -> dict:
    return send(values, "available")


def finish(values: dict) -> dict:
    return send(values, "installed")


def fail(values: dict) -> dict:
    return send(values, "failed")


def acknowledge(values: dict) -> dict:
    """Run by the host for a notification action, after it rechecked actor, story and grants."""
    context = story_action_context(values)
    user_id = actor(values)
    version = values.get("version")
    if not isinstance(version, str) or not 1 <= len(version) <= 32:
        raise ValueError("The declared version input is required")
    request("storage.put", "plugin.storage", {
        "key": f"users/{user_id}/acknowledged/{context['story_id']}",
        "value": json.dumps({"version": version, "revision": context["revision"]}),
    })
    return {"message": f"Version {version} acknowledged"}


def main() -> None:
    request("lifecycle.ready", "lifecycle.ready", {})
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
