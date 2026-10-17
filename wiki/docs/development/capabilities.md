# Capabilities and permissions

Capabilities describe public operations; permissions request authorization to
use them. Both references use a name and version. The host chooses effective
grants per installation and authenticated caller. Declarations alone authorize
nothing.

| Capability | Public behavior / working source |
| --- | --- |
| `games.read` | Library reads/metadata search: reports and curator |
| `plugin.settings` | `settings.get`: UI/API and curator |
| `plugin.storage` | Owned persistent key/value data: reports |
| `notifications.send` | Host notifications: notifier |
| `notifications.canonical`, `notifications.actions`, `notifications.urgency`, `notifications.templates.html` | Versioned story notifications (API 1.1.14), each explicit: [Story Notification Demo](notifications.md#versioned-story-notifications-plugin-api-1114) |
| `events.subscribe`, `tasks.background` | Polling and supervised work: Jellyfin |
| `documents.read` | Opaque scoped documents: Document Viewer |
| `backend.routes.plugin` | Authenticated namespaced JSON routes |
| `frontend.navigation.main`, `frontend.settings` | Declared host navigation/settings |
| `frontend.native` | Reviewed code in the host Vue/browser context |
| `network.outbound` | External destinations subject to runtime policy |

## Review a new permission

Explain the specific user benefit and data accessed in `rationale`. Add the exact
reference in `capabilities` and `permissions`; run validation and denied-grant
tests. Use separate read and destructive grants where the host supports them.
Do not request a broader permission as a fallback for denial.

Updates introducing new scopes must be previewed and approved. The current
release stays active while new scopes await review; automatic-update eligibility
cannot silently grant them. Frontend contributions are filtered by effective
grants and lifecycle state. [Security](../security/permissions.md) explains
default deny, host-owned risk and elevated consent.
