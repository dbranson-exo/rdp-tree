# RDP Tree — To-Do

## Bugs / Quirks

- [x] **Import RDG merge renames root group** — `_import_rdg` sets `self._root_group.name = imported.name` even when merging (not replacing). The root group name should only change on a full replace.
- [x] **Saved keychain passwords don't pre-fill RDP sessions** — `_encode_rdp_password` returns `""` (DPAPI is Windows-only). The password is retrieved from keychain and passed to `launch.launch()`, but is then silently dropped. Microsoft Remote Desktop will still prompt. Consider whether the save-password UI should be hidden or the limitation surfaced to the user.

## UX Improvements

- [x] **Drag-and-drop tree reordering** — currently only Move Up / Move Down in menus; drag-and-drop within and between groups would be much faster.
- [ ] **Recent files menu** — File menu has no "Open Recent" submenu; common for document-based apps.
- [ ] **Copy hostname to clipboard** — add "Copy Address" to the server right-click menu.
- [ ] **Connect keyboard shortcut visible in menu** — Return key works in the tree but the Connection → Connect menu item shows no accelerator label.
- [ ] **Delete group should show server count** — confirmation dialog should warn "Delete 'GroupName' and its 12 servers?"
- [ ] **"Reveal in Finder" for current file** — useful shortcut from File menu or status bar.

## Features

- [ ] **Reconnect to open session** — right-click a server to reconnect to an already-running Microsoft Remote Desktop session (bring the existing window to the front rather than launching a new connection).
- [ ] **Export to .rdg** — round-trip export back to RDCMan format for users who share files with Windows colleagues.
- [ ] **Duplicate server / group** — right-click "Duplicate" for quick cloning of similar entries.
- [ ] **Multi-select** — treeview uses `selectmode="browse"` (single select only); multi-select would enable batch delete/move.
- [x] **Auto-reopen last file** — option to reopen the last-used `.rdptree` file on launch.


## Packaging

- [x] **Create installer package** — bundle the app for distribution (e.g. a macOS `.app` via `py2app` or a `.dmg` installer).

## Code Quality

- [x] **`_move_selected` rebuilds entire tree** — calls `_refresh_tree()` on every Move Up/Down; fine for small trees but could be replaced with a targeted treeview `move()` call for larger connection sets.
