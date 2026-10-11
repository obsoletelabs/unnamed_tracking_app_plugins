"""Embed permission failures retry once with the same authorized content/target."""

import pytest

from test_discord_bot_notifications import load


def test_embed_permission_denial_falls_back_to_plaintext(monkeypatch):
    provider = load()
    calls = []

    def outbound(method, capability, payload):
        calls.append(payload)
        return {"status": 403, "error": "Remote server rejected the request."} if len(calls) == 1 else {"status": 200, "data": {"id": "sent"}}

    monkeypatch.setattr(provider, "request", outbound)
    content = "**Release available**\nAn episode is ready.\nhttps://app.example.test/release"
    provider._send_channel("test-token", "123456789012345678", content)
    assert len(calls) == 2
    assert calls[0]["url"] == calls[1]["url"]
    assert calls[0]["headers"] == calls[1]["headers"]
    assert "embeds" in calls[0]["body"]
    assert calls[1]["body"] == {
        "content": "**Release available**\n\nAn episode is ready.\n\n[View notification](https://app.example.test/release)",
        "flags": 4,
        "allowed_mentions": {"parse": []},
    }


@pytest.mark.parametrize("status", [0, 400, 401, 404, 429, 500])
def test_ambiguous_or_other_send_failures_do_not_send_again(monkeypatch, status):
    provider = load()
    calls = []

    def outbound(*args):
        calls.append(args)
        return {"status": status, "error": "Rejected"}

    monkeypatch.setattr(provider, "request", outbound)
    with pytest.raises(provider.PluginError):
        provider._send_channel("test-token", "123456789012345678", "Notification")
    assert len(calls) == 1


@pytest.mark.parametrize("status", [403, 429, 500])
def test_plaintext_failure_propagates_without_another_attempt(monkeypatch, status):
    provider = load()
    calls = []

    def outbound(*args):
        calls.append(args)
        return {"status": 403 if len(calls) == 1 else status, "error": "Rejected"}

    monkeypatch.setattr(provider, "request", outbound)
    with pytest.raises(provider.PluginError):
        provider._send_channel("test-token", "123456789012345678", "Notification")
    assert len(calls) == 2


def test_plaintext_is_bounded_and_suppresses_mentions_and_url_embeds(monkeypatch):
    provider = load()
    calls = []

    def outbound(method, capability, payload):
        calls.append(payload["body"])
        return {"status": 403} if len(calls) == 1 else {"status": 200, "data": {"id": "sent"}}

    monkeypatch.setattr(provider, "request", outbound)
    provider._send_channel("test-token", "123456789012345678", "@everyone " + "x" * 4000)
    assert len(calls[1]["content"]) == 2000
    assert calls[1]["flags"] == 4
    assert calls[1]["allowed_mentions"] == {"parse": []}


@pytest.mark.parametrize(("title", "label"), [
    ("Reset your password", "Reset your password"),
    ("You are invited", "Accept invitation"),
    ("Verify destination", "Verify destination"),
])
def test_plaintext_actions_describe_their_purpose(monkeypatch, title, label):
    provider = load()
    calls = []

    def outbound(method, capability, payload):
        calls.append(payload["body"])
        return {"status": 403} if len(calls) == 1 else {"status": 200, "data": {"id": "sent"}}

    monkeypatch.setattr(provider, "request", outbound)
    link = "https://app.example.test/action/(edition)#token=example"
    provider._send_channel("test-token", "123456789012345678", f"**{title}**\n" + "x" * 4000 + "\n" + link)
    text = calls[1]["content"]
    assert len(text) <= 2000
    assert text.endswith(f"[{label}](https://app.example.test/action/%28edition%29#token=example)")
    assert text.count("token=example") == 1


def test_too_long_action_is_omitted_whole_not_cut_into_a_broken_link(monkeypatch):
    provider = load()
    calls = []

    def outbound(method, capability, payload):
        calls.append(payload["body"])
        return {"status": 403} if len(calls) == 1 else {"status": 200, "data": {"id": "sent"}}

    monkeypatch.setattr(provider, "request", outbound)
    provider._send_channel("test-token", "123456789012345678", "https://app.example.test/?token=" + "x" * 2100)
    assert len(calls[1]["content"]) <= 2000
    assert "token=" not in calls[1]["content"]
    assert "Open your tracking app" in calls[1]["content"]
