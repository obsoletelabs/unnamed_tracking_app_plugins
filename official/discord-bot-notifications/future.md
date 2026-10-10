# Discord Bot Notifications — Future Work

This roadmap is intentionally separate from the first working notification path. The current priority is reliable private DM delivery through the host notification dispatcher; none of these items should block that.

## Phase 1 — Finish destination lifecycle and delivery reliability

- Keep account linking, host destination enrollment, provider enablement, and per-notification-type routing as separate, clearly explained steps.
- Make removing a host destination invoke the declared retirement action and keep account unlinking consistent with active host routes.
- Add explicit tests for token rotation, bot removal from the configured server, a user disabling DMs, a revoked provider grant, and a plugin restart.
- Handle Discord rate limits with bounded retry/backoff and respect retryability returned by the host delivery dispatcher.
- Record safe delivery diagnostics (attempt time, result category, and correlation ID) without logging bot tokens, verification codes, message contents, or full Discord responses.
- Ensure a successful direct test DM is clearly distinguished from a successful host-dispatched notification.

## Phase 2 — Better operational diagnostics

- Add a compact status view for token validity, configured server access, last successful Discord API request, last test DM, and last host delivery.
- Show actionable, sanitized reasons for common failures: invalid/revoked token, missing bot membership, insufficient permissions, unavailable DM, missing Server Members Intent, and Discord rate limiting.
- Keep the token write-only and never expose it through UI state, diagnostics, logs, or error payloads.

## Phase 3 — Real-time presence prototype

- First verify that the plugin runtime can support a persistent Discord Gateway WebSocket without violating runtime lifecycle and resource limits.
- Start with online/idle/do-not-disturb/offline status only. Keep unknown and stale distinct from offline.
- Request the privileged GUILD_PRESENCES intent only when enabled by the server administrator and available for the application.
- Implement heartbeat handling, reconnect/resume, intent-revocation detection, bounded per-member caching, cache expiry, and restart recovery before showing presence in the UI.
- Keep presence disabled by default and explain exactly what is collected and who can see it.

## Phase 4 — Optional activity details

- Only after status-only presence is stable, consider activities and client/device status as a separate opt-in feature.
- Make activity collection independently switchable, minimize retention, clear cached details when disabled or unlinked, and avoid storing activity history by default.
- Never use presence or activity as an authentication signal or as proof that a user can receive private messages.

## Explicit non-goals for the first release

- No Discord presence polling as a substitute for Gateway events.
- No assumption that an online status guarantees DM delivery.
- No security, account-recovery, or other SECURE notification routing through Discord DMs.
- No unbounded member cache, permanent activity history, or sensitive Discord payloads in logs.
