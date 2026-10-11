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
by Discord Notifications; do not copy host retry/deduplication infrastructure.

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

## Plugin-owned providers (API1.1.5)

The maintained `official/discord-notifications` consumer registers a PUBLIC webhook
using `transport="plugin"` and bounded configuration fields. The plugin stores its
credentials and owns HTTPS delivery through its declared network capability.
The core selects approved content, applies destination trust and per-webhook consent,
owns attempts/retries, and rechecks installation/grants/preferences before handoff.
PUBLIC webhooks cannot receive verification/security/recovery content.

The earlier `discord_webhook` protected-layout transport remains supported for
compatibility and the Chaos demo. Its host broker accepts approved field layouts
and keeps credentials outside plugin code. It is not the maintained webhook's
current transport. Existing credential/consent records are not transferred.

## Per-account possession proof (API1.1.6)

PRIVATE kinds declare `verification_supported`, `sensitive_supported` and
`recovery_supported`; declarations never assert SECURE trust. Core issues exact
destination/revision-bound ten-minute codes and verifies them itself. The independent
critical `notification_providers.sensitive` grant allows verification and approved
security/recovery content at handoff. Broad API/source/delivery grants do not imply it.
Plugins can read this content; explain this explicitly in permission review.
Recovery additionally requires a verified external destination and explicit user opt-in.

The Discord bot preview declares an independent per-account provider with server and
username fields. PRIVATE delivery works before proof. Core UUID/revisions map to exactly
one Discord account, with no broadcast fallback. Its legacy grouped provider/native
dashboard remain PRIVATE and retain existing links. See the [bot migration guide](https://github.com/obsoletelabs/unnamed_tracking_app_plugins/blob/main/official/discord-bot-notifications/README.md).
The paired host is [PR71](https://github.com/obsoletelabs/unnamed_tracking_app_2/pull/71).

## Scoped lifecycle replay (Plugin API 1.1.4)

Declare at least host contract 1.1.4 and explicitly request `notifications.lifecycle.read` with a clear permission rationale before calling `sdk.notifications.poll_lifecycle(cursor, limit=100)`. Neither notification sending, provider delivery, `events.subscribe` nor `api.full` implies the read grant. Requests cannot select another user, installation, provider or destination.

Only the authenticated user/current installation's own source notification lifecycle and own provider delivery states appear. Events contain opaque event/notification/delivery IDs, UTC occurrence time and status. They contain no message bodies, destination IDs, endpoint addresses, credentials, error strings or recovery authority. A source does not receive other providers' delivery history. Revocation stops reads; reinstall needs renewed permission and cannot reclaim the previous installation's feed.

Responses contain `events`, `cursor`, `has_more` and `resync_required`. Process and deduplicate stable event UUIDs before saving the next opaque cursor. A null cursor begins retained history. When `resync_required` is true, discard stale local assumptions and restart using the returned cursor; expired history cannot be reconstructed. This is a change feed rather than a state snapshot. Core publication occurs through the existing job loop in bounded batches; backlog may span multiple ticks.

The host's server-configurable default is 90 days (`NOTIFICATION_AUDIT_RETENTION_DAYS`), independently of inbox retention and longer-lived dedupe receipts. The core owns ordering, audit persistence, leases and delivery retries. These exported schemas are compared with the paired host's public models by `tools/check_host_contract.py`; plugins import only the SDK. This extension depends on host PR [#47](https://github.com/obsoletelabs/unnamed_tracking_app_2/pull/47).

## Failure simulation

The signed Notification Chaos Demo exercises the same protected renderer without a second transport API. Its settings select reversed approved fields, a bounded persistent first-render failure, repeated failure or an intentionally invalid layout. Exceptions enter core retry handling; invalid layouts are rejected before network I/O. Its ledger stores only opaque notification IDs, never delivery rows or credentials. See [examples](../examples/index.md#notification-chaos-demo) and `tests/test_notification_chaos_provider.py`.
