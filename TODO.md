# RDP Tree — To-Do

## Bugs / Quirks

- [x] **Import RDG merge renames root group** — `_import_rdg` sets `self._root_group.name = imported.name` even when merging (not replacing). The root group name should only change on a full replace.
- [x] **Saved keychain passwords don't pre-fill RDP sessions** — `_encode_rdp_password` returns `""` (DPAPI is Windows-only). The password is retrieved from keychain and passed to `launch.launch()`, but is then silently dropped. Microsoft Remote Desktop will still prompt. Consider whether the save-password UI should be hidden or the limitation surfaced to the user.

## UX Improvements

- [x] **Drag-and-drop tree reordering** — currently only Move Up / Move Down in menus; drag-and-drop within and between groups would be much faster.
- [x] **Recent files menu** — File menu has no "Open Recent" submenu; common for document-based apps.
- [x] **Copy hostname to clipboard** — add "Copy Address" to the server right-click menu.
- [x] **Connect keyboard shortcut visible in menu** — Return key works in the tree but the Connection → Connect menu item shows no accelerator label.
- [x] **Delete group should show server count** — confirmation dialog should warn "Delete 'GroupName' and its 12 servers?"
- [x] **"Reveal in Finder" for current file** — useful shortcut from File menu or status bar.

## Features

- [x] **Local folder sharing** — allow per-server selection of local folders to share in RDP sessions via the `drivestoredirect` RDP setting; folders should be configurable in the Server dialog and persisted in the `.rdptree` file.
- [x] **Reconnect to open session** — implemented as "Quick Connect": launches immediately using resolved credentials with no dialog (Cmd+Return / right-click menu). Windows App has no AppleScript API so focusing an existing window is not possible.
- [x] **Export to .rdg** — round-trip export back to RDCMan format for users who share files with Windows colleagues.
- [x] **Duplicate server / group** — right-click "Duplicate" for quick cloning of similar entries.
- [x] **Multi-select** — treeview uses `selectmode="browse"` (single select only); multi-select would enable batch delete/move.
- [x] **Auto-reopen last file** — option to reopen the last-used `.rdptree` file on launch.


## Packaging

- [x] **Create installer package** — bundle the app for distribution (e.g. a macOS `.app` via `py2app` or a `.dmg` installer).

## Code Quality

- [x] **`_move_selected` rebuilds entire tree** — calls `_refresh_tree()` on every Move Up/Down; fine for small trees but could be replaced with a targeted treeview `move()` call for larger connection sets.
