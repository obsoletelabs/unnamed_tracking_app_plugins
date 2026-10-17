# Metadata Curator

A configurable metadata-search demo with real application logic.

The **Search** action reads its `query` setting, calls the host metadata API,
normalizes returned records, returns them and stores a compact snapshot under
`users/<host-injected-user-id>/latest-search`. It requests `games.read`,
`plugin.settings`, `plugin.storage` and `frontend.navigation.main`. Its declarative
page has a real settings section and executable handler. The supervised entrypoint
reports ready and stays alive. It demonstrates useful behavior without importing
or duplicating application metadata-provider code.

Build/test and release instructions are in the [author guide](../../wiki/docs/plugin-author-guide.md).
Each new package carries its own README, tags, icon and automatic-update policy.
