# Story Notification Demo

Demonstrates the versioned notification contract of Plugin API **1.1.14**: one event type with a
lifecycle (`available` → `installed` or `failed`), typed facts, a typed host-authorised action and a
Markdown render contribution. It needs a host that supports Plugin API 1.1.14 or later; check
`sdk.notification_stories.negotiate_contract()` before relying on it.

The `announce`, `finish` and `fail` actions register the type and publish the matching story event
for the authenticated user. Replays of the same version and phase are no-ops, and moving from
`available` to `installed` updates the same story instead of creating a second notification. The
host decides recipients, destinations, trust, timing, retention and dispatch; the plugin cannot
name any of them and sends no HTML, scripts or credentials.

The `available` event offers an `acknowledge` action. The host runs it only after rechecking the
account, the live story, the installation and the grants, then calls this plugin with the private
`_notification_context` (`story_action_context` validates it) and the declared typed input. The
handler stores the acknowledgement for that user and returns a short message.

Permissions are exactly source registration, canonical publication, notification actions and plugin
storage. Urgency, HTML templates and sensitive content are not requested.

```sh
python -m pytest tests/test_notification_story_contract.py
python tools/check_source_layout.py
python tools/build_packages.py
```

Branch previews are unsigned and need explicit untrusted-package consent in the host. Disabling or
uninstalling the plugin retires the type and its queued work while the host keeps notification
history.
