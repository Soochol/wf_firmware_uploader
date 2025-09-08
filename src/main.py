#!/usr/bin/env python3
"""WF firmware uploader main application."""

import sys

from PySide6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main():
    """Run the main application."""
    app = QApplication(sys.argv)
    app.setApplicationName("WF Firmware Uploader")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("WF")

    # High DPI support is enabled by default in Qt6/PySide6

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
