#!/usr/bin/env python3
"""RDP Tree — RDCMan-style connection manager for macOS."""
import sys
import tkinter as tk
from pathlib import Path
from app import RDPTreeApp
import prefs
import storage


def main():
    root = tk.Tk()
    app = RDPTreeApp(root)

    # Determine which file to open: CLI arg takes priority, then last-used file
    if len(sys.argv) > 1:
        open_path = Path(sys.argv[1])
    else:
        open_path = prefs.get_last_file()

    if open_path:
        try:
            app._root_group = storage.load(open_path)
            app._current_file = open_path
            app._refresh_tree()
            app._update_title()
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Open Error", f"Could not open file:\n{exc}")

    app.run()


if __name__ == "__main__":
    main()
