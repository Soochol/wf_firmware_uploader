#!/usr/bin/env python3
"""WF firmware uploader main application."""

import os
import platform
import sys

from PySide6.QtWidgets import QApplication

from core.settings import SettingsManager
from ui.main_window import MainWindow


def detect_platform():
    """Detect if running on WSL, Windows, or Linux."""
    system = platform.system()

    if system == "Linux":
        # Check if running on WSL
        try:
            with open("/proc/version", "r", encoding="utf-8") as f:
                if "microsoft" in f.read().lower():
                    return "WSL"
        except FileNotFoundError:
            pass
        return "Linux"
    if system == "Windows":
        return "Windows"
    else:
        return system


def setup_ui_scaling(settings_manager):
    """Setup UI scaling based on platform and settings."""
    # Get scaling settings
    ui_settings = settings_manager.settings.get("ui", {})
    auto_platform_scale = ui_settings.get("auto_platform_scale", True)
    custom_scale_factor = ui_settings.get("scale_factor", None)

    if custom_scale_factor is not None:
        # Use custom scale factor
        scale_factor = custom_scale_factor
    elif auto_platform_scale:
        # Auto platform scaling
        platform_type = detect_platform()
        if platform_type == "WSL":
            scale_factor = 1.3  # 30% larger for WSL
        elif platform_type == "Windows":
            scale_factor = 0.8  # Normal size for Windows
        else:  # Linux or other
            scale_factor = 1.2  # Slightly larger for Linux
    else:
        scale_factor = 1.0  # Default

    # Apply scaling
    os.environ["QT_SCALE_FACTOR"] = str(scale_factor)

    # Optional: Disable auto DPI scaling to use our manual scaling
    # os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "0"

    return scale_factor


def main():
    """Run the main application."""
    # Initialize settings manager
    settings_manager = SettingsManager()

    # Setup UI scaling before creating QApplication
    scale_factor = setup_ui_scaling(settings_manager)

    app = QApplication(sys.argv)
    app.setApplicationName("WF Firmware Uploader")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("WF")

    # High DPI support is enabled by default in Qt6/PySide6

    # Print scaling info for debugging
    platform_type = detect_platform()
    print(f"Platform: {platform_type}, Scale Factor: {scale_factor}")

    window = MainWindow()
    window.showMaximized()  # Start maximized

    return app.exec()


if __name__ == "__main__":
    # CRITICAL: PyInstaller multiprocessing support
    # Without this, subprocess calls (esptool.py, STM32_Programmer_CLI.exe)
    # will cause PyInstaller to spawn NEW GUI windows instead of child processes!
    import multiprocessing
    import sys

    # IMPORTANT: freeze_support() must be called BEFORE any other code
    # This prevents PyInstaller from re-executing the main script when spawning subprocesses
    multiprocessing.freeze_support()

    # Check if this is a child process spawned by multiprocessing or subprocess -m
    # If so, DO NOT start the GUI - just exit immediately or run the requested module
    # This prevents the bug where subprocess calls open new GUI windows
    if len(sys.argv) > 1:
        first_arg = sys.argv[1]
        # Check for multiprocessing child process
        if first_arg.startswith('--multiprocessing'):
            sys.exit(0)
        # Check for -m flag (module execution like "exe -m esptool")
        elif first_arg == '-m':
            # This is a subprocess calling a Python module (e.g., esptool)
            # Run the module instead of the GUI
            import runpy
            if len(sys.argv) > 2:
                module_name = sys.argv[2]
                # Remove the first two args (-m and module name) and run the module
                sys.argv = [sys.argv[0]] + sys.argv[3:]
                sys.exit(runpy.run_module(module_name, run_name="__main__"))
            else:
                sys.exit(1)  # Invalid -m usage

    # Only start GUI if this is the actual main process (not a subprocess)
    sys.exit(main())
