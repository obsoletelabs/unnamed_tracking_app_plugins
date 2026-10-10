# Classic UI

An official presentation-only theme that brings back the darker, denser and more boxy visual language of the classic Unnamed Tracking application.

## What it changes

- Much darker application surfaces and popovers.
- Compact, squared-off cards, controls, dialogs and menus.
- Darker sidebar/navigation surfaces with the classic orange accent treatment.
- More compact settings navigation, rows and cards.
- Older-style borders instead of large floating shadows and highly rounded surfaces.
- Dark, narrow scrollbars and the classic focus-ring treatment.

The theme intentionally **does not replace the sidebar, Settings routes, or any application functionality**. It styles the current host UI in place. If the visual result is close enough, this can remain a CSS-only restoration; if the remaining structural differences are too large, a later plugin can provide a deeper compatibility layer.

## Permissions

This package requests `frontend.native` solely so its stylesheet can be loaded into the host application. The native entrypoint contains no application logic and the stylesheet does not read, write, or transmit user data.

## Current scope

The first release concentrates on the visual foundations: darker dark mode, boxier components, sidebar/navigation styling, popups/dialogs, and settings surfaces. It deliberately does not attempt to recreate the old information architecture.

## Development

Build and validate it using the normal plugin repository distribution commands. Test it on desktop and narrow/mobile layouts, especially Settings, the profile/notification menus, dialogs and the sidebar.
