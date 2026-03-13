"""Main application window for RDP Tree."""
from __future__ import annotations
import subprocess
import tkinter as tk
import uuid
from tkinter import ttk, messagebox, filedialog, simpledialog
from pathlib import Path
from typing import Optional

import keychain
import launch
import prefs
import rdg_export
import rdg_import
import storage
from models import Group, Server, ServerSettings, TreeNode

RESOLUTIONS = [
    ("Full Screen", 0, 0, True),
    ("3840 x 2160", 3840, 2160, False),
    ("2560 x 1440", 2560, 1440, False),
    ("1920 x 1080", 1920, 1080, False),
    ("1680 x 1050", 1680, 1050, False),
    ("1440 x 900", 1440, 900, False),
    ("1280 x 800", 1280, 800, False),
    ("1280 x 720", 1280, 720, False),
    ("1024 x 768", 1024, 768, False),
]
RESOLUTION_LABELS = [r[0] for r in RESOLUTIONS]


def _resolution_label(server: Server) -> str:
    s = server.settings
    if s.fullscreen:
        return "Full Screen"
    for label, w, h, _ in RESOLUTIONS:
        if w == s.width and h == s.height:
            return label
    return f"{s.width} x {s.height}"


class RDPTreeApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("RDP Tree")
        self.root.geometry("960x640")
        self.root.minsize(700, 450)

        self._current_file: Optional[Path] = None
        self._modified = False
        self._root_group = Group(name="My Connections")
        # Maps treeview IID -> model object (Group or Server)
        self._item_map: dict[str, TreeNode] = {}
        # Maps model ID -> treeview IID
        self._id_map: dict[str, str] = {}
        # Pending after() ID for debounced search
        self._search_after_id: Optional[str] = None

        self._setup_icons()
        self._setup_menu()
        self._setup_ui()
        self._setup_keybindings()
        self._setup_drag_and_drop()

        # macOS quit handler
        try:
            self.root.createcommand("tk::mac::Quit", self._quit)
        except Exception:
            pass

        self._refresh_tree()
        self._show_welcome()

    # ------------------------------------------------------------------
    # Icons
    # ------------------------------------------------------------------

    def _setup_icons(self):
        """Create simple colored block icons for groups and servers."""
        # Group icon: yellow/orange folder-ish rectangle
        self._icon_group_closed = self._make_icon("#F5A623", "#C8840A")
        self._icon_group_open = self._make_icon("#F7C15A", "#C8840A")
        # Server icon: blue monitor-ish rectangle
        self._icon_server = self._make_icon("#4A90D9", "#1E5FA8")

    def _make_icon(self, fill: str, border: str) -> tk.PhotoImage:
        img = tk.PhotoImage(width=16, height=16)
        # Fill entire image
        img.put(fill, to=(1, 1, 15, 15))
        # Border
        for x in range(0, 16):
            img.put(border, to=(x, 0, x + 1, 1))
            img.put(border, to=(x, 15, x + 1, 16))
        for y in range(0, 16):
            img.put(border, to=(0, y, 1, y + 1))
            img.put(border, to=(15, y, 16, y + 1))
        return img

    # ------------------------------------------------------------------
    # Menu
    # ------------------------------------------------------------------

    def _setup_menu(self):
        menubar = tk.Menu(self.root)

        # File
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="New",         command=self._new,        accelerator="Cmd+N")
        file_menu.add_command(label="Open...",     command=self._open,       accelerator="Cmd+O")
        self._open_recent_menu = tk.Menu(file_menu, tearoff=0,
                                         postcommand=self._rebuild_recent_menu)
        file_menu.add_cascade(label="Open Recent", menu=self._open_recent_menu)
        file_menu.add_command(label="Save",        command=self._save,       accelerator="Cmd+S")
        file_menu.add_command(label="Save As...",  command=self._save_as)
        file_menu.add_separator()
        file_menu.add_command(label="Reveal in Finder", command=self._reveal_in_finder)
        file_menu.add_separator()
        file_menu.add_command(label="Import RDG...", command=self._import_rdg)
        file_menu.add_command(label="Export RDG...", command=self._export_rdg)
        menubar.add_cascade(label="File", menu=file_menu)

        # Edit
        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Add Group...",  command=self._add_group,  accelerator="Cmd+Shift+G")
        edit_menu.add_command(label="Add Server...", command=self._add_server, accelerator="Cmd+Shift+N")
        edit_menu.add_separator()
        edit_menu.add_command(label="Edit...",   command=self._edit_selected,   accelerator="Cmd+I")
        edit_menu.add_command(label="Delete",    command=self._delete_selected, accelerator="Delete")
        edit_menu.add_separator()
        edit_menu.add_command(label="Move Up",   command=lambda: self._move_selected(-1))
        edit_menu.add_command(label="Move Down", command=lambda: self._move_selected(1))
        menubar.add_cascade(label="Edit", menu=edit_menu)

        # Connection
        conn_menu = tk.Menu(menubar, tearoff=0)
        conn_menu.add_command(label="Connect",       command=self._connect_selected,       accelerator="Return")
        conn_menu.add_command(label="Quick Connect", command=self._quick_connect_selected, accelerator="Cmd+Return")
        menubar.add_cascade(label="Connection", menu=conn_menu)

        self.root.config(menu=menubar)

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------

    def _setup_ui(self):
        # Main paned window
        self._paned = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        self._paned.pack(fill=tk.BOTH, expand=True)

        # ---- Left panel: tree ----
        left = ttk.Frame(self._paned)
        self._paned.add(left, weight=1)

        # Search
        search_outer = ttk.Frame(left)
        search_outer.pack(fill=tk.X, padx=6, pady=(6, 2))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_changed)
        search_entry = ttk.Entry(search_outer, textvariable=self._search_var)
        search_entry.pack(fill=tk.X)
        search_entry.insert(0, "Search...")
        search_entry.bind("<FocusIn>",  lambda e: self._search_focus_in(search_entry))
        search_entry.bind("<FocusOut>", lambda e: self._search_focus_out(search_entry))
        self._search_placeholder = True

        # Tree + scrollbar
        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(0, 6))

        self._tree = ttk.Treeview(tree_frame, selectmode="extended", show="tree")
        vsb = ttk.Scrollbar(tree_frame, orient=tk.VERTICAL, command=self._tree.yview)
        self._tree.configure(yscrollcommand=vsb.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        # Tags
        self._tree.tag_configure("group",  font=("Helvetica", 13, "bold"))
        self._tree.tag_configure("server", font=("Helvetica", 13))

        # Events
        self._tree.bind("<<TreeviewSelect>>",  self._on_tree_select)
        self._tree.bind("<Double-Button-1>",   self._on_double_click)
        self._tree.bind("<Button-2>",          self._on_right_click)
        self._tree.bind("<Button-3>",          self._on_right_click)
        self._tree.bind("<<TreeviewOpen>>",    self._on_tree_open)
        self._tree.bind("<<TreeviewClose>>",   self._on_tree_close)

        # ---- Right panel: properties ----
        right = ttk.Frame(self._paned)
        self._paned.add(right, weight=2)
        self._setup_detail_panel(right)

        # Status bar
        self._status_var = tk.StringVar(value="Ready")
        ttk.Label(self.root, textvariable=self._status_var,
                  relief=tk.SUNKEN, anchor=tk.W, padding=(8, 2)
                  ).pack(fill=tk.X, side=tk.BOTTOM)

        self._paned.after(10, lambda: self._paned.sashpos(0, 280))

    def _setup_detail_panel(self, parent: ttk.Frame):
        """Build the right-hand details/properties panel."""
        self._detail_frame = ttk.Frame(parent, padding=16)
        self._detail_frame.pack(fill=tk.BOTH, expand=True)

        # Welcome / empty state shown initially; replaced on selection
        self._welcome_label = ttk.Label(
            self._detail_frame,
            text="Select a server or group from the tree.",
            foreground="gray",
            font=("Helvetica", 14),
            anchor="center",
        )
        self._welcome_label.pack(expand=True)

        # Server detail widgets (hidden until a server is selected)
        self._server_frame = ttk.Frame(self._detail_frame)

        # Title row
        title_frame = ttk.Frame(self._server_frame)
        title_frame.pack(fill=tk.X, pady=(0, 4))
        self._detail_name_var = tk.StringVar()
        ttk.Label(title_frame, textvariable=self._detail_name_var,
                  font=("Helvetica", 18, "bold")).pack(side=tk.LEFT)

        self._detail_host_var = tk.StringVar()
        ttk.Label(self._server_frame, textvariable=self._detail_host_var,
                  foreground="gray", font=("Helvetica", 12)).pack(anchor=tk.W)

        ttk.Separator(self._server_frame, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=10)

        # Details grid
        grid = ttk.Frame(self._server_frame)
        grid.pack(fill=tk.X)
        self._detail_labels: dict[str, tk.StringVar] = {}
        for i, key in enumerate(["Username", "Domain", "Resolution", "Port"]):
            ttk.Label(grid, text=key + ":", foreground="gray",
                      width=12, anchor=tk.E).grid(row=i, column=0, sticky=tk.E, pady=2)
            var = tk.StringVar()
            self._detail_labels[key] = var
            ttk.Label(grid, textvariable=var, anchor=tk.W).grid(
                row=i, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        # Notes
        ttk.Separator(self._server_frame, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=10)
        ttk.Label(self._server_frame, text="Notes:", foreground="gray").pack(anchor=tk.W)
        self._detail_notes_var = tk.StringVar()
        ttk.Label(self._server_frame, textvariable=self._detail_notes_var,
                  wraplength=400, justify=tk.LEFT).pack(anchor=tk.W, pady=4)

        # Connect button
        btn_frame = ttk.Frame(self._server_frame)
        btn_frame.pack(fill=tk.X, pady=(16, 0))
        self._connect_btn = ttk.Button(btn_frame, text="Connect",
                                       command=self._connect_selected)
        self._connect_btn.pack(side=tk.LEFT)
        ttk.Button(btn_frame, text="Edit...",
                   command=self._edit_selected).pack(side=tk.LEFT, padx=(8, 0))

        # Group detail widgets (hidden until a group is selected)
        self._group_frame = ttk.Frame(self._detail_frame)

        self._group_name_var = tk.StringVar()
        ttk.Label(self._group_frame, textvariable=self._group_name_var,
                  font=("Helvetica", 18, "bold")).pack(anchor=tk.W, pady=(0, 4))

        self._group_info_var = tk.StringVar()
        ttk.Label(self._group_frame, textvariable=self._group_info_var,
                  foreground="gray").pack(anchor=tk.W)

        ttk.Separator(self._group_frame, orient=tk.HORIZONTAL).pack(
            fill=tk.X, pady=10)

        ggrid = ttk.Frame(self._group_frame)
        ggrid.pack(fill=tk.X)
        self._group_labels: dict[str, tk.StringVar] = {}
        for i, key in enumerate(["Default Username", "Default Domain", "Default Password"]):
            ttk.Label(ggrid, text=key + ":", foreground="gray",
                      width=16, anchor=tk.E).grid(row=i, column=0, sticky=tk.E, pady=2)
            var = tk.StringVar()
            self._group_labels[key] = var
            ttk.Label(ggrid, textvariable=var, anchor=tk.W).grid(
                row=i, column=1, sticky=tk.W, padx=(8, 0), pady=2)

        gbtn = ttk.Frame(self._group_frame)
        gbtn.pack(fill=tk.X, pady=(16, 0))
        ttk.Button(gbtn, text="Add Server...",
                   command=self._add_server).pack(side=tk.LEFT)
        ttk.Button(gbtn, text="Add Sub-Group...",
                   command=self._add_group).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(gbtn, text="Edit...",
                   command=self._edit_selected).pack(side=tk.LEFT, padx=(8, 0))

    def _setup_keybindings(self):
        self.root.bind("<Command-n>", lambda e: self._new())
        self.root.bind("<Command-o>", lambda e: self._open())
        self.root.bind("<Command-s>", lambda e: self._save())
        self.root.bind("<Command-i>", lambda e: self._edit_selected())
        self.root.bind("<Command-G>", lambda e: self._add_group())
        self.root.bind("<Command-N>", lambda e: self._add_server())
        self._tree.bind("<Return>",         lambda e: self._connect_selected())
        self._tree.bind("<Command-Return>", lambda e: self._quick_connect_selected())
        self._tree.bind("<Delete>",   lambda e: self._delete_selected())
        self._tree.bind("<BackSpace>", lambda e: self._delete_selected())

    # ------------------------------------------------------------------
    # Drag and drop
    # ------------------------------------------------------------------

    def _setup_drag_and_drop(self):
        self._drag_iid: Optional[str] = None
        self._drag_active = False
        self._drag_start_y = 0
        self._drag_target_iid: Optional[str] = None
        self._tree.tag_configure("drag_target", background="#3584e4", foreground="white")
        self._tree.bind("<ButtonPress-1>",   self._on_drag_start)
        self._tree.bind("<B1-Motion>",       self._on_drag_motion)
        self._tree.bind("<ButtonRelease-1>", self._on_drag_release)

    def _on_drag_start(self, event):
        iid = self._tree.identify_row(event.y)
        node = self._item_map.get(iid) if iid else None
        if not iid or node is self._root_group:
            self._drag_iid = None
            return
        self._drag_iid = iid
        self._drag_start_y = event.y
        self._drag_active = False
        self._drag_target_iid = None

    def _on_drag_motion(self, event):
        if not self._drag_iid:
            return
        if not self._drag_active:
            if abs(event.y - self._drag_start_y) < 4:
                return
            self._drag_active = True
            self._tree.configure(cursor="fleur")

        target_iid = self._tree.identify_row(event.y)
        if target_iid == self._drag_target_iid:
            return

        # Clear previous highlight
        self._clear_drag_highlight()

        self._drag_target_iid = target_iid

        # Highlight new target if valid
        if (target_iid and target_iid != self._drag_iid
                and not self._is_descendant_or_self(self._drag_iid, target_iid)):
            tags = list(self._tree.item(target_iid, "tags"))
            tags.append("drag_target")
            self._tree.item(target_iid, tags=tags)

    def _on_drag_release(self, event):
        self._clear_drag_highlight()
        self._tree.configure(cursor="")

        if not self._drag_active or not self._drag_iid:
            self._drag_iid = None
            self._drag_active = False
            return

        target_iid = self._tree.identify_row(event.y)
        drag_iid = self._drag_iid
        self._drag_iid = None
        self._drag_active = False

        if not target_iid or target_iid == drag_iid:
            return
        if self._is_descendant_or_self(drag_iid, target_iid):
            return

        self._do_drag_drop(drag_iid, target_iid)

    def _clear_drag_highlight(self):
        if self._drag_target_iid:
            node = self._item_map.get(self._drag_target_iid)
            if node is not None:
                tag = "group" if isinstance(node, Group) else "server"
                tags = [t for t in self._tree.item(self._drag_target_iid, "tags")
                        if t != "drag_target"]
                if tag not in tags:
                    tags.append(tag)
                self._tree.item(self._drag_target_iid, tags=tags)
            self._drag_target_iid = None

    def _is_descendant_or_self(self, ancestor_iid: str, iid: str) -> bool:
        """Return True if iid is ancestor_iid itself or one of its descendants."""
        current = iid
        while current:
            if current == ancestor_iid:
                return True
            current = self._tree.parent(current)
        return False

    def _do_drag_drop(self, drag_iid: str, target_iid: str):
        drag_node = self._item_map.get(drag_iid)
        target_node = self._item_map.get(target_iid)
        if drag_node is None or target_node is None:
            return

        # Determine new parent and insertion position
        if isinstance(target_node, Group):
            # Drop onto a group → append as last child
            new_parent_iid = target_iid
            new_parent_node = target_node
            tree_index = "end"
        else:
            # Drop onto a server → insert before it in its parent
            new_parent_iid = self._tree.parent(target_iid)
            new_parent_node = self._item_map.get(new_parent_iid)
            if not isinstance(new_parent_node, Group):
                return
            siblings = list(self._tree.get_children(new_parent_iid))
            tree_index = siblings.index(target_iid)

        # Remove drag_node from its current model parent
        old_parent_iid = self._tree.parent(drag_iid)
        old_parent_node = self._item_map.get(old_parent_iid)
        if not isinstance(old_parent_node, Group):
            return
        old_parent_node.children = [c for c in old_parent_node.children
                                     if c.id != drag_node.id]

        # Find insertion index in the new parent's model children
        if isinstance(target_node, Group):
            model_index = len(new_parent_node.children)
        else:
            model_index = next(
                (i for i, c in enumerate(new_parent_node.children)
                 if c.id == target_node.id),
                len(new_parent_node.children)
            )

        new_parent_node.children.insert(model_index, drag_node)

        # Update treeview
        self._tree.move(drag_iid, new_parent_iid, tree_index)
        self._tree.selection_set(drag_iid)
        self._tree.see(drag_iid)
        self._mark_modified()

    # ------------------------------------------------------------------
    # Tree population
    # ------------------------------------------------------------------

    def _refresh_tree(self, filter_text: str = ""):
        """Rebuild the treeview from the data model."""
        self._item_map.clear()
        self._id_map.clear()
        for iid in self._tree.get_children():
            self._tree.delete(iid)

        ft = filter_text.strip().lower()

        root_iid = self._tree.insert(
            "", "end",
            text=self._root_group.name,
            image=self._icon_group_open,
            tags=("group",),
            open=True,
        )
        self._item_map[root_iid] = self._root_group
        self._id_map[self._root_group.id] = root_iid

        self._populate_children(root_iid, self._root_group, ft)

        if not ft:
            self._tree.item(root_iid, open=self._root_group.expanded)

    def _populate_children(self, parent_iid: str, group: Group, filter_text: str) -> bool:
        """Insert matching children under parent_iid. Returns True if any item was inserted."""
        any_inserted = False
        for child in group.children:
            if isinstance(child, Server):
                if filter_text and filter_text not in child.label.lower() \
                        and filter_text not in child.settings.host.lower():
                    continue
                iid = self._tree.insert(
                    parent_iid, "end",
                    text=child.label,
                    image=self._icon_server,
                    tags=("server",),
                )
                self._item_map[iid] = child
                self._id_map[child.id] = iid
                any_inserted = True
            elif isinstance(child, Group):
                if filter_text:
                    # Tentatively insert the group, then remove it if nothing matches.
                    iid = self._tree.insert(
                        parent_iid, "end",
                        text=child.name,
                        image=self._icon_group_closed,
                        tags=("group",),
                        open=True,
                    )
                    self._item_map[iid] = child
                    self._id_map[child.id] = iid
                    name_matches = filter_text in child.name.lower()
                    child_inserted = self._populate_children(iid, child, filter_text)
                    if name_matches or child_inserted:
                        any_inserted = True
                    else:
                        self._tree.delete(iid)
                        del self._item_map[iid]
                        del self._id_map[child.id]
                else:
                    iid = self._tree.insert(
                        parent_iid, "end",
                        text=child.name,
                        image=self._icon_group_closed,
                        tags=("group",),
                        open=child.expanded,
                    )
                    self._item_map[iid] = child
                    self._id_map[child.id] = iid
                    self._populate_children(iid, child, filter_text)
        return any_inserted

    def _update_title(self):
        name = self._current_file.name if self._current_file else "Untitled"
        mod = " *" if self._modified else ""
        self.root.title(f"RDP Tree — {name}{mod}")

    def _mark_modified(self):
        self._modified = True
        self._update_title()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _search_focus_in(self, entry: ttk.Entry):
        if self._search_placeholder:
            entry.delete(0, tk.END)
            entry.configure(foreground="black")
            self._search_placeholder = False

    def _search_focus_out(self, entry: ttk.Entry):
        if not entry.get():
            entry.insert(0, "Search...")
            entry.configure(foreground="gray")
            self._search_placeholder = True

    def _on_search_changed(self, *_):
        if self._search_placeholder:
            return
        if self._search_after_id is not None:
            self.root.after_cancel(self._search_after_id)
        self._search_after_id = self.root.after(
            200, lambda: self._refresh_tree(filter_text=self._search_var.get())
        )

    # ------------------------------------------------------------------
    # Selection and display
    # ------------------------------------------------------------------

    def _on_tree_select(self, _event=None):
        sel = self._tree.selection()
        if not sel:
            return
        if len(sel) > 1:
            self._show_multi_select(len(sel))
            return
        iid = sel[0]
        node = self._item_map.get(iid)
        if node is None:
            return
        if isinstance(node, Server):
            self._show_server(node, iid)
        elif isinstance(node, Group):
            self._show_group(node)

    def _show_welcome(self):
        self._server_frame.pack_forget()
        self._group_frame.pack_forget()
        self._welcome_label.configure(text="Select a server or group from the tree.")
        self._welcome_label.pack(expand=True)

    def _show_multi_select(self, count: int):
        self._server_frame.pack_forget()
        self._group_frame.pack_forget()
        self._welcome_label.configure(text=f"{count} items selected")
        self._welcome_label.pack(expand=True)

    def _show_server(self, server: Server, iid: str):
        self._welcome_label.pack_forget()
        self._group_frame.pack_forget()
        self._server_frame.pack(fill=tk.BOTH, expand=True)

        s = server.settings
        username, domain = self._resolve_credentials(iid, server)

        self._detail_name_var.set(server.label)
        self._detail_host_var.set(f"{s.host}:{s.port}" if s.port != 3389 else s.host)
        self._detail_labels["Username"].set(username or "(none)")
        self._detail_labels["Domain"].set(domain or "(none)")
        self._detail_labels["Resolution"].set(_resolution_label(server))
        self._detail_labels["Port"].set(str(s.port))
        self._detail_notes_var.set(s.notes or "")

    def _show_group(self, group: Group):
        self._welcome_label.pack_forget()
        self._server_frame.pack_forget()
        self._group_frame.pack(fill=tk.BOTH, expand=True)

        count = group.server_count()
        self._group_name_var.set(group.name)
        self._group_info_var.set(f"{count} server{'s' if count != 1 else ''}")
        self._group_labels["Default Username"].set(group.default_username or "(none)")
        self._group_labels["Default Domain"].set(group.default_domain or "(none)")
        self._group_labels["Default Password"].set(
            "Saved to Keychain" if group.has_saved_password else "(none)")

    def _resolve_credentials(self, iid: str, server: Server) -> tuple[str, str]:
        """Return (username, domain) for a server, walking up parent groups."""
        username = server.settings.username
        domain = server.settings.domain
        if username and domain:
            return username, domain

        # Walk up the treeview hierarchy to find the nearest group with defaults
        parent_iid = self._tree.parent(iid)
        while parent_iid:
            parent_node = self._item_map.get(parent_iid)
            if isinstance(parent_node, Group):
                if not username and parent_node.default_username:
                    username = parent_node.default_username
                if not domain and parent_node.default_domain:
                    domain = parent_node.default_domain
                if username and domain:
                    break
            parent_iid = self._tree.parent(parent_iid)

        return username, domain

    def _get_password(self, iid: str, server: Server) -> str:
        """Retrieve saved password from Keychain, walking up parent groups."""
        if server.settings.has_saved_password:
            pw = keychain.get_password(server.id)
            if pw:
                return pw

        # Walk up parent groups for an inherited password
        parent_iid = self._tree.parent(iid)
        while parent_iid:
            parent_node = self._item_map.get(parent_iid)
            if isinstance(parent_node, Group) and parent_node.has_saved_password:
                pw = keychain.get_password(parent_node.id)
                if pw:
                    return pw
            parent_iid = self._tree.parent(parent_iid)

        return ""

    # ------------------------------------------------------------------
    # Tree events
    # ------------------------------------------------------------------

    def _on_double_click(self, event):
        iid = self._tree.identify_row(event.y)
        if not iid:
            return
        node = self._item_map.get(iid)
        if isinstance(node, Server):
            self._connect_selected()

    def _on_right_click(self, event):
        iid = self._tree.identify_row(event.y)
        if iid:
            if iid not in self._tree.selection():
                self._tree.selection_set(iid)
        else:
            self._tree.selection_set()

        sel = self._tree.selection()
        node = self._item_map.get(iid) if iid else None
        menu = tk.Menu(self.root, tearoff=0)

        if len(sel) > 1:
            all_servers = all(isinstance(self._item_map.get(s), Server) for s in sel)
            if all_servers:
                menu.add_command(label="Connect All",       command=self._connect_selected)
                menu.add_command(label="Quick Connect All", command=self._quick_connect_selected)
                menu.add_separator()
            menu.add_command(label=f"Delete {len(sel)} Items", command=self._delete_selected)
        elif isinstance(node, Server):
            menu.add_command(label="Connect",       command=self._connect_selected)
            menu.add_command(label="Quick Connect", command=self._quick_connect_selected)
            menu.add_command(label="Connect As...", command=self._connect_as_selected)
            menu.add_separator()
            menu.add_command(label="Copy Address",  command=self._copy_address_selected)
            menu.add_separator()
            menu.add_command(label="Edit...",      command=self._edit_selected)
            menu.add_command(label="Duplicate",    command=self._duplicate_selected)
            menu.add_command(label="Delete",       command=self._delete_selected)
            menu.add_separator()
            menu.add_command(label="Move Up",      command=lambda: self._move_selected(-1))
            menu.add_command(label="Move Down",    command=lambda: self._move_selected(1))
        elif isinstance(node, Group):
            menu.add_command(label="Add Server...",   command=self._add_server)
            menu.add_command(label="Add Sub-Group...", command=self._add_group)
            menu.add_separator()
            if node is not self._root_group:
                menu.add_command(label="Edit...",  command=self._edit_selected)
                menu.add_command(label="Delete",   command=self._delete_selected)
                menu.add_separator()
                menu.add_command(label="Move Up",  command=lambda: self._move_selected(-1))
                menu.add_command(label="Move Down",command=lambda: self._move_selected(1))
        else:
            menu.add_command(label="Add Group...",  command=self._add_group)
            menu.add_command(label="Add Server...", command=self._add_server)

        menu.tk_popup(event.x_root, event.y_root)

    def _on_tree_open(self, _event=None):
        iid = self._tree.focus()
        node = self._item_map.get(iid)
        if isinstance(node, Group):
            node.expanded = True
            self._tree.item(iid, image=self._icon_group_open)
            self._mark_modified()

    def _on_tree_close(self, _event=None):
        iid = self._tree.focus()
        node = self._item_map.get(iid)
        if isinstance(node, Group):
            node.expanded = False
            self._tree.item(iid, image=self._icon_group_closed)
            self._mark_modified()

    # ------------------------------------------------------------------
    # Connect
    # ------------------------------------------------------------------

    def _connect_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        servers = [(s, self._item_map[s]) for s in sel
                   if isinstance(self._item_map.get(s), Server)]
        if not servers:
            return

        if len(servers) == 1:
            iid, node = servers[0]
            username, domain = self._resolve_credentials(iid, node)
            dlg = ConnectDialog(self.root, node, username, domain)
            self.root.wait_window(dlg.dialog)
            if not dlg.result:
                return
            username = dlg.result["username"]
            domain = dlg.result["domain"]
            try:
                launch.launch(node, username, domain, self._get_password(iid, node))
                self._status_var.set(f"Connecting to {node.label}...")
            except Exception as exc:
                messagebox.showerror("Launch Error",
                                     f"Failed to launch RDP session:\n{exc}")
        else:
            launched = 0
            for iid, node in servers:
                username, domain = self._resolve_credentials(iid, node)
                try:
                    launch.launch(node, username, domain,
                                  self._get_password(iid, node))
                    launched += 1
                except Exception as exc:
                    messagebox.showerror("Launch Error",
                                         f"Failed to launch {node.label}:\n{exc}")
            if launched:
                self._status_var.set(
                    f"Connecting to {launched} server{'s' if launched != 1 else ''}...")

    def _quick_connect_selected(self):
        """Launch immediately using resolved credentials — no dialog."""
        sel = self._tree.selection()
        if not sel:
            return
        servers = [(s, self._item_map[s]) for s in sel
                   if isinstance(self._item_map.get(s), Server)]
        if not servers:
            return

        launched = 0
        for iid, node in servers:
            username, domain = self._resolve_credentials(iid, node)
            try:
                launch.launch(node, username, domain,
                              self._get_password(iid, node))
                launched += 1
            except Exception as exc:
                messagebox.showerror("Launch Error",
                                     f"Failed to launch {node.label}:\n{exc}")
        if launched:
            self._status_var.set(
                f"Quick connecting to {launched} server{'s' if launched != 1 else ''}...")

    def _connect_as_selected(self):
        """Open connect dialog with blank credentials to connect as a different user."""
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        node = self._item_map.get(iid)
        if not isinstance(node, Server):
            return

        dlg = ConnectDialog(self.root, node, "", "",
                            title=f"Connect As — {node.label}")
        self.root.wait_window(dlg.dialog)
        if not dlg.result:
            return
        username = dlg.result["username"]
        domain = dlg.result["domain"]
        try:
            launch.launch(node, username, domain, self._get_password(iid, node))
            label = f"{domain}\\{username}" if domain else username
            self._status_var.set(f"Connecting to {node.label} as {label}...")
        except Exception as exc:
            messagebox.showerror("Launch Error",
                                 f"Failed to launch RDP session:\n{exc}")

    # ------------------------------------------------------------------
    # Add / Edit / Delete
    # ------------------------------------------------------------------

    def _selected_parent_group(self) -> tuple[str, Group]:
        """Return (parent_treeview_iid, parent_Group) for inserting a new child."""
        sel = self._tree.selection()
        if sel:
            iid = sel[0]
            node = self._item_map.get(iid)
            if isinstance(node, Group):
                return iid, node
            elif isinstance(node, Server):
                parent_iid = self._tree.parent(iid)
                parent_node = self._item_map.get(parent_iid)
                if isinstance(parent_node, Group):
                    return parent_iid, parent_node
        # Fallback: root
        root_iid = self._id_map.get(self._root_group.id, "")
        return root_iid, self._root_group

    def _add_server(self):
        dlg = ServerDialog(self.root, title="Add Server")
        self.root.wait_window(dlg.dialog)
        if dlg.result is None:
            return

        server = dlg.result
        parent_iid, parent_group = self._selected_parent_group()
        parent_group.children.append(server)

        iid = self._tree.insert(
            parent_iid, "end",
            text=server.label,
            image=self._icon_server,
            tags=("server",),
        )
        self._item_map[iid] = server
        self._id_map[server.id] = iid
        self._tree.see(iid)
        self._tree.selection_set(iid)
        self._mark_modified()

    def _duplicate_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        node = self._item_map.get(iid)
        if not isinstance(node, Server):
            return

        new_settings = ServerSettings(
            host=node.settings.host,
            port=node.settings.port,
            username=node.settings.username,
            domain=node.settings.domain,
            has_saved_password=False,
            width=node.settings.width,
            height=node.settings.height,
            fullscreen=node.settings.fullscreen,
            notes=node.settings.notes,
            shared_folders=list(node.settings.shared_folders),
        )
        new_server = Server(
            display_name=f"Copy of {node.label}",
            settings=new_settings,
        )

        parent_iid = self._tree.parent(iid)
        parent_group = self._item_map.get(parent_iid)
        if not isinstance(parent_group, Group):
            return

        orig_index = parent_group.children.index(node)
        parent_group.children.insert(orig_index + 1, new_server)

        tree_index = self._tree.index(iid)
        new_iid = self._tree.insert(
            parent_iid, tree_index + 1,
            text=new_server.label,
            image=self._icon_server,
            tags=("server",),
        )
        self._item_map[new_iid] = new_server
        self._id_map[new_server.id] = new_iid
        self._tree.see(new_iid)
        self._tree.selection_set(new_iid)
        self._mark_modified()

    def _add_group(self):
        dlg = GroupDialog(self.root, title="Add Group")
        self.root.wait_window(dlg.dialog)
        if dlg.result is None:
            return

        group = dlg.result
        parent_iid, parent_group = self._selected_parent_group()
        parent_group.children.append(group)

        iid = self._tree.insert(
            parent_iid, "end",
            text=group.name,
            image=self._icon_group_closed,
            tags=("group",),
            open=group.expanded,
        )
        self._item_map[iid] = group
        self._id_map[group.id] = iid
        self._tree.see(iid)
        self._tree.selection_set(iid)
        self._mark_modified()

    def _edit_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        node = self._item_map.get(iid)

        if isinstance(node, Server):
            dlg = ServerDialog(self.root, title="Edit Server", server=node)
            self.root.wait_window(dlg.dialog)
            if dlg.result is None:
                return
            # Copy edits back into the existing object (preserve ID)
            edited = dlg.result
            node.display_name = edited.display_name
            node.settings = edited.settings
            self._tree.item(iid, text=node.label)
            self._show_server(node, iid)

        elif isinstance(node, Group) and node is not self._root_group:
            dlg = GroupDialog(self.root, title="Edit Group", group=node)
            self.root.wait_window(dlg.dialog)
            if dlg.result is None:
                return
            edited = dlg.result
            node.name = edited.name
            node.default_username = edited.default_username
            node.default_domain = edited.default_domain
            self._tree.item(iid, text=node.name)
            self._show_group(node)

        elif node is self._root_group:
            new_name = simpledialog.askstring(
                "Rename", "Connection file name:",
                initialvalue=self._root_group.name, parent=self.root)
            if new_name:
                self._root_group.name = new_name
                root_iid = self._id_map[self._root_group.id]
                self._tree.item(root_iid, text=new_name)

        self._mark_modified()

    def _delete_selected(self):
        sel = self._tree.selection()
        if not sel:
            return

        iids = [iid for iid in sel
                if self._item_map.get(iid) is not self._root_group]
        if not iids:
            return

        if len(iids) == 1:
            node = self._item_map.get(iids[0])
            if isinstance(node, Server):
                prompt = f"Delete '{node.label}'?"
            else:
                count = node.server_count()
                if count > 0:
                    prompt = (f"Delete '{node.name}' and its "
                              f"{count} server{'s' if count != 1 else ''}?")
                else:
                    prompt = f"Delete '{node.name}'?"
        else:
            prompt = f"Delete {len(iids)} items?"

        if not messagebox.askyesno("Delete", prompt, parent=self.root):
            return

        for iid in iids:
            if iid not in self._item_map:
                continue  # already removed as a descendant of a prior deletion
            node = self._item_map[iid]

            parent_iid = self._tree.parent(iid)
            parent_node = self._item_map.get(parent_iid)
            if isinstance(parent_node, Group):
                parent_node.children = [c for c in parent_node.children
                                        if c.id != node.id]

            if isinstance(node, Server) and node.settings.has_saved_password:
                keychain.delete_password(node.id)
            elif isinstance(node, Group) and node.has_saved_password:
                keychain.delete_password(node.id)

            self._remove_from_maps(iid)
            self._tree.delete(iid)

        self._show_welcome()
        self._mark_modified()

    def _remove_from_maps(self, iid: str):
        node = self._item_map.pop(iid, None)
        if node:
            self._id_map.pop(node.id, None)
        for child_iid in self._tree.get_children(iid):
            self._remove_from_maps(child_iid)

    def _move_selected(self, direction: int):
        """Move selected item up (-1) or down (+1) within its parent."""
        sel = self._tree.selection()
        if not sel:
            return
        iid = sel[0]
        node = self._item_map.get(iid)
        if node is self._root_group:
            return

        parent_iid = self._tree.parent(iid)
        parent_node = self._item_map.get(parent_iid)
        if not isinstance(parent_node, Group):
            return

        children = parent_node.children
        idx = next((i for i, c in enumerate(children) if c.id == node.id), -1)
        if idx == -1:
            return
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(children):
            return

        # Swap in model
        children[idx], children[new_idx] = children[new_idx], children[idx]

        # Move the treeview item directly instead of rebuilding the whole tree
        self._tree.move(iid, parent_iid, new_idx)
        self._tree.see(iid)
        self._mark_modified()

    # ------------------------------------------------------------------
    # File operations
    # ------------------------------------------------------------------

    def _confirm_discard(self) -> bool:
        if not self._modified:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved Changes",
            "You have unsaved changes. Save before continuing?",
            parent=self.root,
        )
        if answer is None:  # Cancel
            return False
        if answer:  # Yes - save
            return self._save()
        return True  # No - discard

    def _new(self):
        if not self._confirm_discard():
            return
        self._root_group = Group(name="My Connections")
        self._current_file = None
        self._modified = False
        self._refresh_tree()
        self._show_welcome()
        self._update_title()

    def _open(self):
        if not self._confirm_discard():
            return
        path = filedialog.askopenfilename(
            title="Open RDP Tree File",
            filetypes=[("RDP Tree files", "*.rdptree"), ("All files", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        self._open_file(Path(path))

    def _open_file(self, path: Path):
        try:
            self._root_group = storage.load(str(path))
            self._current_file = path
            self._modified = False
            self._refresh_tree()
            self._show_welcome()
            self._update_title()
            self._status_var.set(f"Opened {path.name}")
            prefs.set_last_file(path)
        except Exception as exc:
            messagebox.showerror("Open Error", f"Could not open file:\n{exc}")

    def _save(self) -> bool:
        if self._current_file is None:
            return self._save_as()
        try:
            storage.save(self._current_file, self._root_group)
            self._modified = False
            self._update_title()
            self._status_var.set(f"Saved {self._current_file.name}")
            return True
        except Exception as exc:
            messagebox.showerror("Save Error", f"Could not save file:\n{exc}")
            return False

    def _save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            title="Save RDP Tree File",
            defaultextension=".rdptree",
            filetypes=[("RDP Tree files", "*.rdptree"), ("All files", "*.*")],
            initialfile=self._current_file.name if self._current_file else "connections.rdptree",
            parent=self.root,
        )
        if not path:
            return False
        self._current_file = Path(path)
        prefs.set_last_file(path)
        return self._save()

    def _rebuild_recent_menu(self):
        self._open_recent_menu.delete(0, "end")
        recents = prefs.get_recent_files()
        if recents:
            for path in recents:
                self._open_recent_menu.add_command(
                    label=str(path),
                    command=lambda p=path: self._open_recent(p),
                )
            self._open_recent_menu.add_separator()
            self._open_recent_menu.add_command(label="Clear Menu",
                                               command=self._clear_recent_files)
        else:
            self._open_recent_menu.add_command(label="No Recent Files",
                                               state="disabled")

    def _open_recent(self, path: Path):
        if not self._confirm_discard():
            return
        self._open_file(path)

    def _clear_recent_files(self):
        prefs.clear_recent_files()

    def _reveal_in_finder(self):
        if self._current_file is None:
            self._status_var.set("No file is currently open.")
            return
        subprocess.run(["open", "-R", str(self._current_file)], check=False)

    def _copy_address_selected(self):
        sel = self._tree.selection()
        if not sel:
            return
        node = self._item_map.get(sel[0])
        if not isinstance(node, Server):
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(node.settings.host)
        self._status_var.set(f'Copied "{node.settings.host}" to clipboard')

    def _import_rdg(self):
        path = filedialog.askopenfilename(
            title="Import RDCMan File",
            filetypes=[("RDCMan files", "*.rdg"), ("All files", "*.*")],
            parent=self.root,
        )
        if not path:
            return
        try:
            imported = rdg_import.import_rdg(path)
        except Exception as exc:
            messagebox.showerror("Import Error", f"Could not import RDG file:\n{exc}")
            return

        # Merge into current tree or replace?
        if self._root_group.children:
            answer = messagebox.askyesnocancel(
                "Import",
                "Add imported groups to the current tree?\n"
                "Choose No to replace the entire tree.",
                parent=self.root,
            )
            if answer is None:
                return
            if answer:  # Merge
                self._root_group.children.extend(imported.children)
            else:  # Replace
                self._root_group = imported
        else:
            self._root_group = imported

        self._refresh_tree()
        self._mark_modified()
        count = imported.server_count()
        self._status_var.set(f"Imported {count} servers from {Path(path).name}")

    def _export_rdg(self):
        default_name = (
            self._current_file.stem if self._current_file else self._root_group.name
        )
        path = filedialog.asksaveasfilename(
            title="Export to RDCMan File",
            filetypes=[("RDCMan files", "*.rdg"), ("All files", "*.*")],
            defaultextension=".rdg",
            initialfile=f"{default_name}.rdg",
            parent=self.root,
        )
        if not path:
            return
        try:
            rdg_export.export_rdg(self._root_group, path)
            count = self._root_group.server_count()
            self._status_var.set(f"Exported {count} servers to {Path(path).name}")
        except Exception as exc:
            messagebox.showerror("Export Error", f"Could not export RDG file:\n{exc}")

    def _quit(self):
        if self._search_after_id is not None:
            self.root.after_cancel(self._search_after_id)
            self._search_after_id = None
        if self._confirm_discard():
            self.root.destroy()

    def run(self):
        self.root.protocol("WM_DELETE_WINDOW", self._quit)
        self.root.mainloop()


# ==============================================================================
# Dialogs
# ==============================================================================

class _BaseDialog:
    def __init__(self, parent: tk.Tk, title: str):
        self.dialog = tk.Toplevel(parent)
        self.dialog.title(title)
        self.dialog.transient(parent)
        self.dialog.resizable(False, False)
        self.result = None

        # Center on parent
        self.dialog.update_idletasks()
        px = parent.winfo_x() + parent.winfo_width() // 2
        py = parent.winfo_y() + parent.winfo_height() // 2
        w, h = self._dialog_size()
        self.dialog.geometry(f"{w}x{h}+{px - w // 2}+{py - h // 2}")

        self._build()
        self.dialog.grab_set()
        self.dialog.bind("<Escape>", lambda e: self.dialog.destroy())

    def _dialog_size(self) -> tuple[int, int]:
        return 460, 400

    def _build(self):
        raise NotImplementedError

    def _make_field(self, frame: ttk.Frame, label: str, row: int,
                    show: str = "", width: int = 32) -> tk.StringVar:
        ttk.Label(frame, text=label + ":", anchor=tk.E, width=14).grid(
            row=row, column=0, sticky=tk.E, padx=(0, 8), pady=4)
        var = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=var, show=show, width=width)
        entry.grid(row=row, column=1, sticky=tk.EW, pady=4)
        return var

    def _make_buttons(self, frame: ttk.Frame, ok_text: str = "OK"):
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=(12, 0))
        ttk.Button(btn_frame, text="Cancel",
                   command=self.dialog.destroy).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(btn_frame, text=ok_text,
                   command=self._on_ok).pack(side=tk.RIGHT)

    def _on_ok(self):
        raise NotImplementedError


class ServerDialog(_BaseDialog):
    def __init__(self, parent: tk.Tk, title: str, server: Server | None = None):
        self._server = server
        super().__init__(parent, title)

    def _dialog_size(self):
        return 480, 600

    def _build(self):
        outer = ttk.Frame(self.dialog, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        frame = ttk.Frame(outer)
        frame.pack(fill=tk.X)
        frame.columnconfigure(1, weight=1)

        s = self._server.settings if self._server else ServerSettings()

        self._display_name = self._make_field(frame, "Display Name", 0)
        self._host         = self._make_field(frame, "Host / IP",    1)
        self._port         = self._make_field(frame, "Port",         2)
        self._username     = self._make_field(frame, "Username",     3)
        self._domain       = self._make_field(frame, "Domain",       4)
        self._password     = self._make_field(frame, "Password",     5, show="*")

        # Save password checkbox
        self._save_pw = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Save password to Keychain",
                        variable=self._save_pw).grid(
            row=6, column=1, sticky=tk.W, pady=4)

        # Resolution
        ttk.Label(frame, text="Resolution:", anchor=tk.E, width=14).grid(
            row=7, column=0, sticky=tk.E, padx=(0, 8), pady=4)
        self._resolution = tk.StringVar()
        res_cb = ttk.Combobox(frame, textvariable=self._resolution,
                              values=RESOLUTION_LABELS, state="readonly", width=30)
        res_cb.grid(row=7, column=1, sticky=tk.W, pady=4)

        # Notes
        ttk.Label(frame, text="Notes:", anchor=tk.E, width=14).grid(
            row=8, column=0, sticky=tk.NE, padx=(0, 8), pady=4)
        self._notes_text = tk.Text(frame, height=3, width=32, wrap=tk.WORD)
        self._notes_text.grid(row=8, column=1, sticky=tk.EW, pady=4)

        # Shared Folders
        ttk.Separator(frame, orient=tk.HORIZONTAL).grid(
            row=9, column=0, columnspan=2, sticky=tk.EW, pady=(8, 4))
        ttk.Label(frame, text="Shared Folders:", anchor=tk.E, width=14).grid(
            row=10, column=0, sticky=tk.NE, padx=(0, 8), pady=4)

        folder_frame = ttk.Frame(frame)
        folder_frame.grid(row=10, column=1, sticky=tk.EW, pady=4)
        folder_frame.columnconfigure(0, weight=1)

        self._folders_listbox = tk.Listbox(folder_frame, height=4, selectmode=tk.SINGLE)
        self._folders_listbox.grid(row=0, column=0, sticky=tk.EW)

        folder_btn_frame = ttk.Frame(folder_frame)
        folder_btn_frame.grid(row=1, column=0, sticky=tk.W, pady=(4, 0))
        ttk.Button(folder_btn_frame, text="Add Folder…",
                   command=self._add_folder).pack(side=tk.LEFT)
        ttk.Button(folder_btn_frame, text="Remove",
                   command=self._remove_folder).pack(side=tk.LEFT, padx=(6, 0))

        # Pre-fill
        if self._server:
            self._display_name.set(self._server.display_name)
            self._host.set(s.host)
            self._port.set(str(s.port))
            self._username.set(s.username)
            self._domain.set(s.domain)
            self._resolution.set(_resolution_label(self._server))
            self._notes_text.insert("1.0", s.notes)
            if s.has_saved_password:
                pw = keychain.get_password(self._server.id)
                if pw:
                    self._password.set(pw)
                    self._save_pw.set(True)
            for folder in s.shared_folders:
                self._folders_listbox.insert(tk.END, folder)
        else:
            self._port.set("3389")
            self._resolution.set("1920 x 1080")

        self._make_buttons(outer, ok_text="Save")

    def _on_ok(self):
        host = self._host.get().strip()
        if not host:
            messagebox.showwarning("Validation", "Host / IP is required.", parent=self.dialog)
            return

        port_str = self._port.get().strip()
        try:
            port = int(port_str)
            if not (1 <= port <= 65535):
                raise ValueError
        except ValueError:
            messagebox.showwarning("Validation", "Port must be a number between 1 and 65535.",
                                   parent=self.dialog)
            return

        # Parse resolution
        res_label = self._resolution.get()
        fullscreen, width, height = False, 1920, 1080
        for label, w, h, fs in RESOLUTIONS:
            if label == res_label:
                fullscreen, width, height = fs, w, h
                break

        new_server = Server(
            id=self._server.id if self._server else str(uuid.uuid4()),
            display_name=self._display_name.get().strip(),
            settings=ServerSettings(
                host=host,
                port=port,
                username=self._username.get().strip(),
                domain=self._domain.get().strip(),
                width=width,
                height=height,
                fullscreen=fullscreen,
                notes=self._notes_text.get("1.0", "end-1c").strip(),
                shared_folders=list(self._folders_listbox.get(0, tk.END)),
            ),
        )

        # Handle password
        pw = self._password.get()
        if self._save_pw.get() and pw:
            if keychain.set_password(new_server.id, pw):
                new_server.settings.has_saved_password = True
            else:
                messagebox.showwarning(
                    "Keychain Error",
                    "The password could not be saved to the macOS Keychain.\n"
                    "You will be prompted for it at connect time.",
                    parent=self.dialog,
                )
        elif not self._save_pw.get() and self._server and self._server.settings.has_saved_password:
            keychain.delete_password(new_server.id)
            new_server.settings.has_saved_password = False

        self.result = new_server
        self.dialog.destroy()


    def _add_folder(self):
        path = filedialog.askdirectory(title="Select Folder to Share", parent=self.dialog)
        if path and path not in self._folders_listbox.get(0, tk.END):
            self._folders_listbox.insert(tk.END, path)

    def _remove_folder(self):
        sel = self._folders_listbox.curselection()
        if sel:
            self._folders_listbox.delete(sel[0])


class GroupDialog(_BaseDialog):
    def __init__(self, parent: tk.Tk, title: str, group: Group | None = None):
        self._group = group
        super().__init__(parent, title)

    def _dialog_size(self):
        return 420, 290

    def _build(self):
        outer = ttk.Frame(self.dialog, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        frame = ttk.Frame(outer)
        frame.pack(fill=tk.X)
        frame.columnconfigure(1, weight=1)

        self._name           = self._make_field(frame, "Group Name",       0)
        self._default_user   = self._make_field(frame, "Default Username", 1)
        self._default_domain = self._make_field(frame, "Default Domain",   2)
        self._password       = self._make_field(frame, "Default Password", 3, show="*")

        self._save_pw = tk.BooleanVar()
        ttk.Checkbutton(frame, text="Save Password to Keychain",
                        variable=self._save_pw).grid(
            row=4, column=1, sticky=tk.W, pady=(2, 0))

        if self._group:
            self._name.set(self._group.name)
            self._default_user.set(self._group.default_username)
            self._default_domain.set(self._group.default_domain)
            if self._group.has_saved_password:
                pw = keychain.get_password(self._group.id)
                if pw:
                    self._password.set(pw)
                    self._save_pw.set(True)

        self._make_buttons(outer, ok_text="Save")

    def _on_ok(self):
        name = self._name.get().strip()
        if not name:
            messagebox.showwarning("Validation", "Group name is required.", parent=self.dialog)
            return
        group_id = self._group.id if self._group else str(uuid.uuid4())
        has_pw = False

        # Handle password
        pw = self._password.get()
        if self._save_pw.get() and pw:
            if keychain.set_password(group_id, pw):
                has_pw = True
            else:
                messagebox.showwarning(
                    "Keychain Error",
                    "Failed to save password to Keychain.",
                    parent=self.dialog)
        elif not self._save_pw.get() and self._group and self._group.has_saved_password:
            keychain.delete_password(group_id)

        self.result = Group(
            id=group_id,
            name=name,
            default_username=self._default_user.get().strip(),
            default_domain=self._default_domain.get().strip(),
            has_saved_password=has_pw,
            expanded=self._group.expanded if self._group else True,
            children=self._group.children if self._group else [],
        )
        self.dialog.destroy()


class ConnectDialog(_BaseDialog):
    def __init__(self, parent: tk.Tk, server: Server, username: str, domain: str,
                 title: str = ""):
        self._server = server
        self._pre_username = username
        self._pre_domain = domain
        super().__init__(parent, title or f"Connect to {server.label}")

    def _dialog_size(self):
        return 400, 200

    def _build(self):
        outer = ttk.Frame(self.dialog, padding=16)
        outer.pack(fill=tk.BOTH, expand=True)

        ttk.Label(outer, text=f"Connecting to: {self._server.settings.host}",
                  foreground="gray").pack(anchor=tk.W, pady=(0, 10))

        frame = ttk.Frame(outer)
        frame.pack(fill=tk.X)
        frame.columnconfigure(1, weight=1)

        self._username = self._make_field(frame, "Username", 0)
        self._domain   = self._make_field(frame, "Domain",   1)

        self._username.set(self._pre_username)
        self._domain.set(self._pre_domain)

        self._make_buttons(outer, ok_text="Connect")
        self.dialog.bind("<Return>", lambda e: self._on_ok())

    def _on_ok(self):
        self.result = {
            "username": self._username.get().strip(),
            "domain":   self._domain.get().strip(),
        }
        self.dialog.destroy()
