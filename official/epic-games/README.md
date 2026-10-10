# Epic Games Library

Optional personal Epic game imports through **Plugin API 1.1.3**. Requires
[host PR38](https://github.com/obsoletelabs/unnamed_tracking_app_2/pull/38) or a later
host release implementing `games.import`. Older hosts reject this package during
compatibility review. This plugin uses the existing SDK v1.1.1 wire helper.
The host page/sign-in support is completed by
[host PR40](https://github.com/obsoletelabs/unnamed_tracking_app_2/pull/40).

## Connect and import

Install this plugin's `.utp` through Settings → Plugins, approve the declared
permissions and enable it. Open **Epic Games** in the sidebar or its plugin page.
Use **Sign in on Epic Games** to open Epic in a separate tab, leaving the plugin page open. Copy the one-time authorization code, JSON page or redirect URL from Epic, then return to the plugin tab and paste it into the password field. If the browser blocks the new tab, allow pop-ups for this site and retry.
The host opens the declared Epic sign-in destination outside the sandbox. Your password stays on Epic's site.
The code is cleared immediately after submission and is never saved in settings.

Choose **Import games**. Inventory paging, playtime, catalogue lookup and host
imports run as separate bounded steps. **Pause after this step**, closing the
page or a failed request retains the checkpoint. **Resume import** continues it.
**Start new inventory** deliberately replaces the current checkpoint. Disconnect
removes this user's saved tokens/checkpoint and keeps imported games.

Games use namespace + catalogue identity within the connected account. Similar
titles and another Epic account cannot adopt each other's games. Engine assets,
private sandboxes, DLC and digital extras are skipped. Catalogue requests group
up to 25 entries in one namespace; a missing catalogue response retains the batch
for retry. A repeated/invalid cursor, invalid record, incomplete page or safety
limit stops inventory before availability changes.

Successful imports respect the host's field locks, manual status, notes and
ratings. Playtime only increases; absent/unavailable playtime leaves known values
alone. When multiple launcher artifacts share a catalogue identity, the largest
reported artifact total is used to avoid counting duplicate platform entries.
Only a complete valid inventory can mark previously imported games unavailable.
No game is deleted. Trash or changed local identities are reported as conflicts.

Catalogue artwork and achievements are outside this import. Artwork can be
enriched through the host's existing game metadata tools. This initial plugin
has no automatic background sync, launching or Epic achievement conversion.

## Permissions and credentials

- `games.write`: current-user imports and availability/progress updates.
- `network.outbound`: mediated requests to fixed Epic HTTPS account/library/catalogue services.
- `plugin.storage`: private per-user rotating tokens, account-scoped known identities,
  short atomic leases and resumable checkpoints (16 MiB quota).
- `frontend.navigation.main`: an Epic Games sidebar page. Its packaged frontend
  runs in the host's sandbox and uses the existing appearance/action bridge.

Every operation derives the user from the trusted action context. No supplied
user/account/game ID selects another user's credentials or host records. A
per-user atomic lease serializes token rotation and import checkpoints; after
an interrupted worker the lease expires in 75 seconds. The replacement refresh
token is persisted before inventory/import work. Tokens and remote error bodies
are never returned in UI responses or logged by this plugin.

Private plugin storage uses the runtime's filesystem permissions and isolation;
it is **not encrypted at rest**. Protect the host data directory and backups.
Disconnect forgets this deployment's sign-in; use Epic account security to revoke
sessions on Epic itself when needed.

Epic's launcher library services are not a supported public player-library API
and can change. This implements the legacy import's launcher protocol through
the public gateway. Protocol references: [Epic authentication documentation](https://dev.epicgames.com/docs/web-api-ref/authentication)
and [Legendary's launcher client](https://github.com/legendary-gl/legendary/blob/master/legendary/api/egs.py).
The bundled launcher client ID/credential identifies the public launcher, not
any player's account. No Legendary source is copied or imported.

## Build, tests and distribution

From the plugin repository root:

```sh
python -m pytest tests/test_epic_games.py -q
python tools/check_source_layout.py
python tools/build_packages.py
python tools/distribution.py --root .validation --check-source --include-unreleased
python -m pytest
python -m mkdocs build --strict
```

Branch CI provides an **unsigned-dist** preview for review through the host's
explicit unsigned-install consent. Signed main publication uses the existing
protected official signing pipeline and immutable release history; no private
keys or regenerated historical artifacts belong in this change.

Provider DTO/failure tests use fixtures. Successful live-account import still
requires a user signing in through Epic and checking their own library. Package
installation/runtime/database validation and browser evidence are recorded
separately in the PR; fixtures alone do not certify live Epic availability.
