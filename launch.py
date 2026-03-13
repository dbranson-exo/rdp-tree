"""RDP session launcher for macOS."""
import os
import subprocess
import tempfile
import threading
from pathlib import Path
from models import Server

_WINDOWS_APP_CLI = "/Applications/Windows App.app/Contents/MacOS/Windows App"


def _windows_app_available() -> bool:
    """Check if the Windows App CLI is available."""
    return Path(_WINDOWS_APP_CLI).is_file()


def _sync_bookmark(server: Server, username: str, domain: str,
                   password: str) -> None:
    """Pre-store credentials in Windows App via its CLI.

    Creates or updates a bookmark so that Windows App has the password
    in its internal keychain before the .rdp file is opened.  Best-effort;
    failures are silently ignored and the .rdp launch proceeds as usual.
    """
    host = server.settings.host
    port = server.settings.port
    s = server.settings

    cmd = [
        _WINDOWS_APP_CLI, "--script", "bookmark", "write", server.id,
        "--hostname", f"{host}:{port}" if port != 3389 else host,
        "--friendlyname", server.label,
        "--group", "RDP Tree",
    ]

    full_username = f"{domain}\\{username}" if domain else username
    if full_username:
        cmd.extend(["--username", full_username])
    if password:
        cmd.extend(["--password", password])

    # Display
    if s.fullscreen:
        cmd.extend(["--fullscreen", "true"])
    else:
        cmd.extend(["--fullscreen", "false",
                     "--resolution", f"{s.width} {s.height}"])

    # Clipboard
    cmd.extend(["--redirectclipboard", "1"])

    # Folder sharing
    if s.shared_folders:
        cmd.extend(["--redirectfolders", "true"])

    try:
        subprocess.run(cmd, capture_output=True, timeout=10)
    except Exception:
        pass


def build_rdp_file(server: Server, username: str, domain: str) -> str:
    """Generate the contents of a .rdp file for the given server and credentials."""
    lines = []

    # Connection
    host = server.settings.host
    port = server.settings.port
    lines.append(f"full address:s:{host}:{port}")

    # Credentials
    if domain:
        lines.append(f"username:s:{domain}\\{username}")
    elif username:
        lines.append(f"username:s:{username}")

    # Display
    s = server.settings
    if s.fullscreen:
        lines.append("screen mode id:i:2")
    else:
        lines.append("screen mode id:i:1")
        lines.append(f"desktopwidth:i:{s.width}")
        lines.append(f"desktopheight:i:{s.height}")

    # Folder sharing
    if s.shared_folders:
        lines.append("redirectdrives:i:1")
        lines.append("drivestoredirect:s:" + ";".join(s.shared_folders) + ";")
    else:
        lines.append("redirectdrives:i:0")

    # General settings
    lines.append("authentication level:i:2")
    lines.append("prompt for credentials:i:0")
    lines.append("negotiate security layer:i:1")
    lines.append("enablecredsspsupport:i:1")
    lines.append("redirectclipboard:i:1")
    lines.append("redirectprinters:i:0")
    lines.append("redirectcomports:i:0")
    lines.append("redirectsmartcards:i:0")
    lines.append("audiomode:i:0")

    return "\n".join(lines) + "\n"


def _cleanup_rdp_file(path: str) -> None:
    """Delete the temp .rdp file after a short delay."""
    import time
    time.sleep(5)
    try:
        os.unlink(path)
    except OSError:
        pass


def launch(server: Server, username: str, domain: str, password: str) -> None:
    """
    Write a temporary .rdp file and open it with Microsoft Remote Desktop.

    If the Windows App CLI is available and a password is provided, a
    bookmark is created/updated first so that credentials are pre-stored
    in the app's internal keychain.  The temp file is cleaned up after a
    short delay via a background thread.
    """
    # Pre-store credentials in Windows App when possible
    if password and _windows_app_available():
        _sync_bookmark(server, username, domain, password)

    rdp_content = build_rdp_file(server, username, domain)

    # Write to a named temp file (must persist until the RD app opens it)
    fd, rdp_path = tempfile.mkstemp(suffix=".rdp", prefix="rdptree_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(rdp_content)
        subprocess.Popen(["open", rdp_path])
        # Schedule deletion after 5 seconds via a background thread
        threading.Thread(target=_cleanup_rdp_file, args=(rdp_path,),
                         daemon=True).start()
    except Exception:
        try:
            os.unlink(rdp_path)
        except OSError:
            pass
        raise
