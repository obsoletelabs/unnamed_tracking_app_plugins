"""A fake Discord HTTP API at the host's `network.request` boundary.

It enforces the hard message limits (a violation is an HTTP 400, never silently accepted), keeps
messages per bot and per webhook so edits by another bot or webhook fail like on Discord, dedupes
creates by nonce and can be scripted to fail, rate limit or lose messages.
"""
import json
import re
from urllib.parse import urlsplit

EMBED_TOTAL = 6000


def embed_characters(embed):
    total = len(embed.get("title", "")) + len(embed.get("description", "")) + len(embed.get("footer", {}).get("text", ""))
    return total + sum(len(f["name"]) + len(f["value"]) for f in embed.get("fields", []))


def violations(body, *, webhook):
    problems = []
    embeds = body.get("embeds", [])
    if len(embeds) > 10:
        problems.append("embeds")
    if sum(map(embed_characters, embeds)) > EMBED_TOTAL:
        problems.append("total characters")
    for embed in embeds:
        if len(embed.get("title", "")) > 256 or len(embed.get("description", "")) > 4096:
            problems.append("title/description")
        if len(embed.get("fields", [])) > 25:
            problems.append("fields")
        for field in embed.get("fields", []):
            if not field["name"] or not field["value"] or len(field["name"]) > 256 or len(field["value"]) > 1024:
                problems.append("field")
        if "description" in embed and not embed["description"]:
            problems.append("empty description")
    rows = body.get("components") or []
    if webhook and rows:
        problems.append("webhook components")
    if len(rows) > 5:
        problems.append("rows")
    for row in rows:
        buttons = row["components"]
        if len(buttons) > 5:
            problems.append("buttons")
        for button in buttons:
            if button.get("style") != 5 or not button.get("url", "").startswith(("http://", "https://")) or len(button["label"]) > 80:
                problems.append("button")
    if len(json.dumps(body)) > 64 * 1024:
        problems.append("request size")
    if body.get("allowed_mentions") != {"parse": []}:
        problems.append("mentions")
    if len(body.get("content") or "") > 2000:
        problems.append("content")
    if "nonce" in body and len(body["nonce"]) > 25:
        problems.append("nonce")
    return problems


class FakeDiscord:
    def __init__(self):
        self.calls = []
        self.messages = {}  # (scope, message id) -> {"owner": ..., "body": ...}
        self.next_id = 700000000000000000
        self.nonces = {}
        self.failures = []  # scripted (status, retry_after, match)
        self.denied_embeds = False
        self.dm_channels = {}

    # --- scripting -----------------------------------------------------------------------
    def fail_next(self, status, *, retry_after=None, method=None):
        self.failures.append((status, retry_after, method))

    def delete(self, scope, message_id):
        self.messages.pop((scope, message_id), None)

    def sent(self, method=None):
        return [c for c in self.calls if method in (None, c["method"])]

    # --- transport -----------------------------------------------------------------------
    def __call__(self, method, capability, payload):
        assert (method, capability) == ("network.request", "network.outbound")
        verb = payload.get("method", "GET")
        url = payload["url"]
        body = payload.get("body")
        headers = payload.get("headers", {})
        self.calls.append({"method": verb, "url": url, "body": body, "headers": headers})
        for index, (status, retry, only) in enumerate(self.failures):
            if only in (None, verb):
                del self.failures[index]
                result = {"status": status, "error": "Remote server rejected the request."}
                if retry is not None:
                    result["retry_after_seconds"] = retry
                return result
        parts = urlsplit(url)
        query = parts.query
        path = parts.path
        if "/webhooks/" in path:
            return self.webhook(verb, path, query, body)
        return self.api(verb, path.removeprefix("/api/v10"), body, headers)

    def new_id(self):
        self.next_id += 1
        return str(self.next_id)

    def webhook(self, verb, path, query, body):
        match = re.fullmatch(r"/api/webhooks/(\d+)/([\w.-]+)(?:/messages/(\d+))?", path)
        scope = "webhook:" + match.group(1) + ":" + match.group(2)
        message_id = match.group(3)
        problems = violations(body, webhook=True)
        if problems:
            return {"status": 400, "error": "Remote server rejected the request.", "problems": problems}
        if verb == "POST":
            if query != "wait=true":  # Discord answers 204 and never reveals the message id
                self.messages[(scope, self.new_id())] = {"owner": scope, "body": body}
                return {"status": 204, "text": ""}
            new = self.new_id()
            self.messages[(scope, new)] = {"owner": scope, "body": body}
            return {"status": 200, "data": {"id": new}}
        if verb == "PATCH" and (scope, message_id) in self.messages:
            self.messages[(scope, message_id)]["body"] = body
            return {"status": 200, "data": {"id": message_id}}
        return {"status": 404, "error": "Remote server rejected the request."}

    def api(self, verb, path, body, headers):
        bot = headers["Authorization"]
        if verb == "POST" and path == "/users/@me/channels":
            channel = self.dm_channels.setdefault((bot, body["recipient_id"]), self.new_id())
            return {"status": 200, "data": {"id": channel}}
        create = re.fullmatch(r"/channels/(\d+)/messages", path)
        edit = re.fullmatch(r"/channels/(\d+)/messages/(\d+)", path)
        if verb == "POST" and create:
            if self.denied_embeds and body.get("embeds"):
                return {"status": 403, "error": "Remote server rejected the request."}
            problems = violations(body, webhook=False)
            if problems:
                return {"status": 400, "error": "Remote server rejected the request.", "problems": problems}
            scope = create.group(1)
            key = (bot, scope, body.get("nonce")) if body.get("enforce_nonce") else None
            if key and key in self.nonces:
                return {"status": 200, "data": {"id": self.nonces[key]}}
            new = self.new_id()
            self.messages[(scope, new)] = {"owner": bot, "body": body}
            if key:
                self.nonces[key] = new
            return {"status": 200, "data": {"id": new}}
        if verb == "PATCH" and edit:
            record = self.messages.get((edit.group(1), edit.group(2)))
            if record is None:
                return {"status": 404, "error": "Remote server rejected the request."}
            if record["owner"] != bot:
                return {"status": 403, "error": "Remote server rejected the request."}
            problems = violations(body, webhook=False)
            if problems:
                return {"status": 400, "error": "Remote server rejected the request.", "problems": problems}
            record["body"] = body
            return {"status": 200, "data": {"id": edit.group(2)}}
        if verb == "GET" and re.fullmatch(r"/channels/(\d+)", path):
            return {"status": 200, "data": self.channel_info(path.rsplit("/", 1)[1])}
        raise AssertionError(f"Unexpected Discord request {verb} {path}")

    channel_info = staticmethod(lambda channel_id: {"id": channel_id, "guild_id": "123456789012345678", "type": 0})
