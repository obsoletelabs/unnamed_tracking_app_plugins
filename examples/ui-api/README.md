# UI and API Example

A small Plugin API v1 reference with a real declarative page, a `display_mode`
settings section and a **Read library** action returning up to 50 current-user
games. It requests `games.read`, `plugin.settings` and `frontend.navigation.main`.
It also requests `tasks.background` for a **Library summary** job in Administration
→ Tasks. The schedule starts off, supports an interval and Run now, and uses the
plugin's existing background administrator identity. Its handler returns only a
bounded public summary; it does not read every user's library or opt anyone into
personal background subscriptions. Withdraw either background or library access
to pause the job. Updates and ordinary reinstall retain its schedule.
The host owns permission classification and supplies authenticated gateway context.
The entrypoint reports ready and remains supervised instead of exiting after
startup requests. No plugin JavaScript is loaded by the native host.

Use it as the minimal structure in the [author guide](../../wiki/docs/plugin-author-guide.md).
Build/test with `pytest` and `python tools/build_packages.py`; inspect the isolated
`.validation/` distribution. New packages include this README, an icon, tags and
release-specific update metadata. Release signing requires a registered publisher.
