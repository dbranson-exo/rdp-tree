"""User preferences for RDP Tree."""
import json
from pathlib import Path

_PREFS_PATH = Path.home() / "Library" / "Preferences" / "rdptree.json"
_MAX_RECENT = 10


def _load() -> dict:
    try:
        with open(_PREFS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(data: dict) -> None:
    _PREFS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(_PREFS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_last_file() -> Path | None:
    """Return the last opened file path if it still exists, otherwise None."""
    path_str = _load().get("last_file")
    if path_str:
        p = Path(path_str)
        if p.exists():
            return p
    return None


def get_recent_files() -> list[Path]:
    """Return recently opened files that still exist, most recent first."""
    return [Path(p) for p in _load().get("recent_files", [])
            if Path(p).exists()][:_MAX_RECENT]


def set_last_file(path: Path | str) -> None:
    """Persist the most recently opened/saved file path and update recent list."""
    data = _load()
    path_str = str(path)
    data["last_file"] = path_str
    recents = [p for p in data.get("recent_files", []) if p != path_str]
    recents.insert(0, path_str)
    data["recent_files"] = recents[:_MAX_RECENT]
    _save(data)


def clear_recent_files() -> None:
    """Clear the recent files list."""
    data = _load()
    data["recent_files"] = []
    _save(data)
