"""Plugin API 1.1.14 canonical notification helpers, independent of host source.

A plugin declares an event type once (``register_canonical_type``) and publishes
story events for the authenticated account (``publish``). The host remains the
only owner of recipients, destinations, credentials, trust, retention,
scheduling, aggregation and dispatch, and validates every document again; the
checks here only fail fast with actionable messages and mirror the published
schemas and conformance cases (``tools/schemas``, ``tests/fixtures``).

Never publish this SDK's 1.1.14 helpers against a host older than Plugin API
1.1.14: ``negotiate_contract`` reports what the connected host supports.
"""

from __future__ import annotations

import ipaddress
import re
from string import Formatter
from typing import Any, NoReturn
from urllib.parse import urlsplit

from .plugin_protocol import request

CONTRACT_VERSION = "1.0.0"
NOTIFICATION_API_VERSION = "1.1.14"
CANONICAL_CAPABILITY = "notifications.canonical"
ACTIONS_CAPABILITY = "notifications.actions"
URGENCY_CAPABILITY = "notifications.urgency"
HTML_TEMPLATES_CAPABILITY = "notifications.templates.html"

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_FACT_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,31}$")
_EVENT_TYPE = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
_ACTION_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_FACT_PLACEHOLDER = re.compile(r"^fact_[A-Za-z_][A-Za-z0-9_]{0,31}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f-\x9f  ]")
_EXECUTABLE = re.compile(
    r"<\s*/?\s*(?:script|iframe|frame|frameset|object|embed|applet|form|input|button|textarea"
    r"|select|base|meta|link|svg|math|template|noscript)\b"
    r"|[\s/\"']on[a-z]+\s*="
    r"|=\s*[\"']?\s*(?:javascript|vbscript|data)\s*:"
    r"|expression\s*\(|@import",
    re.IGNORECASE,
)
_PLACEHOLDERS = {
    "title", "summary", "blocks", "facts", "actions", "attribution", "occurred_at",
    "expires_at", "live_link",
}
_FORBIDDEN_REQUIREMENTS = {"api.full", "notifications.sensitive"}
_FACT_KINDS = {"text", "integer", "decimal", "money", "timestamp", "boolean"}
_PHASE_SEVERITIES = {"info", "warning", "error"}
_SAFE_INTEGER = 2**53 - 1
_DNS_LABEL = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
_LOCAL_SUFFIXES = (".local", ".localhost", ".internal", ".lan", ".home.arpa", ".localdomain")


class ContractError(ValueError):
    """A document violates the published notification contract."""


def _fail(message: str) -> NoReturn:
    raise ContractError(message)


def _exact(document: Any, allowed: set[str], required: set[str], what: str) -> dict[str, Any]:
    if not isinstance(document, dict):
        _fail(f"{what} must be an object")
    unknown = set(document) - allowed
    if unknown:
        _fail(f"{what} has unsupported fields: {', '.join(sorted(map(str, unknown))[:3])}")
    missing = required - set(document)
    if missing:
        _fail(f"{what} is missing: {', '.join(sorted(missing))}")
    return document


def _text(value: Any, what: str, *, low: int = 1, high: int, line: bool = True) -> str:
    if not isinstance(value, str) or not low <= len(value) <= high:
        _fail(f"{what} must be text of {low} to {high} characters")
    if (_CONTROL.search(value) if line else re.search(r"[\x00-\x08\x0b-\x1f\x7f-\x9f]", value)):
        _fail(f"{what} contains control characters")
    if low and not value.strip():
        _fail(f"{what} must not be blank")
    return value


def _version(value: Any, what: str = "contract_version") -> str:
    match = isinstance(value, str) and re.fullmatch(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)", value)
    if not match:
        _fail(f"{what} must be a semantic version")
    parts = tuple(int(part) for part in value.split("."))
    host = tuple(int(part) for part in CONTRACT_VERSION.split("."))
    if parts[0] != host[0]:
        _fail(f"{what} {value} has an unsupported major version")
    if parts > host:
        _fail(f"{what} {value} is newer than this SDK ({CONTRACT_VERSION})")
    return value


def _https_url(value: Any, what: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) > 2048
        or not value.isascii()
        or any(char.isspace() or char == "\\" for char in value)
    ):
        _fail(f"{what} must be a short ASCII URL")
    parts = urlsplit(value)
    try:
        port = parts.port
    except ValueError:
        _fail(f"{what} port is invalid")
    host = parts.hostname or ""
    if (
        parts.scheme != "https"
        or not host
        or parts.username is not None
        or parts.password is not None
        or port not in (None, 443)
    ):
        _fail(f"{what} must be an HTTPS URL without credentials or a custom port")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        _fail(f"{what} hosts must be public DNS names, not IP addresses")
    labels = host.split(".")
    if len(labels) < 2 or host.endswith(_LOCAL_SUFFIXES) or not all(
        _DNS_LABEL.fullmatch(label) for label in labels
    ):
        _fail(f"{what} hosts must be public DNS names")
    return value


def _lifecycle(document: Any, event_type: str) -> dict[str, Any]:
    life = _exact(
        document,
        {"contract_version", "event_type", "phases", "initial_phases", "transitions"},
        {"contract_version", "event_type", "phases", "initial_phases"},
        "lifecycle",
    )
    _version(life["contract_version"], "lifecycle.contract_version")
    if life["event_type"] != event_type:
        _fail("The lifecycle describes another event type")
    phases = life["phases"]
    if not isinstance(phases, list) or not 1 <= len(phases) <= 16:
        _fail("lifecycle.phases must list 1 to 16 phases")
    ids: dict[str, bool] = {}
    for phase in phases:
        phase = _exact(phase, {"id", "label", "terminal", "severity"}, {"id", "label"}, "phase")
        if not isinstance(phase["id"], str) or not _IDENTIFIER.fullmatch(phase["id"]):
            _fail("Phase IDs are short lowercase identifiers")
        if phase["id"] in ids:
            _fail("Story phase IDs must be unique")
        _text(phase["label"], "phase label", high=64)
        if phase.get("severity") not in {None, *_PHASE_SEVERITIES}:
            _fail("Phase severity is unsupported")
        ids[phase["id"]] = phase.get("terminal") is True
    initial = life["initial_phases"]
    if (
        not isinstance(initial, list)
        or not 1 <= len(initial) <= 16
        or len(set(initial)) != len(initial)
        or not set(initial) <= set(ids)
    ):
        _fail("Initial phases must be unique declared phases")
    edges = []
    for edge in life.get("transitions", []):
        edge = _exact(edge, {"from_phase", "to_phase"}, {"from_phase", "to_phase"}, "transition")
        edges.append((edge["from_phase"], edge["to_phase"]))
    if len(edges) > 64 or len(set(edges)) != len(edges):
        _fail("Story transitions must be unique and at most 64")
    if any(a not in ids or b not in ids for a, b in edges):
        _fail("Story transitions must reference declared phases")
    if any(ids[a] for a, _ in edges):
        _fail("Terminal phases cannot transition")
    reachable, pending = set(initial), list(initial)
    while pending:
        current = pending.pop()
        for a, b in edges:
            if a == current and b not in reachable:
                reachable.add(b)
                pending.append(b)
    if reachable != set(ids):
        _fail("Every story phase must be reachable from an initial phase")
    return life


def _contribution(document: Any, event_type: str, facts: set[str]) -> dict[str, Any]:
    item = _exact(
        document,
        {"contract_version", "event_type", "surface", "kind", "fields", "template"},
        {"contract_version", "event_type", "surface", "kind"},
        "renderer contribution",
    )
    _version(item["contract_version"], "renderer contract_version")
    if item["event_type"] != event_type:
        _fail("Renderer contributions must describe this event type")
    if item["surface"] not in {"card", "email", "chat", "push", "text"}:
        _fail("Renderer surface is unsupported")
    if item["kind"] == "fields":
        fields = item.get("fields")
        allowed = {"title", "summary", "blocks", "facts", "images", "actions", "attribution",
                   "occurred_at", "expires_at", "live_link"}
        if (not isinstance(fields, list) or not 1 <= len(fields) <= 10
                or len(set(fields)) != len(fields) or not set(fields) <= allowed
                or item.get("template") is not None):
            _fail("Field layouts need unique approved field references and no template")
        return item
    if item["kind"] not in {"markdown_template", "html_template"} or item.get("fields"):
        _fail("Template contributions need a kind of markdown_template or html_template")
    template = _text(item.get("template"), "template", high=20_000, line=False)
    if item["kind"] == "html_template" and item["surface"] != "email":
        _fail("HTML templates are limited to the email surface")
    try:
        names = list(Formatter().parse(template))
    except ValueError:
        _fail("Template braces are unbalanced")
    for _, name, spec, conversion in names:
        if name is None:
            continue
        if spec or conversion or (name not in _PLACEHOLDERS and not _FACT_PLACEHOLDER.fullmatch(name)):
            _fail("Templates support only named canonical content placeholders")
        if name.startswith("fact_") and name[5:] not in facts:
            _fail("Templates may only reference declared facts")
    if item["kind"] == "html_template" and _EXECUTABLE.search(template):
        _fail("HTML templates cannot contain executable or embedded markup")
    return item


def check_registration(registration: dict[str, Any]) -> dict[str, Any]:
    """Validate a canonical type declaration locally; the host repeats every check."""
    document = _exact(
        registration,
        {"contract_version", "event_type", "label", "description", "required_trust", "purpose",
         "severity", "default_category", "max_urgency", "lifecycle", "story_key_prefix",
         "grouping", "facts", "actions", "renderers"},
        {"contract_version", "event_type", "label", "lifecycle"},
        "registration",
    )
    _version(document["contract_version"])
    event_type = document["event_type"]
    if not isinstance(event_type, str) or not _EVENT_TYPE.fullmatch(event_type):
        _fail("event_type must be a namespaced lowercase identifier")
    _text(document["label"], "label", high=128)
    _text(document.get("description", ""), "description", low=0, high=500, line=False)
    trust = document.get("required_trust", "PRIVATE")
    if trust not in {"PRIVATE", "SECURE"}:
        _fail("required_trust must be PRIVATE or SECURE")
    purpose = document.get("purpose", "standard")
    if purpose not in {"standard", "security"} or (purpose == "security" and trust != "SECURE"):
        _fail("Security notification types require SECURE destinations")
    if document.get("severity", "info") not in _PHASE_SEVERITIES:
        _fail("severity is unsupported")
    if document.get("default_category", "plugin") != "plugin":
        _fail("Categories are host-assigned: plugin producers are always 'plugin'")
    if document.get("max_urgency", "normal") not in {"normal", "critical"}:
        _fail("max_urgency must be normal or critical")
    prefix = document.get("story_key_prefix")
    if prefix is not None:
        _text(prefix, "story_key_prefix", high=64)
    grouping = _exact(document.get("grouping", {}), {"strategy", "merge"}, set(), "grouping")
    if grouping.get("strategy", "none") not in {"none", "key"} or grouping.get(
        "merge", "digest"
    ) not in {"digest", "separate"}:
        _fail("grouping strategy or merge is unsupported")
    _lifecycle(document["lifecycle"], event_type)
    facts = document.get("facts", [])
    if not isinstance(facts, list) or len(facts) > 24:
        _fail("At most 24 facts may be declared")
    keys = set()
    for fact in facts:
        fact = _exact(fact, {"key", "label", "kind", "required"}, {"key", "label", "kind"}, "fact")
        if not isinstance(fact["key"], str) or not _FACT_KEY.fullmatch(fact["key"]):
            _fail("Fact keys are short identifiers")
        _text(fact["label"], "fact label", high=64)
        if fact["kind"] not in _FACT_KINDS or not isinstance(fact.get("required", True), bool):
            _fail("Fact kind or required flag is unsupported")
        keys.add(fact["key"])
    if len(keys) != len(facts):
        _fail("Fact keys must be unique")
    _check_actions(document.get("actions", []))
    renderers = document.get("renderers", [])
    if not isinstance(renderers, list) or len(renderers) > 8:
        _fail("At most 8 renderer contributions may be declared")
    seen = {(item.get("surface"), item.get("kind"))
            for item in (_contribution(item, event_type, keys) for item in renderers)}
    if len(seen) != len(renderers):
        _fail("Each surface and kind may have one renderer contribution")
    return document


def _check_actions(actions: Any) -> None:
    if not isinstance(actions, list) or len(actions) > 5:
        _fail("At most 5 actions may be declared")
    ids = set()
    for action in actions:
        action = _exact(action, {"action_id", "label", "input", "output", "requires"},
                        {"action_id", "label"}, "action")
        if not isinstance(action["action_id"], str) or not _ACTION_ID.fullmatch(action["action_id"]):
            _fail("Action IDs are lowercase identifiers")
        ids.add(action["action_id"])
        _text(action["label"], "action label", high=40)
        if action.get("output", "message") not in {"none", "message"}:
            _fail("Action output must be none or message")
        inputs = action.get("input", {})
        if not isinstance(inputs, dict) or len(inputs) > 8:
            _fail("Actions take at most 8 inputs")
        for name, spec in inputs.items():
            spec = _exact(spec, {"type", "required", "max_length"}, {"type"}, "action input")
            if not _IDENTIFIER.fullmatch(str(name)) or spec["type"] not in {"string", "integer", "boolean"}:
                _fail("Action inputs are named identifiers of type string, integer or boolean")
            length = spec.get("max_length", 500)
            if type(length) is not int or not 1 <= length <= 500:
                _fail("Action input max_length must be 1 to 500")
        requires = action.get("requires", [])
        if (not isinstance(requires, list) or len(requires) > 4 or len(set(requires)) != len(requires)
                or any(not isinstance(item, str) for item in requires)):
            _fail("Action requirements must be at most 4 unique capability names")
        if _FORBIDDEN_REQUIREMENTS & set(requires):
            _fail("Actions cannot require sensitive or whole-API authority")
    if len(ids) != len(actions):
        _fail("Action IDs must be unique")


_FACT_VALUE_KEYS = {
    "text": {"kind", "value"}, "integer": {"kind", "value"}, "decimal": {"kind", "value"},
    "money": {"kind", "amount", "currency"}, "timestamp": {"kind", "value"},
    "boolean": {"kind", "value"},
}


def _fact_value(value: Any, kind: str) -> None:
    value = _exact(value, _FACT_VALUE_KEYS.get(kind, set()), _FACT_VALUE_KEYS.get(kind, set()), "fact value")
    if value["kind"] != kind:
        _fail(f"Fact value must be of kind {kind}")
    if kind == "text":
        _text(value["value"], "text fact", low=0, high=1000)
    elif kind in {"integer", "timestamp"}:
        number = value["value"]
        if type(number) is not int or abs(number) > _SAFE_INTEGER or (kind == "timestamp" and number < 0):
            _fail("Integer facts must be whole numbers within the safe range")
    elif kind == "decimal":
        if not isinstance(value["value"], str) or not re.fullmatch(
            r"-?(?:0|[1-9][0-9]{0,14})(?:\.[0-9]{1,6})?", value["value"]
        ):
            _fail("Decimal facts are exact decimal strings")
    elif kind == "money":
        if not isinstance(value["amount"], str) or not re.fullmatch(
            r"(?:0|[1-9][0-9]{0,14})(?:\.[0-9]{1,6})?", value["amount"]
        ) or not isinstance(value["currency"], str) or not re.fullmatch(r"[A-Z]{3}", value["currency"]):
            _fail("Money facts need an exact amount and a three-letter currency")
    elif type(value["value"]) is not bool:
        _fail("Boolean facts must be true or false")


def check_event(
    event: dict[str, Any], registration: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Validate an event, and its conformance to the registration when one is given."""
    document = _exact(
        event,
        {"contract_version", "event_type", "event_id", "occurred_at", "story", "grouping_key",
         "urgency", "content"},
        {"contract_version", "event_type", "event_id", "occurred_at", "content"},
        "event",
    )
    _version(document["contract_version"])
    if not isinstance(document["event_type"], str) or not _EVENT_TYPE.fullmatch(document["event_type"]):
        _fail("event_type must be a namespaced lowercase identifier")
    _text(document["event_id"], "event_id", high=64)
    if type(document["occurred_at"]) is not int or not 0 <= document["occurred_at"] <= _SAFE_INTEGER:
        _fail("occurred_at must be Unix seconds")
    if document.get("urgency", "normal") not in {"normal", "critical"}:
        _fail("urgency must be normal or critical")
    if document.get("grouping_key") is not None:
        _text(document["grouping_key"], "grouping_key", high=64, line=False)
    story = document.get("story")
    if story is not None:
        story = _exact(story, {"key", "phase"}, {"key", "phase"}, "story")
        _text(story["key"], "story key", high=128)
        if not isinstance(story["phase"], str) or not _IDENTIFIER.fullmatch(story["phase"]):
            _fail("Story phases are short lowercase identifiers")
    content = _check_content(document["content"])
    if content.get("expires_at") is not None and content["expires_at"] <= document["occurred_at"]:
        _fail("Content expiry must follow the event occurrence")
    if registration is not None:
        _conforms(document, content, check_registration(registration))
    return document


def _check_content(content: Any) -> dict[str, Any]:
    content = _exact(
        content, {"title", "summary", "blocks", "facts", "images", "actions", "attribution", "expires_at"},
        {"title", "summary"}, "content",
    )
    _text(content["title"], "title", high=500)
    _text(content["summary"], "summary", high=10_000, line=False)
    for name, bound in (("blocks", 32), ("facts", 24), ("images", 4), ("actions", 5)):
        if not isinstance(content.get(name, []), list) or len(content.get(name, [])) > bound:
            _fail(f"content.{name} may hold at most {bound} entries")
    for block in content.get("blocks", []):
        block = _exact(block, {"type", "text", "markdown"}, {"type"}, "block")
        field = {"text": "text", "markdown": "markdown"}.get(block["type"])
        if field is None:
            _fail("Block types are text and markdown")
        _text(block.get(field), "block", high=10_000, line=False)
    seen = set()
    for fact in content.get("facts", []):
        fact = _exact(fact, {"key", "label", "value"}, {"key", "label", "value"}, "fact")
        if not isinstance(fact["key"], str) or not _FACT_KEY.fullmatch(fact["key"]) or fact["key"] in seen:
            _fail("Fact keys must be unique identifiers")
        seen.add(fact["key"])
        _text(fact["label"], "fact label", high=64)
        if not isinstance(fact["value"], dict) or fact["value"].get("kind") not in _FACT_KINDS:
            _fail("Fact values need a supported kind")
        _fact_value(fact["value"], fact["value"]["kind"])
    for image in content.get("images", []):
        image = _exact(image, {"role", "source", "alt"}, {"source"}, "image")
        source = image["source"]
        if not isinstance(source, dict) or source.get("kind") not in {"external", "host_media"}:
            _fail("Image sources are external URLs or host media")
        if source["kind"] == "external":
            _https_url(source.get("url"), "image URL")
    action_ids = set()
    for action in content.get("actions", []):
        action = _exact(action, {"id", "label", "style", "target"}, {"id", "label", "target"}, "action")
        if not isinstance(action["id"], str) or not _IDENTIFIER.fullmatch(action["id"]) or action["id"] in action_ids:
            _fail("Content action IDs must be unique identifiers")
        action_ids.add(action["id"])
        _text(action["label"], "action label", high=40)
        target = action["target"]
        kind = target.get("kind") if isinstance(target, dict) else None
        if kind == "link":
            _https_url(target.get("url"), "action URL")
        elif kind == "host_route":
            path = target.get("path")
            if (not isinstance(path, str) or not path.startswith("/") or path.startswith("//")
                    or path == "/api" or path.startswith("/api/") or ".." in path.split("?")[0].split("/")):
                _fail("Use an application path such as /plugins/example, not an API route")
        elif kind == "plugin_action":
            if not isinstance(target.get("action_id"), str) or not _ACTION_ID.fullmatch(target["action_id"]):
                _fail("Plugin action targets name a declared action")
            if not isinstance(target.get("input", {}), dict) or len(target.get("input", {})) > 8:
                _fail("Plugin action inputs are at most 8 scalar values")
        else:
            _fail("Action targets are link, host_route or plugin_action")
    return content


def _conforms(event: dict[str, Any], content: dict[str, Any], registration: dict[str, Any]) -> None:
    if event["event_type"] != registration["event_type"]:
        _fail("The event describes another event type")
    story = event.get("story")
    if story is None:
        _fail("Canonical plugin events belong to a story")
    prefix = registration.get("story_key_prefix")
    if prefix is not None and not story["key"].startswith(prefix):
        _fail("The story key does not use the declared prefix")
    if story["phase"] not in {phase["id"] for phase in registration["lifecycle"]["phases"]}:
        _fail("The story phase is not declared")
    if event.get("urgency") == "critical" and registration.get("max_urgency") != "critical":
        _fail("The event type does not declare critical urgency")
    strategy = registration.get("grouping", {}).get("strategy", "none")
    if strategy == "none" and event.get("grouping_key") is not None:
        _fail("The event type declares no grouping")
    if strategy == "key" and event.get("grouping_key") is None:
        _fail("The event type declares grouping and needs a grouping key")
    declared = {fact["key"]: fact for fact in registration.get("facts", [])}
    sent = {fact["key"]: fact for fact in content.get("facts", [])}
    if set(sent) - set(declared):
        _fail("Facts are not declared for this event type")
    if any(fact.get("required", True) and key not in sent for key, fact in declared.items()):
        _fail("A required fact is missing")
    if any(sent[key]["value"]["kind"] != declared[key]["kind"] for key in sent):
        _fail("A fact does not have its declared kind")
    actions = {item["action_id"]: item for item in registration.get("actions", [])}
    for action in content.get("actions", []):
        target = action["target"]
        if target["kind"] != "plugin_action":
            continue
        declaration = actions.get(target["action_id"])
        if declaration is None:
            _fail("An action is not declared for this event type")
        values, inputs = target.get("input", {}), declaration.get("input", {})
        if set(values) - set(inputs):
            _fail("Action input is not declared")
        for name, spec in inputs.items():
            if name not in values:
                if spec.get("required", True):
                    _fail(f"Action input is required: {name}")
                continue
            expected = {"string": str, "integer": int, "boolean": bool}[spec["type"]]
            value = values[name]
            if not isinstance(value, expected) or (spec["type"] == "integer" and isinstance(value, bool)):
                _fail(f"Action input {name} must be of type {spec['type']}")
            if isinstance(value, str) and len(value) > spec.get("max_length", 500):
                _fail(f"Action input {name} exceeds its declared length")


# --- gateway operations ----------------------------------------------------------------------


def negotiate_contract(contract_version: str = CONTRACT_VERSION) -> str:
    """Ask the connected host which contract version to use; raise if none is compatible."""
    result = request("notifications.contract", CANONICAL_CAPABILITY,
                     {"contract_version": contract_version})
    negotiated = result.get("negotiated")
    if not isinstance(negotiated, str):
        raise ContractError(str(result.get("reason") or "No compatible contract version"))
    return negotiated


def register_canonical_type(registration: dict[str, Any]) -> dict[str, Any]:
    """Declare a canonical event type. Needs notifications.canonical plus each grant it uses."""
    return request("notification_sources.register", "notification_sources.register",
                   check_registration(registration))


def publish(event: dict[str, Any], *, registration: dict[str, Any] | None = None) -> dict[str, Any]:
    """Publish one canonical event for the authenticated account (idempotent by event_id)."""
    return request("notifications.publish", CANONICAL_CAPABILITY, check_event(event, registration))


def _for_user(user_id: str, method: str, capability: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Run one reviewed operation for a subscribed account from a background worker.

    Requires ``tasks.background`` and the account's opt-in; the host rechecks the target
    account's live grant for ``capability`` and rejects any other operation.
    """
    return request("tasks.request", "tasks.background",
                   {"user_id": user_id, "method": method, "capability": capability, "payload": payload})


def register_canonical_type_for_user(user_id: str, registration: dict[str, Any]) -> dict[str, Any]:
    """``register_canonical_type`` for a background worker acting for ``user_id``."""
    return _for_user(user_id, "notification_sources.register", "notification_sources.register",
                     check_registration(registration))


def publish_for_user(user_id: str, event: dict[str, Any], *,
                     registration: dict[str, Any] | None = None) -> dict[str, Any]:
    """``publish`` for a background worker acting for ``user_id`` (idempotent by event_id)."""
    return _for_user(user_id, "notifications.publish", CANONICAL_CAPABILITY,
                     check_event(event, registration))


# --- host callbacks ----------------------------------------------------------------------------


def story_action_context(values: dict[str, Any]) -> dict[str, Any]:
    """Validate the private context the host gives a story-action handler.

    The handler's own ``values`` are the typed inputs the plugin declared; the account is in
    ``_plugin_context``. The host already rechecked ownership, the live story and the grants.
    """
    context = values.get("_notification_context") if isinstance(values, dict) else None
    if (not isinstance(context, dict) or context.get("operation") != "story_action"
            or set(context) != {"operation", "story_id", "revision", "installation_id"}
            or type(context["revision"]) is not int or context["revision"] < 1):
        raise ContractError("Core story-action authority is required")
    return context


def delivery_operation(delivery: dict[str, Any]) -> tuple[str, str | None]:
    """The operation and earlier-message reference of a capability-narrowed delivery."""
    operation = delivery.get("operation", "send") if isinstance(delivery, dict) else None
    reference = delivery.get("remote_ref") if isinstance(delivery, dict) else None
    if operation not in {"send", "edit", "follow_up"} or (
        reference is not None and (not isinstance(reference, str) or not 1 <= len(reference) <= 512)
    ) or (operation == "edit" and reference is None):
        raise ContractError("Delivery operation is invalid")
    return operation, reference


def delivery_result(
    *, success: bool, retryable: bool = False, remote_ref: str | None = None, gone: bool = False
) -> dict[str, Any]:
    """Result of a delivery or edit. Return ``gone=True`` when an earlier message cannot change."""
    if remote_ref is not None and (not isinstance(remote_ref, str) or not 1 <= len(remote_ref) <= 512):
        raise ContractError("remote_ref must be an opaque reference of 1 to 512 characters")
    result: dict[str, Any] = {"success": bool(success), "retryable": bool(retryable)}
    if remote_ref is not None:
        result["remote_ref"] = remote_ref
    if gone:
        result["gone"] = True
    return result


def provider_capabilities(**changes: Any) -> dict[str, Any]:
    """A presentation-capability declaration for ``NotificationProviderDefinition.capabilities``.

    Declaring ``message_updates`` of ``edit`` or ``replace`` also requires the definition's
    ``edit_action``. Capabilities never carry trust, verification, consent or grants.
    """
    declaration = {"contract_version": CONTRACT_VERSION, **changes}
    allowed = {"contract_version", "max_batch_items", "message_updates", "threaded_follow_ups",
               "text_formats", "rich_embeds", "images", "action_buttons", "links",
               "live_page_links", "max_title_chars", "max_text_chars", "max_payload_bytes"}
    unknown = set(declaration) - allowed
    if unknown:
        raise ContractError(f"Unsupported capability fields: {', '.join(sorted(unknown))}")
    _version(declaration["contract_version"])
    if declaration.get("message_updates", "none") not in {"none", "edit", "replace"}:
        raise ContractError("message_updates must be none, edit or replace")
    if (declaration.get("live_page_links") or declaration.get("action_buttons")) and not declaration.get("links"):
        raise ContractError("Live-page links and action buttons require link support")
    return declaration
