#!/usr/bin/env python3
"""WF firmware uploader main application."""

import os
import platform
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.settings import SettingsManager
from ui.main_window import MainWindow


def detect_platform():
    """Detect if running on WSL, Windows, or Linux."""
    system = platform.system()

    if system == "Linux":
        # Check if running on WSL
        try:
            with open("/proc/version", "r") as f:
                if "microsoft" in f.read().lower():
                    return "WSL"
        except FileNotFoundError:
            pass
        return "Linux"
    elif system == "Windows":
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
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
