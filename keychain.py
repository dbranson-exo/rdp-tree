"""macOS Keychain integration for storing RDP passwords."""
import subprocess

_SERVICE = "RDPTree"


def _account_key(server_id: str) -> str:
    return f"rdptree:{server_id}"


def get_password(server_id: str) -> str | None:
    """Retrieve a password from the macOS Keychain. Returns None if not found."""
    try:
        result = subprocess.run(
            ["security", "find-generic-password",
             "-s", _SERVICE,
             "-a", _account_key(server_id),
             "-w"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def set_password(server_id: str, password: str) -> bool:
    """Store a password in the macOS Keychain. Returns True on success."""
    try:
        result = subprocess.run(
            ["security", "add-generic-password",
             "-s", _SERVICE,
             "-a", _account_key(server_id),
             "-w", password,
             "-U"],  # -U = update if exists
            capture_output=True
        )
        return result.returncode == 0
    except Exception:
        return False


def delete_password(server_id: str) -> bool:
    """Remove a password from the macOS Keychain. Returns True on success."""
    try:
        result = subprocess.run(
            ["security", "delete-generic-password",
             "-s", _SERVICE,
             "-a", _account_key(server_id)],
            capture_output=True
        )
        return result.returncode == 0
    except Exception:
        return False
