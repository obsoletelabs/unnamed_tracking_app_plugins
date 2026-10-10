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
Use **Sign in on Epic Games**. The action is declared as external navigation, so
the host validates Epic's returned HTTPS destination and navigates the host tab;
the sandboxed plugin does not open a popup itself. After signing in, use browser
Back to return to the plugin page, then paste the one-time authorization code,
JSON page or redirect URL into the password field. No popup permission is needed.
The host opens the declared Epic sign-in destination outside the sandbox. Your
password stays on Epic's site. The code is cleared immediately after submission
and is never saved in settings.

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
