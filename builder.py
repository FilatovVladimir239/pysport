import subprocess
import sys
from importlib.util import find_spec
from pathlib import Path

from cx_Freeze import Executable, setup

from sportorg import config


def _ensure_commit_version_file() -> None:
    path = Path(config.COMMIT_VERSION_FILE)
    if path.exists():
        return
    commit = ""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        commit = result.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        pass
    path.write_text(commit, encoding="utf-8")


_ensure_commit_version_file()

base = None
if sys.platform == "win32":
    base = "Win32GUI"

include_files = [
    (config.base_dir("sportorg", "data"), "lib/sportorg/data"),
    config.base_dir("LICENSE"),
    config.base_dir("changelog.md"),
    config.base_dir("changelog_ru.md"),
    (config.base_dir("configs"), "configs"),
    config.COMMIT_VERSION_FILE,
]
includes = ["atexit", "codecs", "playsound3", "pyImpinj"]
if find_spec("sportorg_rust_example") is not None:
    includes.append("sportorg_rust_example")
if find_spec("sportorg_core") is not None:
    includes.append("sportorg_core")
excludes = ["Tkinter", "unittest", "test", "pydoc"]

build_exe_options = {
    "includes": includes,
    "excludes": excludes,
    "packages": ["idna", "requests", "encodings", "asyncio", "pywinusb"],
    "include_files": include_files,
    "zip_include_packages": ["PySide6"],
    "optimize": 2,
    "include_msvcr": True,
    "silent": 1,
}

bdist_msi_options = {
    "all_users": False,
    "data": {
        "Shortcut": [
            (
                "DesktopShortcut",  # Shortcut
                "DesktopFolder",  # Directory
                config.NAME,  # Name
                "TARGETDIR",  # Component
                "[TARGETDIR]SportOrg.exe",  # Target
                None,  # Arguments
                None,  # Description
                None,  # Hotkey
                None,  # Icon
                None,  # IconIndex
                None,  # ShowCmd
                "TARGETDIR",  # WkDir
            ),
        ]
    },
}

options = {"build_exe": build_exe_options, "bdist_msi": bdist_msi_options}

executables = [
    Executable(
        "SportOrg.pyw",
        base=base,
        icon=config.icon_dir("sportorg.ico"),
        copyright="GNU GENERAL PUBLIC LICENSE {}".format(config.NAME),
    )
]

setup(
    name=config.NAME,
    version=config.VERSION,
    description=config.NAME,
    options=options,
    executables=executables,
)
