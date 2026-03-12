"""Export RDP Tree data model to RDCMan .rdg XML format."""
import xml.etree.ElementTree as ET
from xml.dom import minidom

from models import Group, Server


def export_rdg(root_group: Group, path: str) -> None:
    """Write root_group tree to an RDCMan v3 .rdg file at path."""
    rdcman = ET.Element("RDCMan", programVersion="2.7", schemaVersion="3")
    file_el = ET.SubElement(rdcman, "file")
    ET.SubElement(file_el, "credentialsProfiles")
    _add_properties(file_el, root_group.name, root_group.expanded)
    _add_children(file_el, root_group)

    xml_str = ET.tostring(rdcman, encoding="unicode")
    pretty = minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="utf-8")
    with open(path, "wb") as f:
        f.write(pretty)


def _add_properties(parent: ET.Element, name: str, expanded: bool) -> None:
    props = ET.SubElement(parent, "properties")
    _sub_text(props, "expanded", str(expanded))
    _sub_text(props, "name", name)


def _add_children(parent_el: ET.Element, group: Group) -> None:
    for child in group.children:
        if isinstance(child, Group):
            _add_group(parent_el, child)
        elif isinstance(child, Server):
            _add_server(parent_el, child)


def _add_group(parent_el: ET.Element, group: Group) -> None:
    el = ET.SubElement(parent_el, "group")
    _add_properties(el, group.name, group.expanded)
    if group.default_username or group.default_domain:
        _add_credentials(el, group.default_username, group.default_domain)
    _add_children(el, group)


def _add_server(parent_el: ET.Element, server: Server) -> None:
    s = server.settings
    el = ET.SubElement(parent_el, "server")

    props = ET.SubElement(el, "properties")
    _sub_text(props, "name", s.host)
    if server.display_name:
        _sub_text(props, "displayName", server.display_name)
    if s.notes:
        _sub_text(props, "comment", s.notes)

    if s.port != 3389:
        conn = ET.SubElement(el, "connectionSettings", inherit="FromParent")
        _sub_text(conn, "port", str(s.port))

    desktop = ET.SubElement(el, "remoteDesktop", inherit="FromParent")
    _sub_text(desktop, "fullScreen", str(s.fullscreen))
    _sub_text(desktop, "width", str(s.width))
    _sub_text(desktop, "height", str(s.height))

    if s.shared_folders:
        local_res = ET.SubElement(el, "localResources", inherit="FromParent")
        drives = ET.SubElement(local_res, "drives")
        _sub_text(drives, "driveSelection", "Custom")
        for folder in s.shared_folders:
            _sub_text(drives, "drive", folder)

    if s.username or s.domain:
        _add_credentials(el, s.username, s.domain)


def _add_credentials(parent: ET.Element, username: str, domain: str) -> None:
    creds = ET.SubElement(parent, "logonCredentials", inherit="None")
    profile = ET.SubElement(creds, "profileName", inherit="None")
    profile.text = "Custom"
    _sub_text(creds, "userName", username)
    _sub_text(creds, "domain", domain)


def _sub_text(parent: ET.Element, tag: str, text: str) -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = text
    return el
