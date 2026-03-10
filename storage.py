"""JSON persistence for RDP Tree files."""
import json
from pathlib import Path
from models import Group

FILE_EXTENSION = ".rdptree"
FILE_VERSION = "1.0"


def load(path: str | Path) -> Group:
    """Load a .rdptree file, returning the root Group."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    root_data = data.get("root", {})
    return Group.from_dict(root_data)


def save(path: str | Path, root: Group) -> None:
    """Save the root Group to a .rdptree file."""
    data = {
        "version": FILE_VERSION,
        "root": root.to_dict(),
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
