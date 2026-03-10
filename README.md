# RDP Tree

A macOS RDP connection manager with a tree view, inspired by [RDCMan](https://learn.microsoft.com/en-us/sysinternals/downloads/rdcman) for Windows.

Organize your RDP servers into groups, inherit credentials from parent groups, and launch sessions directly into Microsoft Remote Desktop — all from a familiar tree-view interface.

![RDP Tree screenshot placeholder](docs/screenshot.png)

## Features

- **Tree view** — organize servers into nested groups, just like RDCMan
- **Credential inheritance** — set a default username/domain on a group and all child servers inherit it automatically
- **macOS Keychain** — passwords are stored securely in the system Keychain, never in config files
- **Import from RDCMan** — open your existing `.rdg` files and pick up where you left off
- **Native RDP launch** — hands off to Microsoft Remote Desktop via `.rdp` files

## Prerequisites

- macOS (Apple Silicon or Intel)
- Python 3.14 via Homebrew
- Tkinter for Python 3.14
- [Microsoft Remote Desktop](https://apps.apple.com/us/app/microsoft-remote-desktop/id1295203466) (free, from the Mac App Store)

## Installation

1. **Install Homebrew** if you haven't already:
   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```

2. **Install Python and Tkinter:**
   ```bash
   brew install python@3.14
   brew install python-tk@3.14
   ```

3. **Clone this repository:**
   ```bash
   git clone https://github.com/yourname/rdp-tree.git
   cd rdp-tree
   ```

No additional Python packages are required — the app uses the standard library only.

## Usage

```bash
python3 rdptree.py
```

To open a saved connection file directly:
```bash
python3 rdptree.py ~/connections.rdptree
```

### Getting started

1. **Add a group** — `Edit > Add Group` or `Cmd+Shift+G`. Give it a name and optionally set a default username and domain that all servers in the group will inherit.
2. **Add a server** — select a group, then `Edit > Add Server` or `Cmd+Shift+N`. Fill in the host/IP, display name, and credentials (or leave credentials blank to inherit from the group).
3. **Connect** — double-click a server, press `Return`, or use `Connection > Connect`. If no password is saved, you'll be prompted; tick **Save to Keychain** to avoid being asked again.
4. **Save your connections** — `Cmd+S` saves to a `.rdptree` file that you can reopen later.

### Importing from RDCMan

`File > Import RDG...` — select your `.rdg` file. You can merge it into an existing tree or replace the current one. Group structure, server names, display names, and credential assignments are all preserved.

### Keyboard shortcuts

| Action | Shortcut |
|---|---|
| New file | `Cmd+N` |
| Open file | `Cmd+O` |
| Save | `Cmd+S` |
| Add Group | `Cmd+Shift+G` |
| Add Server | `Cmd+Shift+N` |
| Edit selected | `Cmd+I` |
| Connect | `Return` |
| Delete selected | `Delete` / `Backspace` |

### Connection file format

Connections are saved as `.rdptree` files — plain JSON that is easy to back up, version-control, or share with colleagues. **Passwords are never written to this file**; they are stored exclusively in the macOS Keychain.

## Project structure

```
rdptree.py      — entry point
app.py          — all UI (main window + dialogs)
models.py       — Group and Server data classes
storage.py      — load/save .rdptree JSON files
keychain.py     — macOS Keychain integration
rdg_import.py   — RDCMan .rdg XML importer
launch.py       — RDP session launcher
```

## License

MIT
