# Password Reset Routing Demo

**Demo only.** This executes a synthetic issue → notification → confirmation flow through the public Plugin API 1.1.2. It never changes passwords, creates accounts, grants membership or returns destination addresses/credentials. SMTP belongs to the host. There is no anonymous recovery endpoint or production reset/invite implementation.

The `issue` action registers `example.password-reset-notification-demo.requested`, stores an expiring token digest under the authenticated user's storage key and emits typed facts. Its result contains acceptance/notification identity and expiry, never the token. The core handles preferences, destination selection, trust, urgency, retries and SMTP rendering. Required trust is **SECURE**, purpose **recovery**. Recovery requires a verified external destination with explicit recovery opt-in, suitable transport and a separately reviewed notifications.sensitive grant; the inbox cannot receive this token.

With the plugin enabled and its declared permissions approved, call the authenticated host action API:

```http
POST /api/plugins/example.password-reset-notification-demo/actions/issue
Content-Type: application/json

{"values": {}}
```

Read the token from the eligible notification, then explicitly submit it:

```http
POST /api/plugins/example.password-reset-notification-demo/actions/confirm
Content-Type: application/json

{"values": {"token": "TOKEN_FROM_NOTIFICATION"}}
```

Both calls require the existing authenticated host session/API authorization. The sender cannot select another user/address. A new issue replaces the previous challenge; it expires after ten minutes. Confirmation consumes it sequentially and rejects another owner, replacement, expiry, alteration and sequential replay. Storage get/put is not a compare-and-swap transaction; concurrent confirmation is intentionally not a production authentication guarantee. No real authority is attached to the demo token.

Permissions are exactly source registration, notification emission and plugin storage, plus the separate critical notifications.sensitive grant. No full API, user enumeration, network access, host source imports or database access is requested. This is a protocol/action demonstration with no new frontend page; no screenshots apply.

From the companion repository root:

```sh
python -m pytest tests/test_notification_demos.py
python tools/check_source_layout.py
python tools/build_packages.py
```

Builds use the existing SDK/package format. Branch previews are unsigned and require explicit untrusted-package consent in the host. Signed main publication uses the existing demo signer; do not claim the source preview is a maintained official production auth plugin. Disable/uninstall retires source routing and queued work while the host retains notification history/preferences. Actual package/host acceptance is documented in the PR.
