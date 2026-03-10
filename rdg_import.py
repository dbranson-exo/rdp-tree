"""Import RDCMan .rdg XML files into the RDP Tree data model."""
import xml.etree.ElementTree as ET
from models import Group, Server, ServerSettings


def import_rdg(path: str) -> Group:
    """
    Parse an RDCMan .rdg file and return a root Group containing the tree.
    Raises ValueError on parse errors.
    """
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        raise ValueError(f"Could not parse RDG file: {e}") from e

    root_el = tree.getroot()
    if root_el.tag != "RDCMan":
        raise ValueError("Not a valid RDCMan file (missing <RDCMan> root element)")

    # The file element holds the top-level name and children
    file_el = root_el.find("file")
    if file_el is None:
        raise ValueError("No <file> element found in RDG")

    file_name = _get_text(file_el, "properties/name") or "Imported"
    root_group = Group(name=file_name)

    _parse_children(file_el, root_group)
    return root_group


def _parse_children(parent_el: ET.Element, parent_group: Group) -> None:
    """Recursively parse group and server elements into parent_group.children."""
    for child_el in parent_el:
        if child_el.tag == "group":
            group = _parse_group(child_el)
            parent_group.children.append(group)
        elif child_el.tag == "server":
            server = _parse_server(child_el, parent_group)
            parent_group.children.append(server)


def _parse_group(el: ET.Element) -> Group:
    name = _get_text(el, "properties/name") or "Group"
    expanded_str = _get_text(el, "properties/expanded") or "True"
    expanded = expanded_str.lower() == "true"

    group = Group(name=name, expanded=expanded)

    # Group-level default credentials
    creds_el = el.find("logonCredentials")
    if creds_el is not None and creds_el.get("inherit", "FromParent") == "None":
        group.default_username = _get_text(creds_el, "userName") or ""
        group.default_domain = _get_text(creds_el, "domain") or ""

    _parse_children(el, group)
    return group


def _parse_server(el: ET.Element, parent_group: Group) -> Server:
    host = _get_text(el, "properties/name") or ""
    display_name = _get_text(el, "properties/displayName") or ""
    notes = _get_text(el, "properties/comment") or ""

    # Per-server credentials
    username = ""
    domain = ""
    creds_el = el.find("logonCredentials")
    if creds_el is not None and creds_el.get("inherit", "FromParent") == "None":
        username = _get_text(creds_el, "userName") or ""
        domain = _get_text(creds_el, "domain") or ""

    # Connection settings
    port = 3389
    conn_el = el.find("connectionSettings")
    if conn_el is not None:
        port_str = _get_text(conn_el, "port")
        if port_str and port_str.isdigit():
            port = int(port_str)

    # Display settings
    width, height, fullscreen = 1920, 1080, False
    display_el = el.find("remoteDesktop")
    if display_el is not None:
        fs_str = _get_text(display_el, "fullScreen")
        if fs_str:
            fullscreen = fs_str.lower() == "true"
        w_str = _get_text(display_el, "width")
        h_str = _get_text(display_el, "height")
        if w_str and w_str.isdigit():
            width = int(w_str)
        if h_str and h_str.isdigit():
            height = int(h_str)

    settings = ServerSettings(
        host=host,
        port=port,
        username=username,
        domain=domain,
        width=width,
        height=height,
        fullscreen=fullscreen,
        notes=notes,
    )
    return Server(display_name=display_name, settings=settings)


def _get_text(el: ET.Element, path: str) -> str | None:
    """Find a nested element by path and return its text, or None."""
    found = el.find(path)
    if found is not None and found.text:
        return found.text.strip()
    return None
