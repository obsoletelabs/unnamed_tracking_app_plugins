# Notification Chaos Demo

**Demonstration only; unsuitable for production delivery.** This intentionally
unreliable provider exercises the public Plugin API 1.1.2 protected renderer.
It is independent of the maintained official Discord Notifications provider.
This source is unreleased until reviewed signed promotion; preview packages are
available through the existing builder.

Install, review its four exact grants, and enable it. Choose a simulation mode
in Plugin Manager settings, then explicitly enroll a webhook for **Notification
Chaos Demo** in Account Notifications. Use the host's destination test button.
Successful modes really send to the configured Discord webhook; use a test
channel. No credential is entered into or returned to this plugin.

| Mode | Behavior |
| --- | --- |
| Backwards embed (default) | Approved link, timestamp, body and title in backwards order |
| Backwards plain message | The same field order in plain text |
| Fail first render | Record an opaque ID, raise once, then allow core retry to render |
| Fail every render | Raise every time; core eventually records permanent failure |
| Invalid layout | Return an unsupported style; core rejects it before transport |

The host still selects public versus explicitly consented media fields. Webhooks
remain PUBLIC and cannot receive private/security/recovery content. The renderer
cannot append private text, return raw embeds, request credentials or set delivery
state. It declares no network, game-reading or sensitive-content permission.

Only the most recent 100 opaque notification UUIDs are retained in plugin-owned
simulation storage. This is a teaching ledger, not an authoritative attempt
counter: eviction, explicit data purge and concurrent renders may simulate another
first failure. Reinstall does not reclaim old endpoints or replay notifications.
Core leases, retries, dedupe, preferences and destination lifecycle remain authoritative.

```sh
python -m pytest tests/test_notification_chaos_provider.py -q
python tools/build_packages.py
python tools/check_reference_lifecycle.py --host-root /path/to/host
```

Package tests cover exact grants, isolation, schema rejection, bounded persistent
simulation, temporary startup recovery and standalone imports. Real-worker
lifecycle acceptance installs an independently signed package; it does not claim
live Discord delivery. Production notification behavior must not depend on this
demo being installed.
