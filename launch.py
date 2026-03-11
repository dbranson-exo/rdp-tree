"""RDP session launcher for macOS."""
import os
import subprocess
import tempfile
from models import Server


def build_rdp_file(server: Server, username: str, domain: str, password: str) -> str:
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

    if password:
        # Note: storing plaintext password in the temp .rdp file.
        # The file is deleted after launching.
        lines.append(f"password 51:b:{_encode_rdp_password(password)}")

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


def launch(server: Server, username: str, domain: str, password: str) -> None:
    """
    Write a temporary .rdp file and open it with Microsoft Remote Desktop.
    The temp file is cleaned up after a short delay via a background process.
    """
    rdp_content = build_rdp_file(server, username, domain, password)

    # Write to a named temp file (must persist until the RD app opens it)
    fd, rdp_path = tempfile.mkstemp(suffix=".rdp", prefix="rdptree_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(rdp_content)
        subprocess.Popen(["open", rdp_path])
        # Schedule deletion after 5 seconds via a background shell
        subprocess.Popen(
            f"sleep 5 && rm -f {rdp_path!r}",
            shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except Exception:
        try:
            os.unlink(rdp_path)
        except OSError:
            pass
        raise


def _encode_rdp_password(password: str) -> str:
    """
    RDP password encoding (password 51:b:) is Windows DPAPI-encrypted and
    cannot be generated on macOS. We return an empty string; Microsoft Remote
    Desktop will prompt for credentials if needed.
    """
    # DPAPI is Windows-only. The RD app on macOS handles auth its own way.
    # Returning empty causes the RD app to ask for the password.
    return ""
