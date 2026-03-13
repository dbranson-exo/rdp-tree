"""py2app build configuration for RDP Tree."""
from setuptools import setup

APP = ["rdptree.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "plist": {
        "CFBundleName": "RDP Tree",
        "CFBundleDisplayName": "RDP Tree",
        "CFBundleIdentifier": "com.radiantglobal.rdptree",
        "CFBundleVersion": "1.4.0",
        "CFBundleShortVersionString": "1.4.0",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "RDP Tree File",
                "CFBundleTypeExtensions": ["rdptree"],
                "CFBundleTypeRole": "Editor",
                "LSHandlerRank": "Owner",
            }
        ],
    },
    "includes": ["tkinter", "tkinter.ttk"],
    "excludes": ["matplotlib", "numpy", "PIL", "scipy", "wx"],
}

setup(
    name="RDP Tree",
    app=APP,
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
