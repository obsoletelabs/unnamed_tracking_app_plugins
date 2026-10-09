# Notifications: send one requested message

## Goal

Send a persistent host notification to the authenticated caller.

## Prerequisites

Declare `notifications.send` v1 and a permission rationale. Use a short declared
action; Recently Played Notifier demonstrates data-driven notification behavior.

## Minimal code

<!-- recipe: notifications -->
```python
from sdk.plugin_protocol import request

def run(values: dict) -> dict:
    return request("notifications.send", "notifications.send", {
        "title": "Report ready", "body": "Your requested report is available."
    })
```

The host owns records and delivery preferences. A local native toast is transient
browser feedback. External provider delivery is another contract, demonstrated
by Discord Delivery Provider; do not copy host retry/deduplication infrastructure.

## Test command

```sh
python -m pytest tests/test_feature_tutorials.py -k notifications
python -m pytest tests/test_help_button.py -k notification
```

## Expected result

The exact message is sent through the public gateway. Denial raises an actionable
SDK error. In a configured development host, the user sees one host notification;
delivery preferences may determine the channel.

## Common mistakes

Sending a notification every time an unchanged event is polled; treating a toast
as durable delivery; leaking a secret or another user's data in the body; returning
success after a denied gateway call.

## Protected provider layouts (Plugin API 1.1.2)

The maintained `official/discord-notifications` consumer registers
`official.discord-notifications.webhook` with `transport="discord_webhook"` using
`sdk.notifications.register_provider`. The renderer returns only a bounded layout,
for example `{"style":"embed","fields":["title","body","event_at","link"]}`.
The host selects the approved public/media projection and builds transport content.
Arbitrary strings, external links, raw embeds and mention overrides are rejected.

Users enroll encrypted concrete webhooks in the host's Account Notifications.
The plugin never receives destination credentials, verification proofs, other
users' addresses or a mutable delivery row. Core owns routing, attempts and retries;
current grants/installation/revision/preferences are rechecked before send.
Each webhook stays PUBLIC, even after explicit richer-media consent. Security
and recovery content is ineligible. The new plugin requests only provider
registration/delivery, without storage, data-reading or frontend permissions.

This is an explicit source preview until paired host lifecycle acceptance and
reviewed signed promotion. Legacy example credentials are not transferred.
Standalone consumer tests: `python -m pytest tests/test_discord_notifications.py -q`.
