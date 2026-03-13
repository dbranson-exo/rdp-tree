"""Data models for RDP Tree."""
from __future__ import annotations
import uuid
from dataclasses import dataclass, field
from typing import List, Union


@dataclass
class ServerSettings:
    host: str = ""
    port: int = 3389
    username: str = ""
    domain: str = ""
    has_saved_password: bool = False
    width: int = 1920
    height: int = 1080
    fullscreen: bool = False
    notes: str = ""
    shared_folders: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "host": self.host,
            "port": self.port,
            "username": self.username,
            "domain": self.domain,
            "has_saved_password": self.has_saved_password,
            "width": self.width,
            "height": self.height,
            "fullscreen": self.fullscreen,
            "notes": self.notes,
            "shared_folders": self.shared_folders,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ServerSettings":
        return cls(
            host=d.get("host", ""),
            port=d.get("port", 3389),
            username=d.get("username", ""),
            domain=d.get("domain", ""),
            has_saved_password=d.get("has_saved_password", False),
            width=d.get("width", 1920),
            height=d.get("height", 1080),
            fullscreen=d.get("fullscreen", False),
            notes=d.get("notes", ""),
            shared_folders=d.get("shared_folders", []),
        )


@dataclass
class Server:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    display_name: str = ""
    settings: ServerSettings = field(default_factory=ServerSettings)

    @property
    def label(self) -> str:
        return self.display_name or self.settings.host or "Unnamed Server"

    def to_dict(self) -> dict:
        return {
            "type": "server",
            "id": self.id,
            "display_name": self.display_name,
            "settings": self.settings.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Server":
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            display_name=d.get("display_name", ""),
            settings=ServerSettings.from_dict(d.get("settings", {})),
        )


@dataclass
class Group:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "New Group"
    expanded: bool = True
    default_username: str = ""
    default_domain: str = ""
    has_saved_password: bool = False
    children: List[Union["Group", Server]] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.name

    def server_count(self) -> int:
        count = 0
        for child in self.children:
            if isinstance(child, Server):
                count += 1
            elif isinstance(child, Group):
                count += child.server_count()
        return count

    def to_dict(self) -> dict:
        return {
            "type": "group",
            "id": self.id,
            "name": self.name,
            "expanded": self.expanded,
            "default_username": self.default_username,
            "default_domain": self.default_domain,
            "has_saved_password": self.has_saved_password,
            "children": [child.to_dict() for child in self.children],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "Group":
        children = []
        for child in d.get("children", []):
            if child.get("type") == "server":
                children.append(Server.from_dict(child))
            elif child.get("type") == "group":
                children.append(Group.from_dict(child))
        return cls(
            id=d.get("id", str(uuid.uuid4())),
            name=d.get("name", "Group"),
            expanded=d.get("expanded", True),
            default_username=d.get("default_username", ""),
            default_domain=d.get("default_domain", ""),
            has_saved_password=d.get("has_saved_password", False),
            children=children,
        )


TreeNode = Union[Group, Server]
