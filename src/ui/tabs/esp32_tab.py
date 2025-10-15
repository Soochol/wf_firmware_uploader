"""ESP32-specific tab with multi-file support."""

from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTextEdit,
)

from core.serial_utils import SerialPortManager
from core.settings import SettingsManager
from ui.widgets.counter_widget import CounterWidget


class ESP32Tab(QWidget):
    """ESP32-specific tab with multi-file support."""

    def __init__(self, settings_manager: Optional[SettingsManager] = None):
        """Initialize ESP32 tab."""
        super().__init__()
        self.device_type = "ESP32"
        self.firmware_files: list[tuple[str, str]] = []  # List of (address, filepath) tuples
        self.settings_manager = settings_manager
        self.counter_widget = None  # Will be initialized in init_ui
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        # Set 12pt font for all widgets in ESP32 tab
        self.setStyleSheet(
            """
            QLabel, QPushButton, QRadioButton, QCheckBox, QGroupBox, QComboBox {
                font-size: 12pt;
            }
        """
        )

        layout = QVBoxLayout(self)

        # === TOP ROW: 2-COLUMN LAYOUT (Firmware Files | Counter) ===
        top_row_layout = QHBoxLayout()

        # Multi-file selection group
        file_group = QGroupBox("ESP32 Firmware Files")
        file_layout = QVBoxLayout(file_group)

        # File list
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(150)
        # Increase font size for firmware file list
        self.file_list.setStyleSheet("QListWidget { font-size: 11pt; }")
        # Enable editing on double-click
        self.file_list.itemDoubleClicked.connect(self.edit_firmware_file)
        file_layout.addWidget(QLabel("Files to upload (double-click to edit address):"))
        file_layout.addWidget(self.file_list)

        # File control buttons
        file_btn_layout = QHBoxLayout()

        add_file_btn = QPushButton("Add File...")
        add_file_btn.clicked.connect(self.add_firmware_file)
        file_btn_layout.addWidget(add_file_btn)

        remove_file_btn = QPushButton("Remove File")
        remove_file_btn.clicked.connect(self.remove_firmware_file)
        file_btn_layout.addWidget(remove_file_btn)

        clear_files_btn = QPushButton("Clear All")
        clear_files_btn.clicked.connect(self.clear_firmware_files)
        file_btn_layout.addWidget(clear_files_btn)

        file_btn_layout.addStretch()
        file_layout.addLayout(file_btn_layout)

        # Quick setup buttons
        quick_layout = QHBoxLayout()

        single_app_btn = QPushButton("Single App (0x10000)")
        single_app_btn.clicked.connect(self.setup_single_app)
        quick_layout.addWidget(single_app_btn)

        full_build_btn = QPushButton("Full Build...")
        full_build_btn.clicked.connect(self.setup_full_build)
        quick_layout.addWidget(full_build_btn)

        quick_layout.addStretch()
        file_layout.addLayout(quick_layout)

        # Add file_group to top row (LEFT COLUMN - 60% width)
        top_row_layout.addWidget(file_group, 60)

        # RIGHT COLUMN: Counter Widget (40% width)
        self.counter_widget = CounterWidget(device_type=self.device_type)
        # Load saved counters
        if self.settings_manager:
            total, passed, failed = self.settings_manager.get_counters(self.device_type)
            self.counter_widget.set_counters(total, passed, failed)

        # Connect counter signals
        self.counter_widget.counters_reset.connect(self.on_counters_reset)

        top_row_layout.addWidget(self.counter_widget, 40)

        layout.addLayout(top_row_layout)

        # ============================================================
        # UNIFIED ESP32 SETTINGS CARD (3-COLUMN LAYOUT)
        # ============================================================
        settings_group = QGroupBox("ESP32 Settings")
        settings_layout = QVBoxLayout(settings_group)

        # 3-column layout for all settings
        three_column_layout = QHBoxLayout()

        # ============================================================
        # COLUMN 1: Port & Baud Rate (33% width)
        # ============================================================
        column1 = QVBoxLayout()

        # Serial Port
        port_label = QLabel("Serial Port")
        port_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        column1.addWidget(port_label)

        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        port_row.addWidget(self.port_combo, stretch=3)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        port_row.addWidget(refresh_btn, stretch=1)
        column1.addLayout(port_row)

        column1.addSpacing(10)

        # Baud Rate
        baud_label = QLabel("Baud Rate")
        baud_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        column1.addWidget(baud_label)

        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "230400", "460800", "921600"])
        self.baud_combo.setCurrentText("921600")
        self.baud_combo.currentTextChanged.connect(self.on_settings_changed)
        column1.addWidget(self.baud_combo)

        column1.addStretch()

        # ============================================================
        # COLUMN 2: Full Erase & Connection Options (34% width)
        # ============================================================
        column2 = QVBoxLayout()

        # Full Erase
        self.full_erase_checkbox = QCheckBox("Full Erase")
        self.full_erase_checkbox.setToolTip("Erase entire flash memory before uploading firmware")
        self.full_erase_checkbox.setStyleSheet("font-weight: bold; margin-bottom: 10px;")
        column2.addWidget(self.full_erase_checkbox)

        # Connection Options
        connection_label = QLabel("Connection Options")
        connection_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        column2.addWidget(connection_label)

        self.before_reset_checkbox = QCheckBox("Reset before")
        self.before_reset_checkbox.setToolTip("--before default-reset")
        self.before_reset_checkbox.setChecked(True)
        self.before_reset_checkbox.toggled.connect(self.on_settings_changed)
        column2.addWidget(self.before_reset_checkbox)

        self.after_reset_checkbox = QCheckBox("Reset after")
        self.after_reset_checkbox.setToolTip("--after hard-reset")
        self.after_reset_checkbox.setChecked(True)
        self.after_reset_checkbox.toggled.connect(self.on_settings_changed)
        column2.addWidget(self.after_reset_checkbox)

        self.no_sync_checkbox = QCheckBox("No-sync mode")
        self.no_sync_checkbox.setToolTip("--before no-reset-no-sync")
        self.no_sync_checkbox.setChecked(False)
        self.no_sync_checkbox.toggled.connect(self.on_no_sync_changed)
        self.no_sync_checkbox.toggled.connect(self.on_settings_changed)
        column2.addWidget(self.no_sync_checkbox)

        column2.addStretch()

        # ============================================================
        # COLUMN 3: Automatic Mode & Connection Attempts (33% width)
        # ============================================================
        column3 = QVBoxLayout()

        # Automatic Mode
        self.auto_mode_checkbox = QCheckBox("Automatic Mode")
        self.auto_mode_checkbox.setToolTip(
            "Automatic mode: Waits for ESP32 connection and automatically uploads.\n\n"
            "Perfect for production workflow:\n"
            "1. Click 'Upload ESP32' button\n"
            "2. Connect USB cable to ESP32\n"
            "3. Power on ESP32\n"
            "4. Upload starts automatically!\n"
            "5. Replace ESP32 and repeat\n\n"
            "No manual button clicking needed between boards."
        )
        self.auto_mode_checkbox.setStyleSheet("font-weight: bold; color: #ff6b00; margin-bottom: 10px;")
        column3.addWidget(self.auto_mode_checkbox)

        # Connection Attempts
        attempts_label = QLabel("Connection Attempts")
        attempts_label.setStyleSheet("font-weight: bold; margin-bottom: 5px;")
        column3.addWidget(attempts_label)

        self.connect_attempts_combo = QComboBox()
        self.connect_attempts_combo.addItems(["1", "3", "5", "10"])
        self.connect_attempts_combo.setCurrentText("1")
        self.connect_attempts_combo.currentTextChanged.connect(self.on_settings_changed)
        column3.addWidget(self.connect_attempts_combo)

        column3.addStretch()

        # Add all columns to 3-column layout
        three_column_layout.addLayout(column1, 33)
        three_column_layout.addLayout(column2, 34)
        three_column_layout.addLayout(column3, 33)

        settings_layout.addLayout(three_column_layout)
        layout.addWidget(settings_group)

        # Upload controls
        upload_layout = QHBoxLayout()

        self.upload_btn = QPushButton("Upload ESP32")
        self.upload_btn.setMinimumHeight(60)
        self.upload_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        )
        upload_layout.addWidget(self.upload_btn)

        self.erase_btn = QPushButton("Erase Flash")
        self.erase_btn.setMinimumHeight(60)
        upload_layout.addWidget(self.erase_btn)

        layout.addLayout(upload_layout)

        # Reset guidance label
        self.reset_guidance_label = QLabel("💡 Press ESP32 RESET button now")
        self.reset_guidance_label.setVisible(False)

        # Set font for better visibility
        guidance_font = QFont()
        guidance_font.setBold(True)
        guidance_font.setPointSize(10)
        self.reset_guidance_label.setFont(guidance_font)

        self.reset_guidance_label.setStyleSheet(
            """
            QLabel {
                background-color: #ff5722;
                color: white;
                padding: 10px;
                border-radius: 6px;
                border: 3px solid #d32f2f;
                font-size: 14px;
                font-weight: bold;
            }
        """
        )
        self.reset_guidance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.reset_guidance_label)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel("ESP32: Ready")
        layout.addWidget(self.status_label)

        # ESP32 log section
        self.log_group = QGroupBox("ESP32 Log")
        self.log_group.setProperty("class", "log-group")  # Add CSS class
        self.log_group.setStyleSheet(
            """
    QGroupBox.log-group {
        font-size: 12pt !important;
        font-weight: bold !important;
        border: 2px solid #cccccc;
        border-radius: 8px;
        margin-top: 10px;
        padding-top: 10px;
    }
    QGroupBox.log-group::title {
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 5px 0 5px;
    }
"""
        )
        log_layout = QVBoxLayout(self.log_group)

        # Log controls
        log_controls = QHBoxLayout()
        self.clear_log_btn = QPushButton("Clear ESP32 Log")
        self.clear_log_btn.setProperty("class", "log-widget")  # Add CSS class
        self.clear_log_btn.setStyleSheet(
            """
    QPushButton.log-widget {
        font-size: 10pt !important;
        padding: 5px 10px;
        background-color: #f44336;
        color: white;
        border: none;
        border-radius: 4px;
    }
    QPushButton.log-widget:hover {
        background-color: #d32f2f;
    }
"""
        )
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_controls.addWidget(self.clear_log_btn)

        log_controls.addStretch()

        self.save_log_btn = QPushButton("Save ESP32 Log")
        self.save_log_btn.setProperty("class", "log-widget")  # Add CSS class
        self.save_log_btn.setStyleSheet(
            """
    QPushButton.log-widget {
        font-size: 10pt !important;
        padding: 5px 10px;
        background-color: #2196F3;
        color: white;
        border: none;
        border-radius: 4px;
    }
    QPushButton.log-widget:hover {
        background-color: #1976D2;
    }
"""
        )
        self.save_log_btn.clicked.connect(self.save_log)
        log_controls.addWidget(self.save_log_btn)

        log_layout.addLayout(log_controls)

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setMinimumHeight(120)
        self.log_text.setFont(QFont("Courier", 10))
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet(
            """
    QTextEdit {
        background-color: #2b2b2b;
        color: #ffffff;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 5px;
        font-family: 'Courier New', monospace;
    }
"""
        )
        log_layout.addWidget(self.log_text)

        layout.addWidget(self.log_group, stretch=1)

        # Initialize ports
        self.refresh_ports()

    def add_firmware_file(self):
        """Add a firmware file with address."""
        from PySide6.QtWidgets import QInputDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ESP32 Firmware File", "", "Binary Files (*.bin);;All Files (*)"
        )
        if file_path:
            # Auto-detect address based on filename
            suggested_address = self.get_address_for_file(file_path)
            filename = Path(file_path).name

            # Let user confirm or modify the address
            is_bootloader = "bootloader" in filename.lower()
            hint = ""
            if is_bootloader:
                hint = "\n\nNote: ESP32-S3/C3/C6/H2 use 0x0, ESP32 Classic uses 0x1000"

            address, ok = QInputDialog.getText(
                self,
                "Flash Address",
                f"Enter flash address for {filename}:{hint}",
                text=suggested_address,
            )

            if ok and address:
                # Validate hex address format
                try:
                    int(address, 16)  # Check if valid hex
                    self.firmware_files.append((address, file_path))
                    self.update_file_list()
                    # Auto-save settings when file is added
                    self.save_settings()
                    if self.settings_manager:
                        self.settings_manager.save_settings()
                except ValueError:
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Invalid Address")
                    msg.setText(f"Invalid hex address: {address}\nPlease use format: 0x1000")
                    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                    msg.exec()

    def get_address_for_file(self, file_path: str) -> str:
        """Get flash address for file (simple heuristic).

        Note: For ESP32-S3/C3/C6/H2, bootloader is at 0x0 instead of 0x1000.
        This method uses ESP32 Classic addresses. Users should use 'Full Build'
        button for automatic chip detection or manually adjust addresses.
        """
        filename = Path(file_path).name.lower()

        # Common ESP32 file patterns (ESP32 Classic addresses)
        # WARNING: ESP32-S3/C3/C6/H2 use different addresses!
        if "bootloader" in filename:
            return "0x1000"  # ESP32 Classic (0x0 for S3/C3/C6/H2)
        if "partition" in filename or "partitions" in filename:
            return "0x8000"
        if "ota_data" in filename:
            return "0xd000"
        if any(name in filename for name in ["app", "firmware", "main"]):
            return "0x10000"
        # Default to application area
        return "0x10000"

    def setup_single_app(self):
        """Quick setup for single application file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ESP32 Application File", "", "Binary Files (*.bin);;All Files (*)"
        )
        if file_path:
            self.firmware_files = [("0x10000", file_path)]
            self.update_file_list()
            # Auto-save settings
            self.save_settings()
            if self.settings_manager:
                self.settings_manager.save_settings()

    def setup_full_build(self):
        """Quick setup for full ESP32 build directory with automatic chip detection."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select ESP32 Build Directory")
        if dir_path:
            build_path = Path(dir_path)
            self.firmware_files = []

            # Detect chip type from bootloader (ESP32-S3/C3/C6/H2 use different addresses)
            bootloader_address = "0x1000"  # Default for ESP32 Classic

            # Check if this is an ESP32-S3/C3/C6/H2 build by looking at flasher_args.json
            flasher_args_path = build_path / "flasher_args.json"
            if flasher_args_path.exists():
                try:
                    import json

                    with open(flasher_args_path, "r", encoding="utf-8") as f:
                        flasher_args = json.load(f)
                        # Check flash_files for bootloader address
                        flash_files = flasher_args.get("flash_files", {})
                        if "0x0" in flash_files or any("0x0" in k for k in flash_files.keys()):
                            bootloader_address = "0x0"  # ESP32-S3/C3/C6/H2
                except Exception:
                    pass  # Fall back to ESP32 Classic addresses

            # Look for common ESP32 build files with correct addresses
            files_to_check = [
                (bootloader_address, "bootloader.bin"),
                ("0x8000", "partition-table.bin"),
                ("0x8000", "partitions.bin"),
                ("0xd000", "ota_data_initial.bin"),
                ("0x10000", "*.bin"),  # Application binary
            ]

            for address, pattern in files_to_check:
                if "*" in pattern:
                    # Find application binary
                    for bin_file in build_path.glob("*.bin"):
                        if bin_file.name not in [
                            "bootloader.bin",
                            "partition-table.bin",
                            "partitions.bin",
                            "ota_data_initial.bin",
                        ]:
                            self.firmware_files.append((address, str(bin_file)))
                            break
                else:
                    file_path = build_path / pattern
                    if file_path.exists():
                        self.firmware_files.append((address, str(file_path)))

            self.update_file_list()
            # Auto-save settings
            self.save_settings()
            if self.settings_manager:
                self.settings_manager.save_settings()

    def edit_firmware_file(self, item):
        """Edit the flash address of a firmware file."""
        from PySide6.QtWidgets import QInputDialog

        current_row = self.file_list.row(item)
        if current_row >= 0:
            old_address, filepath = self.firmware_files[current_row]
            filename = Path(filepath).name

            # Check if this is a bootloader to show helpful hint
            is_bootloader = "bootloader" in filename.lower()
            hint = ""
            if is_bootloader:
                hint = "\n\nNote: ESP32-S3/C3/C6/H2 use 0x0, ESP32 Classic uses 0x1000"

            new_address, ok = QInputDialog.getText(
                self,
                "Edit Flash Address",
                f"Enter new flash address for {filename}:{hint}",
                text=old_address,
            )

            if ok and new_address:
                # Validate hex address format
                try:
                    int(new_address, 16)  # Check if valid hex
                    # Update the address
                    self.firmware_files[current_row] = (new_address, filepath)
                    self.update_file_list()
                    # Auto-save settings
                    self.save_settings()
                    if self.settings_manager:
                        self.settings_manager.save_settings()
                except ValueError:
                    msg = QMessageBox(self)
                    msg.setIcon(QMessageBox.Icon.Warning)
                    msg.setWindowTitle("Invalid Address")
                    msg.setText(f"Invalid hex address: {new_address}\nPlease use format: 0x1000")
                    msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                    msg.exec()

    def remove_firmware_file(self):
        """Remove selected firmware file."""
        current_row = self.file_list.currentRow()
        if current_row >= 0:
            del self.firmware_files[current_row]
            self.update_file_list()
            # Auto-save settings
            self.save_settings()
            if self.settings_manager:
                self.settings_manager.save_settings()

    def clear_firmware_files(self):
        """Clear all firmware files."""
        self.firmware_files = []
        self.update_file_list()
        # Auto-save settings
        self.save_settings()
        if self.settings_manager:
            self.settings_manager.save_settings()

    def update_file_list(self):
        """Update the file list display."""
        self.file_list.clear()
        for address, filepath in self.firmware_files:
            item_text = f"{address}: {Path(filepath).name}"
            item = QListWidgetItem(item_text)
            item.setToolTip(filepath)
            self.file_list.addItem(item)

    def refresh_ports(self):
        """Refresh serial port list."""
        current_port = self.port_combo.currentText()
        self.port_combo.clear()

        ports = SerialPortManager.get_available_ports()
        for port in ports:
            display_text = SerialPortManager.format_port_display(port)
            self.port_combo.addItem(display_text, port["device"])

        if current_port:
            index = self.port_combo.findData(current_port)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)

    def get_firmware_files(self) -> list:
        """Return firmware files list."""
        return self.firmware_files

    def get_selected_port(self) -> str:
        """Return selected port."""
        return self.port_combo.currentData() or ""

    def is_full_erase_enabled(self) -> bool:
        """Return full erase checkbox state."""
        return self.full_erase_checkbox.isChecked()

    def set_upload_enabled(self, enabled: bool):
        """Set upload button state."""
        self.upload_btn.setEnabled(enabled)
        self.erase_btn.setEnabled(enabled)

    def start_progress(self):
        """Start progress display."""
        # Start with static progress bar (waiting state)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setVisible(True)
        self.set_upload_enabled(False)

    def finish_progress(self, success: bool):
        """Finish progress display."""
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1 if success else 0)
        self.set_upload_enabled(True)

    def update_status(self, message: str):
        """Update status message."""
        self.status_label.setText(f"ESP32: {message}")

    def load_settings(self):
        """Load settings for ESP32."""
        if not self.settings_manager:
            return

        # Load ESP32 firmware files
        last_files = self.settings_manager.get_esp32_last_firmware_files()
        if last_files:
            # Filter out files that no longer exist
            valid_files = [
                (addr, path)
                for addr, path in last_files
                if self.settings_manager.validate_file_exists(path)
            ]
            self.firmware_files = valid_files
            self.update_file_list()

        # Load ESP32 port
        last_port = self.settings_manager.get_esp32_last_port()
        if last_port:
            index = self.port_combo.findData(last_port)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)

        # Load full erase setting
        full_erase = self.settings_manager.get_esp32_full_erase()
        self.full_erase_checkbox.setChecked(full_erase)

        # Load automatic mode setting
        if hasattr(self, "auto_mode_checkbox"):
            auto_mode = self.settings_manager.get_esp32_auto_mode()
            self.auto_mode_checkbox.setChecked(auto_mode)

        # Load advanced settings
        baud_rate = self.settings_manager.get_esp32_baud_rate()
        self.baud_combo.setCurrentText(str(baud_rate))

        before_reset = self.settings_manager.get_esp32_before_reset()
        self.before_reset_checkbox.setChecked(before_reset)

        after_reset = self.settings_manager.get_esp32_after_reset()
        self.after_reset_checkbox.setChecked(after_reset)

        no_sync = self.settings_manager.get_esp32_no_sync()
        self.no_sync_checkbox.setChecked(no_sync)

        connect_attempts = self.settings_manager.get_esp32_connect_attempts()
        self.connect_attempts_combo.setCurrentText(str(connect_attempts))

    def save_settings(self):
        """Save current settings for ESP32."""
        if not self.settings_manager:
            return

        # Save ESP32 firmware files
        if self.firmware_files:
            self.settings_manager.set_esp32_last_firmware_files(self.firmware_files)

        # Save ESP32 port
        current_port = self.get_selected_port()
        if current_port:
            self.settings_manager.set_esp32_last_port(current_port)

        # Save full erase setting
        self.settings_manager.set_esp32_full_erase(self.is_full_erase_enabled())

        # Save automatic mode setting
        if hasattr(self, "auto_mode_checkbox"):
            self.settings_manager.set_esp32_auto_mode(self.auto_mode_checkbox.isChecked())

        # Save advanced settings
        self.settings_manager.set_esp32_baud_rate(int(self.baud_combo.currentText()))
        self.settings_manager.set_esp32_before_reset(self.before_reset_checkbox.isChecked())
        self.settings_manager.set_esp32_after_reset(self.after_reset_checkbox.isChecked())
        self.settings_manager.set_esp32_no_sync(self.no_sync_checkbox.isChecked())
        self.settings_manager.set_esp32_connect_attempts(
            int(self.connect_attempts_combo.currentText())
        )

    def on_settings_changed(self):
        """Handle settings change - auto-save settings."""
        self.save_settings()
        if self.settings_manager:
            self.settings_manager.save_settings()

    def on_no_sync_changed(self, checked: bool):
        """Handle no-sync checkbox change."""
        if checked:
            # When no-sync is enabled, disable before_reset
            self.before_reset_checkbox.setChecked(False)
            self.before_reset_checkbox.setEnabled(False)
        else:
            # When no-sync is disabled, re-enable before_reset
            self.before_reset_checkbox.setEnabled(True)

    def get_connection_settings(self) -> dict:
        """Get current connection settings."""
        return {
            "baud_rate": int(self.baud_combo.currentText()),
            "before_reset": self.before_reset_checkbox.isChecked(),
            "after_reset": self.after_reset_checkbox.isChecked(),
            "no_sync": self.no_sync_checkbox.isChecked(),
            "connect_attempts": int(self.connect_attempts_combo.currentText()),
        }

    def show_reset_guidance(self):
        """Show reset button guidance label."""
        self.reset_guidance_label.setVisible(True)

    def hide_reset_guidance(self):
        """Hide reset button guidance label."""
        self.reset_guidance_label.setVisible(False)

    def append_log(self, message: str):
        """Add message to ESP32 log."""
        from datetime import datetime

        current_time = datetime.now().strftime("%H:%M:%S")
        formatted_msg = f"[{current_time}] {message}"

        self.log_text.append(formatted_msg)

        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()

    def clear_log(self):
        """Clear ESP32 log."""
        self.log_text.clear()
        # Reset log background to default when clearing
        self.set_log_background_color("#2b2b2b")

    def set_log_background_color(self, color: str):
        """Set log background color."""
        self.log_text.setStyleSheet(
            f"""
            QTextEdit {{
                background-color: {color};
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 4px;
                padding: 5px;
                font-family: 'Courier New', monospace;
            }}
        """
        )

    def save_log(self):
        """Save ESP32 log to file."""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save ESP32 Log", "esp32_log.txt", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write("=== ESP32 Upload Log ===\n\n")
                    f.write(self.log_text.toPlainText())
                self.append_log(f"Log saved to: {file_path}")
            except Exception as e:
                self.append_log(f"Failed to save log: {str(e)}")

    def on_counters_reset(self):
        """Handle counter reset signal."""
        # Save reset counters to settings
        if self.settings_manager:
            self.settings_manager.reset_counters(self.device_type)
            self.settings_manager.save_settings()
        self.append_log(f"{self.device_type} counters reset")
