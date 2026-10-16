# Epic Games Library

Optional personal Epic game imports through **Plugin API 1.1.11**. Requires a host
that implements `games.import`, connection sync actions and personal scheduled
tasks. Older hosts reject this package during compatibility review;
use an earlier Epic release on a host that predates 1.1.11. This plugin uses the existing SDK v1.1.1 wire helper.
The host page/sign-in support is completed by
[host PR40](https://github.com/obsoletelabs/unnamed_tracking_app_2/pull/40).

## Connect and import

Install this plugin's `.utp` through Settings → Plugins, approve the declared
permissions and enable it. Open Settings → Account → Connections, where **Epic Games**
is listed with its connection status. Choose **Connect** (or **Manage** once
connected) to open the plugin page in a popup. The page is also reachable at its
plugin route, but it no longer adds a sidebar entry.
The popup uses the host's appearance and spacing, with an account summary and
import controls. Expand **Use your regular browser**, then use **Copy sign-in link** to open Epic in your regular browser while leaving the
app open. If clipboard access is unavailable, copy the selected link manually.
Alternatively, use **Sign in on Epic Games**. The action is declared as external navigation, so
the host validates Epic's returned HTTPS destination and opens it in a new tab,
leaving this popup open; the sandboxed plugin does not open a popup itself.
After signing in, Epic shows a page of text. Select all of it, copy it and paste
it into the code field: pasting the whole page connects without another click.
The one-time authorization code, its JSON page, a single copied JSON line or the
redirect URL are all accepted. Hosts that predate new-tab handling, or a browser
that blocks the tab, navigate the host tab instead; then use browser Back and
reopen **Connections → Epic Games**. No popup permission is needed. Your
password stays on Epic's site. The code is cleared immediately after submission
and is never saved in settings.

If Epic later rejects the saved sign-in (for example after a password change),
the popup shows the code field again. **Replace sign-in** does the same at any
time. The existing connection stays until Epic accepts the new code; an
accepted replacement then starts a fresh import checkpoint, and games already
imported stay in your library.

Launcher access/refresh tokens are validated independently from the 32-character
account ID and bounded to 8 KiB. Hosts must support authorization headers larger
than the original 2 KiB limit; older hosts need the companion token-header fix
before an import can use these tokens. Failed replacement sign-ins retain an
existing connection and never show token values in errors.

Positive, finite access-token lifetimes from Epic are accepted, including lifetimes
longer than one day. The plugin schedules refresh at the shorter of that lifetime
and one day, so a longer provider lifetime does not delay local token rotation.
Malformed expiry values retain an existing connection.

Choose **Import games**. Inventory paging, playtime, catalogue lookup and host
imports run as separate bounded steps. **Pause after this step**, closing the
page or a failed request retains the checkpoint. **Resume import** continues it.
**Start new inventory** deliberately replaces the current checkpoint. Disconnect
removes this user's saved tokens/checkpoint and keeps imported games.

The popup follows Steam's host dialog sizing and shared appearance. Disconnected
accounts show sign-in controls; import controls appear after connecting.
On Games, **Sync / import → Sync Epic Games** starts or resumes the same
import flow. The menu does not add a second connection page.

For automatic imports, open **Account → Background tasks → Epic Games autosync**.
Approve the declared `tasks.background` access and enable your own schedule; it
starts off and normally runs daily. Intervals can range from 5 minutes to 1 week.
Each run advances one bounded checkpoint; incomplete work requests the next step
after 60 seconds, even with the page closed. Completion restores your chosen interval.
Disabling autosync stops queued steps. Manual and automatic imports share the same
per-user lease, tokens, checkpoint and preservation rules; another user's schedule
cannot adopt your Epic account or change your library.

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
