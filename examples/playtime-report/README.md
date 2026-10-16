# Playtime Report

A real, small plugin rather than a protocol stub.

The **Refresh report** action asks the host for the signed-in user's game library,
calculates total playtime and the ten most-played games, returns the result and
persists it under `users/<host-injected-user-id>/latest-report`. It requests
`games.read`, `plugin.storage` and `frontend.navigation.main` for its sidebar page.
The supervised entrypoint reports ready and remains alive; library reads occur
on user action, not on every process restart.

It demonstrates a normal plugin pattern:

1. request an approved core capability;
2. perform application-specific logic entirely inside the plugin;
3. persist only plugin-owned data;
4. return a useful action result while the host supervises the worker.

It does not implement game storage, lifecycle management, or the plugin gateway itself.

Build/test and release instructions are in the [author guide](../../wiki/docs/plugin-author-guide.md).
The package includes this README, release-specific policy/tags and an icon.
