# Plugin-owned pages and browser UI

## Goal and prerequisites

Expose a bounded Python action on a page. Start from Library Summary; keep its
manifest/action/page IDs consistent and approve the action's domain grant.

Choose the smallest UI mode that supports your behavior:

| Mode | Source | Authority |
| --- | --- | --- |
| Declarative UI | `ui.json` sections, actions, tables, dialogs, pages | Host renders and filters declared contributions |
| Sandboxed bundle | `frontend/index.html` and local assets | Opaque iframe and approved bridge |
| Native frontend | `native/` module | Privileged host Vue/browser context; explicit review |

The [first-plugin tutorial](../getting-started/first-plugin.md) creates a real
declarative page. Pages refer to existing action/settings/table/dialog IDs;
`pages[].components` is not v1. Every action needs an executable `module:function`
handler. Keep manifest and UI IDs synchronized.

## Add a sandboxed frontend

Declare `frontend: {"entry": "frontend/index.html"}` and bundle local HTML/JS/CSS
dependencies. Use the existing `postMessage` bridge (`plugin.run-action`,
`plugin.save-settings`, `plugin.store-secret`) demonstrated by the shipped
frontends. Correlate responses, bound timeouts and handle denial/malformed replies.
The iframe does not receive arbitrary host DOM, cookie or database access.

Document Viewer demonstrates authenticated inline asset delivery with
`frontend.inline_assets: true`, contextual `document_id`/`game_id`, and
`plugin.download-document`. This uses the host's existing authorized inlining
and bridge; it does not weaken the opaque sandbox or grant arbitrary downloads.
The UI Playground's pinned Vue CDN is a teaching limitation; bundle dependencies
for independent production publication.

Test actual assets in a browser, including missing bridge replies, stale
responses, denied grants, unsupported content and disable/unmount cleanup.
[Screenshots](../assets/screenshots/index.md) distinguish component fixtures
from authenticated host workflow evidence.

## Minimal declarative configuration

```json
{"id": "summary", "title": "Library Summary", "actions": ["summarize"]}
```

This is one `pages[]` element in `ui.json`, referring to the existing `summarize`
action. List `summary` in `manifest.ui.pages`. The host renders the action button
and presents the authenticated handler's result.

## Test command

```sh
python -m pytest tests/test_author_tutorial.py tests/test_native_packages.py
npm test
```

## Expected result

The tutorial's real UI/action/package contract passes. Browser tests execute
Document Viewer's actual assets with fixture bridge replies, including errors.
In the host, Library Summary appears in the detail panel and returns a result;
denied/disabled actions cannot execute.

## Common mistakes

Unsupported `pages[].components`; missing bundled assets; assuming iframe
cookies/DOM access; uncorrelated bridge replies; reporting fixture output as
authenticated permission enforcement evidence.


### Host navigation in opaque frames

The shared `sdk/frontend_appearance.js` also keeps host Alt navigation available when your frontend frame has focus. It reads the host's `navigation_shortcuts` list and sends `plugin.shortcut` with the selected key. Editing fields, composition, repeated keys, AltGraph, competing modifiers and handled events are ignored. The host maps only its current known keys and retains dialog/command-palette guards; this grants no arbitrary navigation or privileged action. Plugins without this additive snapshot field keep their previous behavior.

An optional `global_shortcuts` list also advertises active default `help` (`?`)
and `search` (Ctrl/Cmd+K) bindings. The additive `keyboard_shortcuts` snapshot
contains the current remapped combinations and IDs. The SDK prefers that list,
including an empty list when shortcuts are disabled. The host rechecks every
forwarded binding before dispatch. Host dialogs open without leaving the plugin
page and preserve focus and dismissal behavior. See [Keyboard shortcuts](shortcuts.md)
for native registration, declarative bindings, personal overrides and conflicts.

The bundled appearance helper accepts the compatible 1.1.0, 1.1.1 and 1.1.2 snapshots for both the initial response and later theme updates. It still accepts messages only from its host parent and applies only bounded cosmetic tokens. Unknown contract versions are ignored.
