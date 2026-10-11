# User Invites

Maintained official administrator email-invite integration for host Plugin API **1.1.8**.

Configure built-in SMTP in Administration > Notifications. Install this plugin, explicitly approve `auth.user_invites` and enable invitations under Settings > Administration > Account security > User invitations. Choose a link lifetime between one hour and seven days (one day by default). Use Invite user on Administration > Users to send to the intended recipient email address; do not create an account first.

The host queues a PRIVATE bootstrap email through the existing notification dispatcher. It uses the configured public app URL, falling back to the issuing administrator's signed-in app address. An allowed secure SMTP transport is required; explicit local-IP/development plaintext exceptions follow the built-in policy. Routing restrictions still apply. The destination exists only for that invitation and cannot receive ordinary or security notices.

The invitee opens the emailed link and chooses a username/password. Opening the link does not consume it. POST acceptance creates an active normal account, never an administrator, and requires normal sign-in afterward. The email address cannot be changed by the acceptance payload. Possession of the invite does not create a verified notification destination automatically.

The administrator page lists the current installation's last 100 invites, expiry and delivery state, and can revoke outstanding links. Sending another invite to the same address retires the earlier link. Requests are bounded to 100 per administrator/day and five per recipient/day, with a global 1,000-row pending capacity. Expired pre-account records are cleaned after a day. Disabling, uninstalling or revoking the grant invalidates old links; reinstall requires explicit activation.

The plugin owns activation and its admin UI. It uses only the public gateway and receives its own invitation email/status records. The host owns tokens, account/password validation, creation, SMTP credentials and delivery retries. Passwords and bearer links never pass through plugin code. Existing registered emails are rejected to the administrator.

This is a usable flow, separate from the synthetic `example.user-invite-notification-demo` routing demonstration.

Configure activation/lifetime under Settings → Administration → Account security → User invitations. On Administration → Users, **Invite user** opens the plugin dialog to send and review invitations. Requires API1.1.10 and reviewed administrative/settings grants. The host renders invitation mail as HTML plus text.
