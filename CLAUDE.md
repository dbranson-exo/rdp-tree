# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the App

```bash
python3 rdptree.py                        # Launch the app
python3 rdptree.py connections.rdptree    # Open a specific file on launch
```

**Dependency:** `python-tk@3.14` must be installed (`brew install python-tk@3.14`). No pip packages required — stdlib only.

## Architecture

This is a single-process, tkinter-based desktop app. All modules are flat in the project root; there are no packages.

**Data flow:** `models.py` → `storage.py` (persist to disk) / `keychain.py` (passwords) / `launch.py` (connect) / `rdg_import.py` (import from RDCMan)

### Module responsibilities

| File | Role |
|---|---|
| `rdptree.py` | Entry point; handles CLI file argument |
| `app.py` | Entire UI: `RDPTreeApp` (main window), `ServerDialog`, `GroupDialog`, `ConnectDialog` |
| `models.py` | `Group` and `Server` dataclasses with `to_dict`/`from_dict` for JSON serialization |
| `storage.py` | Load/save `.rdptree` JSON files |
| `keychain.py` | macOS `security` CLI wrappers — passwords never stored in JSON |
| `rdg_import.py` | Parses RDCMan `.rdg` XML into the `Group`/`Server` model |
| `launch.py` | Generates a temp `.rdp` file and calls `open` to launch Microsoft Remote Desktop |

### Key design decisions

- **Passwords**: Never written to `.rdptree` files. Stored/retrieved via macOS Keychain using `security add-generic-password` with service name `RDPTree` and account key `rdptree:<server_uuid>`. The `Server.settings.has_saved_password` flag tracks whether a keychain entry exists.

- **Tree ↔ model mapping**: `RDPTreeApp` maintains two dicts — `_item_map` (treeview IID → `Group|Server`) and `_id_map` (model UUID → treeview IID). These are rebuilt on every `_refresh_tree()` call. The treeview is the source of truth for display order; model order is kept in sync via `Group.children` lists.

- **Credential inheritance**: When connecting, `_resolve_credentials(iid, server)` walks up the treeview parent chain to find the nearest `Group` with `default_username`/`default_domain` set, falling through to each ancestor if not yet resolved.

- **RDP launch**: macOS DPAPI is unavailable, so `password 51:b:` encoding is not possible. Passwords are passed via the credentials dialog at connect time; Microsoft Remote Desktop handles auth. The temp `.rdp` file is deleted after 5 seconds via a background shell.

- **`.rdptree` file format**: JSON with a top-level `root` key containing a serialized `Group` tree. Groups and servers are distinguished by a `"type"` field (`"group"` or `"server"`).

- **RDG import**: Supports RDCMan schema v2/v3. Credential inheritance from `<logonCredentials inherit="None">` is captured at the group level. Servers with `inherit="FromParent"` get empty username/domain (resolved at connect time).
