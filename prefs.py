"""User preferences for RDP Tree."""
import json
from pathlib import Path

_PREFS_PATH = Path.home() / "Library" / "Preferences" / "rdptree.json"


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


def set_last_file(path: Path | str) -> None:
    """Persist the most recently opened/saved file path."""
    data = _load()
    data["last_file"] = str(path)
    _save(data)
