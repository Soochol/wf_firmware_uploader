"""Create MSI installer for WF Firmware Uploader using cx_Freeze."""
import sys
from pathlib import Path

try:
    from cx_Freeze import setup, Executable
except ImportError:
    print("cx_Freeze not installed. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "cx-freeze"])
    from cx_Freeze import setup, Executable

# Project metadata
project_root = Path(__file__).parent.parent
src_path = project_root / "src"

# Build options
build_options = {
    "packages": [
        "PySide6",
        "serial",
        "esptool",
        "core",
        "ui",
    ],
    "excludes": [
        "tkinter",
        "unittest",
        "email",
        "http",
        "urllib",
        "xml",
        "pydoc",
    ],
    "include_files": [
        # Add any additional files here if needed
    ],
    "include_msvcr": True,
}

# MSI options
bdist_msi_options = {
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFilesFolder]\WF Firmware Uploader",
    "upgrade_code": "{12345678-1234-1234-1234-123456789012}",  # Generate unique GUID
    "install_icon": None,  # Add icon path if available
}

# Executable configuration
executables = [
    Executable(
        str(src_path / "main.py"),
        base="Win32GUI",  # Use Win32GUI for windowed app
        target_name="wf_firmware_uploader.exe",
        shortcut_name="WF Firmware Uploader",
        shortcut_dir="ProgramMenuFolder",
    )
]

# Setup
setup(
    name="WF Firmware Uploader",
    version="1.0.0",
    description="GUI firmware uploader for STM32 and ESP32 microcontrollers",
    author="WF Team",
    options={
        "build_exe": build_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
