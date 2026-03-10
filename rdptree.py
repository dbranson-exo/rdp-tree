#!/usr/bin/env python3
"""RDP Tree — RDCMan-style connection manager for macOS."""
import sys
import tkinter as tk
from app import RDPTreeApp


def main():
    root = tk.Tk()
    app = RDPTreeApp(root)

    # Open a file passed as a command-line argument
    if len(sys.argv) > 1:
        path = sys.argv[1]
        try:
            import storage
            app._root_group = storage.load(path)
            from pathlib import Path
            app._current_file = Path(path)
            app._refresh_tree()
            app._update_title()
        except Exception as exc:
            from tkinter import messagebox
            messagebox.showerror("Open Error", f"Could not open file:\n{exc}")

    app.run()


if __name__ == "__main__":
    main()
