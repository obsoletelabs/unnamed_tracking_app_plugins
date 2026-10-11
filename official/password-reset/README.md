# Password Reset

Maintained optional password recovery integration for host Plugin API 1.1.7. This is a functional account flow; the synthetic example remains a separate demonstration.

## Setup

Install the signed official package and explicitly grant the critical **auth.password_reset** permission globally. Open **Administration → Password recovery**, choose a link lifetime (600–3600 seconds, default 1200), and click **Enable or save recovery**. Disable invalidates outstanding links; installation alone does not enable public recovery.

Each user must configure an external notification destination, verify it and separately enable recovery delivery. SMTP is built into the host. A plugin destination must declare verification/security/recovery support and hold the independent high-risk provider grant. The authenticated inbox and browser push cannot carry recovery links. Normal routing preferences and administrator restrictions apply; there is no direct SMTP bypass.

## Use

The sign-in page shows **Forgot your password?** when this contribution is active. Request with your app username or configured app email. The acknowledgement is the same for unknown, disabled, SSO and ineligible accounts. Open the delivered link, choose a password satisfying the server policy and confirm. All browser sessions are revoked; **API keys remain active**. Sign in normally afterward.

Links expire, are single-use and are bound to the current account/password/email, installation and configuration revision. Opening a link never consumes it. Bearer material uses a URL fragment and is removed from the displayed address. Disabling/uninstalling or withdrawing the grant blocks pending delivery/redemption; reinstall cannot reclaim old links.

The host stores encrypted delivery material only until consumption/expiry and never puts it in inbox content or lifecycle audit. This plugin stores only its activation/lifetime configuration and never receives reset tokens, passwords, SMTP credentials or account rows.

## Testing

Run `pytest tests/test_official_password_reset.py` and the paired host recovery suite. Actual signed-package installation and the host request/link/redemption workflow are required before release. Temporary SMTP capture is suitable for local acceptance; no production SMTP account is required.

Startup uses auth_flows.password_reset.restore to resume only an already-active matching installation and definition. Withdrawal or reinstallation requires explicit activation; regranting permission cannot revive an old reset credential.

Configuration is under Settings → Administration → Account security → Password recovery. The page shows live **Account recovery enabled/disabled** from the host. Saved preferences do not imply availability. Requires API1.1.10 and explicit settings placement grants. All SMTP mail now uses the host shared HTML design with a plain alternative.
