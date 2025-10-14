"""Main window module."""

from pathlib import Path
from typing import Any, Optional, Union

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.esp32_uploader import ESP32Uploader
from core.serial_boot_controller import SerialBootController
from core.serial_utils import SerialPortManager
from core.settings import SettingsManager
from core.stm32_uploader import STM32Uploader


class UploadWorkerThread(QThread):
    """Worker thread for firmware upload tasks."""

    progress_update = Signal(str, str)  # device_type, message
    upload_finished = Signal(str, bool, list, bool)  # device_type, success, corrected_files, was_fixed

    def __init__(self, device_type, uploader, full_erase=False, erase_only=False, **kwargs):
        """Initialize worker thread."""
        super().__init__()
        self.device_type = device_type
        self.uploader = uploader
        self.full_erase = full_erase
        self.erase_only = erase_only
        self.kwargs = kwargs

    def run(self):
        """Execute upload task with optional full erase."""

        def progress_callback(message):
            try:
                self.progress_update.emit(self.device_type, message)
            except Exception:
                # Silent fail for GUI update errors
                pass

        try:
            success = True
            corrected_files = []
            was_fixed = False

            # Step 1: Full erase if requested
            if self.full_erase or self.erase_only:
                progress_callback("Starting full flash erase...")
                port = self.kwargs.get("port", "")
                erase_success = self.uploader.erase_flash(port, progress_callback=progress_callback)
                if not erase_success:
                    progress_callback("Flash erase failed")
                    self.upload_finished.emit(self.device_type, False, [], False)
                    return
                progress_callback("Flash erase completed successfully")

                # If erase-only mode, we're done
                if self.erase_only:
                    self.upload_finished.emit(self.device_type, True, [], False)
                    return

            # Step 2: Upload firmware (only if not erase-only)
            progress_callback("Starting firmware upload...")

            # ESP32 uploader returns tuple with corrected files info
            if self.device_type == "ESP32":
                result = self.uploader.upload_firmware(
                    progress_callback=progress_callback, **self.kwargs
                )
                if isinstance(result, tuple) and len(result) == 3:
                    success, corrected_files, was_fixed = result
                else:
                    success = result
            else:
                success = self.uploader.upload_firmware(
                    progress_callback=progress_callback, **self.kwargs
                )

            self.upload_finished.emit(self.device_type, success, corrected_files, was_fixed)

        except Exception as e:
            try:
                error_msg = f"Upload error: {str(e)}"
                self.progress_update.emit(self.device_type, error_msg)
                self.upload_finished.emit(self.device_type, False, [], False)
            except Exception:
                # If even error reporting fails, just emit failure
                try:
                    self.upload_finished.emit(self.device_type, False, [], False)
                except Exception:
                    # Last resort - do nothing if everything fails
                    pass


class DeviceTab(QWidget):
    """Device-specific tab widget."""

    def __init__(
        self, device_type: str, file_filter: str, settings_manager: Optional[SettingsManager] = None
    ):
        """Initialize device tab."""
        super().__init__()
        self.device_type = device_type
        self.file_filter = file_filter
        self.settings_manager = settings_manager
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        # Set 10pt font for all widgets except log widgets
        self.setStyleSheet(
            """
            QLabel:not(.log-widget),
            QPushButton:not(.log-widget),
            QRadioButton, QCheckBox,
            QGroupBox:not(.log-group),
            QComboBox, QLineEdit {
                font-size: 10pt;
            }
        """
        )

        layout = QVBoxLayout(self)

        # File selection group
        file_group = QGroupBox(f"{self.device_type} Firmware File")
        file_layout = QHBoxLayout(file_group)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText(f"Select {self.device_type} firmware file")
        file_layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)

        layout.addWidget(file_group)

        # Port selection
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Serial Port:"))

        self.port_combo = QComboBox()
        port_layout.addWidget(self.port_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(refresh_btn)

        layout.addLayout(port_layout)

        # Full Erase option
        self.full_erase_checkbox = QCheckBox("Full Erase before Upload")
        self.full_erase_checkbox.setToolTip("Erase entire flash memory before uploading firmware")
        layout.addWidget(self.full_erase_checkbox)

        # STM32-specific options
        if self.device_type == "STM32":
            # Automatic Mode option
            self.auto_mode_checkbox = QCheckBox("🔄 Automatic Mode (Auto-detect & Upload)")
            self.auto_mode_checkbox.setToolTip(
                "Automatic mode: Waits for MCU connection and automatically uploads.\n\n"
                "Perfect for production workflow:\n"
                "1. Click 'Upload STM32' button\n"
                "2. Connect SWD cable to MCU\n"
                "3. Power on MCU\n"
                "4. Upload starts automatically!\n"
                "5. Replace MCU and repeat\n\n"
                "No manual button clicking needed between MCUs."
            )
            self.auto_mode_checkbox.setStyleSheet(
                "QCheckBox { font-weight: bold; color: #ff6b00; font-size: 11pt; }"
            )
            layout.addWidget(self.auto_mode_checkbox)

            # Advanced Connection Settings
            self.init_stm32_advanced_settings(layout)

        # Upload controls
        upload_layout = QHBoxLayout()

        self.upload_btn = QPushButton(f"Upload {self.device_type}")
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

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel(f"{self.device_type}: Ready")
        layout.addWidget(self.status_label)

        # Device log section (moved below upload buttons)
        self.log_group = QGroupBox(f"{self.device_type} Log")
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
        self.clear_log_btn = QPushButton(f"Clear {self.device_type} Log")
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

        self.save_log_btn = QPushButton(f"Save {self.device_type} Log")
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

        layout.addWidget(self.log_group)

        layout.addStretch()

        # Initialize ports
        self.refresh_ports()

    def browse_file(self):
        """Select firmware file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {self.device_type} Firmware File",
            "",
            f"{self.file_filter};;All Files (*)",
        )
        if file_path:
            self.file_path_edit.setText(file_path)
            # Auto-save settings when file is selected
            self.save_settings()
            if self.settings_manager:
                self.settings_manager.save_settings()

    def refresh_ports(self):
        """Refresh serial port list."""
        current_port = self.port_combo.currentText()
        self.port_combo.clear()

        # Add SWD option for STM32
        if self.device_type == "STM32":
            self.port_combo.addItem("SWD", "SWD")

        ports = SerialPortManager.get_available_ports()
        for port in ports:
            display_text = SerialPortManager.format_port_display(port)
            self.port_combo.addItem(display_text, port["device"])

        # Set default selection
        if self.device_type == "STM32" and not current_port:
            self.port_combo.setCurrentIndex(0)  # Select SWD by default
        elif current_port:
            index = self.port_combo.findData(current_port)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)

    def get_file_path(self) -> str:
        """Return selected file path."""
        return self.file_path_edit.text()

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
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.set_upload_enabled(False)

    def finish_progress(self, success: bool):
        """Finish progress display."""
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1 if success else 0)
        self.set_upload_enabled(True)

    def update_status(self, message: str):
        """Update status message."""
        self.status_label.setText(f"{self.device_type}: {message}")

    def load_settings(self):
        """Load settings for this device type."""
        if not self.settings_manager:
            return

        if self.device_type == "STM32":
            # Load STM32 settings
            last_file = self.settings_manager.get_stm32_last_firmware()
            if last_file and self.settings_manager.validate_file_exists(last_file):
                self.file_path_edit.setText(last_file)

            last_port = self.settings_manager.get_stm32_last_port()
            if last_port:
                index = self.port_combo.findData(last_port)
                if index >= 0:
                    self.port_combo.setCurrentIndex(index)

            # Load full erase setting
            full_erase = self.settings_manager.get_stm32_full_erase()
            self.full_erase_checkbox.setChecked(full_erase)

            # Load STM32 advanced settings
            self.load_stm32_advanced_settings()

    def save_settings(self):
        """Save current settings for this device type."""
        if not self.settings_manager:
            return

        if self.device_type == "STM32":
            # Save STM32 settings
            current_file = self.get_file_path()
            if current_file:
                self.settings_manager.set_stm32_last_firmware(current_file)

            current_port = self.get_selected_port()
            if current_port:
                self.settings_manager.set_stm32_last_port(current_port)

            # Save full erase setting
            self.settings_manager.set_stm32_full_erase(self.is_full_erase_enabled())

            # Save STM32 advanced settings
            self.save_stm32_advanced_settings()

    def init_stm32_advanced_settings(self, layout):
        """Initialize STM32-specific advanced connection settings."""
        advanced_group = QGroupBox("Advanced Connection Settings")
        advanced_layout = QVBoxLayout(advanced_group)

        # Connection Mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Connection Mode:"))

        self.connection_mode_group = QButtonGroup(self)

        self.hotplug_radio = QRadioButton("HOTPLUG")
        self.hotplug_radio.setChecked(True)  # Default
        self.hotplug_radio.toggled.connect(self.on_settings_changed)
        self.connection_mode_group.addButton(self.hotplug_radio, 0)
        mode_layout.addWidget(self.hotplug_radio)

        self.ur_radio = QRadioButton("Under Reset")
        self.ur_radio.toggled.connect(self.on_settings_changed)
        self.connection_mode_group.addButton(self.ur_radio, 1)
        mode_layout.addWidget(self.ur_radio)

        self.normal_radio = QRadioButton("Normal")
        self.normal_radio.toggled.connect(self.on_settings_changed)
        self.connection_mode_group.addButton(self.normal_radio, 2)
        mode_layout.addWidget(self.normal_radio)

        mode_layout.addStretch()
        advanced_layout.addLayout(mode_layout)

        # Hardware Reset checkbox
        self.hardware_reset_checkbox = QCheckBox("Hardware Reset")
        self.hardware_reset_checkbox.setToolTip("Enable hardware reset during connection")
        self.hardware_reset_checkbox.toggled.connect(self.on_settings_changed)
        advanced_layout.addWidget(self.hardware_reset_checkbox)

        # Connection Speed and Retry Attempts
        speed_retry_layout = QHBoxLayout()

        # Connection Speed
        speed_retry_layout.addWidget(QLabel("Speed:"))
        self.speed_combo = QComboBox()
        self.speed_combo.addItems(["1000 kHz", "4000 kHz", "8000 kHz"])
        self.speed_combo.setCurrentText("4000 kHz")  # Default
        self.speed_combo.currentTextChanged.connect(self.on_settings_changed)
        speed_retry_layout.addWidget(self.speed_combo)

        speed_retry_layout.addWidget(QLabel("Retry:"))
        self.retry_combo = QComboBox()
        self.retry_combo.addItems(["1", "3", "5", "10"])
        self.retry_combo.setCurrentText("3")  # Default
        self.retry_combo.currentTextChanged.connect(self.on_settings_changed)
        speed_retry_layout.addWidget(self.retry_combo)

        speed_retry_layout.addStretch()
        advanced_layout.addLayout(speed_retry_layout)

        layout.addWidget(advanced_group)

    def on_settings_changed(self):
        """Handle settings change for auto-save."""
        # Auto-save STM32 settings when changed
        if self.device_type == "STM32" and self.settings_manager:
            self.save_stm32_advanced_settings()

    def save_stm32_advanced_settings(self):
        """Save STM32 advanced connection settings."""
        if not self.settings_manager:
            return

        # Save connection mode
        if hasattr(self, "hotplug_radio") and self.hotplug_radio.isChecked():
            self.settings_manager.set_stm32_connection_mode("HOTPLUG")
        elif hasattr(self, "ur_radio") and self.ur_radio.isChecked():
            self.settings_manager.set_stm32_connection_mode("UR")
        elif hasattr(self, "normal_radio") and self.normal_radio.isChecked():
            self.settings_manager.set_stm32_connection_mode("Normal")

        # Save hardware reset
        if hasattr(self, "hardware_reset_checkbox"):
            self.settings_manager.set_stm32_hardware_reset(self.hardware_reset_checkbox.isChecked())

        # Save connection speed
        if hasattr(self, "speed_combo"):
            speed_text = self.speed_combo.currentText()
            speed = int(speed_text.split()[0])  # Extract number from "4000 kHz"
            self.settings_manager.set_stm32_connection_speed(speed)

        # Save retry attempts
        if hasattr(self, "retry_combo"):
            retry = int(self.retry_combo.currentText())
            self.settings_manager.set_stm32_retry_attempts(retry)

    def load_stm32_advanced_settings(self):
        """Load STM32 advanced connection settings."""
        if not self.settings_manager or self.device_type != "STM32":
            return

        # Load connection mode
        mode = self.settings_manager.get_stm32_connection_mode()
        if hasattr(self, "hotplug_radio"):
            if mode == "HOTPLUG":
                self.hotplug_radio.setChecked(True)
            elif mode == "UR":
                self.ur_radio.setChecked(True)
            elif mode == "Normal":
                self.normal_radio.setChecked(True)

        # Load hardware reset
        if hasattr(self, "hardware_reset_checkbox"):
            hardware_reset = self.settings_manager.get_stm32_hardware_reset()
            self.hardware_reset_checkbox.setChecked(hardware_reset)

        # Load connection speed
        if hasattr(self, "speed_combo"):
            speed = self.settings_manager.get_stm32_connection_speed()
            speed_text = f"{speed} kHz"
            index = self.speed_combo.findText(speed_text)
            if index >= 0:
                self.speed_combo.setCurrentIndex(index)

        # Load retry attempts
        if hasattr(self, "retry_combo"):
            retry = self.settings_manager.get_stm32_retry_attempts()
            retry_text = str(retry)
            index = self.retry_combo.findText(retry_text)
            if index >= 0:
                self.retry_combo.setCurrentIndex(index)

    def get_stm32_connection_settings(self):
        """Get STM32 connection settings for upload."""
        if self.device_type != "STM32":
            return {}

        settings = {}

        # Connection mode
        if hasattr(self, "hotplug_radio"):
            if self.hotplug_radio.isChecked():
                settings["connection_mode"] = "HOTPLUG"
            elif self.ur_radio.isChecked():
                settings["connection_mode"] = "UR"
            elif self.normal_radio.isChecked():
                settings["connection_mode"] = "Normal"

        # Hardware reset
        if hasattr(self, "hardware_reset_checkbox"):
            settings["hardware_reset"] = self.hardware_reset_checkbox.isChecked()

        # Connection speed
        if hasattr(self, "speed_combo"):
            speed_text = self.speed_combo.currentText()
            settings["connection_speed"] = int(speed_text.split()[0])

        # Retry attempts
        if hasattr(self, "retry_combo"):
            settings["retry_attempts"] = int(self.retry_combo.currentText())

        return settings

    def append_log(self, message: str):
        """Add message to device log."""
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
        """Clear device log."""
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
        """Save device log to file."""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {self.device_type} Log",
            f"{self.device_type.lower()}_log.txt",
            "Text Files (*.txt);;All Files (*)",
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(f"=== {self.device_type} Upload Log ===\n\n")
                    f.write(self.log_text.toPlainText())
                self.append_log(f"Log saved to: {file_path}")
            except Exception as e:
                self.append_log(f"Failed to save log: {str(e)}")


class ESP32Tab(QWidget):
    """ESP32-specific tab with multi-file support."""

    def __init__(self, settings_manager: Optional[SettingsManager] = None):
        """Initialize ESP32 tab."""
        super().__init__()
        self.device_type = "ESP32"
        self.firmware_files: list[tuple[str, str]] = []  # List of (address, filepath) tuples
        self.settings_manager = settings_manager
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

        layout.addWidget(file_group)

        # Port selection
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Serial Port:"))

        self.port_combo = QComboBox()
        port_layout.addWidget(self.port_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(refresh_btn)

        layout.addLayout(port_layout)

        # Upload method selection
        method_group = QGroupBox("Upload Method")
        method_layout = QVBoxLayout(method_group)

        self.upload_method_group = QButtonGroup()

        self.auto_method_radio = QRadioButton("Auto (ESP32 Prog Module)")
        self.auto_method_radio.setChecked(True)
        self.auto_method_radio.setToolTip(
            "Use automatic reset/boot control (standard ESP32 development boards)"
        )
        method_layout.addWidget(self.auto_method_radio)
        self.upload_method_group.addButton(self.auto_method_radio, 0)

        self.manual_method_radio = QRadioButton("Manual CTS/RTS Control (TTL-RS232)")
        self.manual_method_radio.setToolTip(
            "Use DTR/RTS signals for manual boot control (TTL-RS232 modules)"
        )
        method_layout.addWidget(self.manual_method_radio)
        self.upload_method_group.addButton(self.manual_method_radio, 1)

        # Manual control options (initially hidden)
        self.manual_control_widget = QWidget()
        manual_control_layout = QVBoxLayout(self.manual_control_widget)
        manual_control_layout.setContentsMargins(20, 5, 5, 5)  # Indent

        info_label = QLabel("TTL-RS232 Connection:")
        info_label.setStyleSheet("color: #666; font-size: 10px;")
        manual_control_layout.addWidget(info_label)

        connection_info = QLabel("DTR → GPIO0, RTS → EN/RST")
        connection_info.setStyleSheet("color: #666; font-size: 10px; font-family: monospace;")
        manual_control_layout.addWidget(connection_info)

        # Test button for manual control
        test_layout = QHBoxLayout()
        self.test_control_btn = QPushButton("Test DTR/RTS Control")
        self.test_control_btn.clicked.connect(self.test_manual_control)
        test_layout.addWidget(self.test_control_btn)
        test_layout.addStretch()
        manual_control_layout.addLayout(test_layout)

        method_layout.addWidget(self.manual_control_widget)
        self.manual_control_widget.setVisible(False)

        # Connect radio button changes
        self.manual_method_radio.toggled.connect(self.on_upload_method_changed)

        layout.addWidget(method_group)

        # Full Erase option
        self.full_erase_checkbox = QCheckBox("Full Erase before Upload")
        self.full_erase_checkbox.setToolTip("Erase entire flash memory before uploading firmware")
        layout.addWidget(self.full_erase_checkbox)

        # Advanced settings group
        advanced_group = QGroupBox("Advanced Settings")
        advanced_layout = QVBoxLayout(advanced_group)

        # Baud rate selection
        baud_layout = QHBoxLayout()
        baud_layout.addWidget(QLabel("Baud Rate:"))

        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["115200", "230400", "460800", "921600"])
        self.baud_combo.setCurrentText("921600")
        self.baud_combo.currentTextChanged.connect(self.on_settings_changed)
        baud_layout.addWidget(self.baud_combo)
        baud_layout.addStretch()
        advanced_layout.addLayout(baud_layout)

        # Connection options
        connection_label = QLabel("Connection Options:")
        connection_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        advanced_layout.addWidget(connection_label)

        self.before_reset_checkbox = QCheckBox("Reset before connection (--before default-reset)")
        self.before_reset_checkbox.setChecked(True)
        self.before_reset_checkbox.toggled.connect(self.on_settings_changed)
        advanced_layout.addWidget(self.before_reset_checkbox)

        self.after_reset_checkbox = QCheckBox("Reset after upload (--after hard-reset)")
        self.after_reset_checkbox.setChecked(True)
        self.after_reset_checkbox.toggled.connect(self.on_settings_changed)
        advanced_layout.addWidget(self.after_reset_checkbox)

        self.no_sync_checkbox = QCheckBox("Use no-sync mode (--before no-reset-no-sync)")
        self.no_sync_checkbox.setChecked(False)
        self.no_sync_checkbox.toggled.connect(self.on_no_sync_changed)
        self.no_sync_checkbox.toggled.connect(self.on_settings_changed)
        advanced_layout.addWidget(self.no_sync_checkbox)

        # Connect attempts
        attempts_layout = QHBoxLayout()
        attempts_layout.addWidget(QLabel("Connection Attempts:"))

        self.connect_attempts_combo = QComboBox()
        self.connect_attempts_combo.addItems(["1", "3", "5", "10"])
        self.connect_attempts_combo.setCurrentText("1")
        self.connect_attempts_combo.currentTextChanged.connect(self.on_settings_changed)
        attempts_layout.addWidget(self.connect_attempts_combo)
        attempts_layout.addStretch()
        advanced_layout.addLayout(attempts_layout)

        layout.addWidget(advanced_group)

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
                box-shadow: 0px 2px 4px rgba(0,0,0,0.3);
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

        layout.addWidget(self.log_group)

        layout.addStretch()

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
        self.progress_bar.setRange(0, 0)
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

        # Load upload method setting
        upload_method = self.settings_manager.get_esp32_upload_method()
        if upload_method == "manual":
            self.manual_method_radio.setChecked(True)
        else:
            self.auto_method_radio.setChecked(True)
        self.on_upload_method_changed(self.manual_method_radio.isChecked())

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

        # Save upload method setting
        self.settings_manager.set_esp32_upload_method(self.get_upload_method())

        # Save advanced settings
        self.settings_manager.set_esp32_baud_rate(int(self.baud_combo.currentText()))
        self.settings_manager.set_esp32_before_reset(self.before_reset_checkbox.isChecked())
        self.settings_manager.set_esp32_after_reset(self.after_reset_checkbox.isChecked())
        self.settings_manager.set_esp32_no_sync(self.no_sync_checkbox.isChecked())
        self.settings_manager.set_esp32_connect_attempts(
            int(self.connect_attempts_combo.currentText())
        )

    def get_upload_method(self) -> str:
        """Get selected upload method.

        Returns:
            'auto' or 'manual'
        """
        return "manual" if self.manual_method_radio.isChecked() else "auto"

    def on_upload_method_changed(self, _checked: bool):
        """Handle upload method radio button change."""
        self.manual_control_widget.setVisible(self.manual_method_radio.isChecked())

    def test_manual_control(self):
        """Test manual DTR/RTS control."""

        port = self.get_selected_port()
        if not port:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Warning")
            msg.setText("Please select a serial port first")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()
            return

        def show_result(title: str, message: str, success: bool):
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Information if success else QMessageBox.Icon.Warning)
            msg.setWindowTitle(title)
            msg.setText(message)
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.exec()

        try:
            controller = SerialBootController(port)

            # Test connection
            if controller.test_connection():
                show_result(
                    "Test Successful",
                    f"DTR/RTS control signals tested successfully on {port}\n\n"
                    + controller.get_signal_mapping_info(),
                    True,
                )
            else:
                show_result(
                    "Test Failed",
                    f"Failed to control DTR/RTS signals on {port}\n\n"
                    "Please check:\n"
                    "1. Serial port connection\n"
                    "2. TTL-RS232 module supports DTR/RTS\n"
                    "3. Correct wiring (DTR→GPIO0, RTS→EN)",
                    False,
                )

        except Exception as e:
            show_result("Test Error", f"Error testing control signals: {str(e)}", False)

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

class MainWindow(QMainWindow):
    """Main window class."""

    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.settings_manager = SettingsManager()
        self.stm32_uploader = STM32Uploader()
        self.esp32_uploader = ESP32Uploader()
        self.upload_threads = {}
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize UI."""
        self.setWindowTitle("WF Firmware Uploader")
        self.setMinimumSize(900, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Tab widget
        self.tab_widget = QTabWidget()
        # Apply 12pt font to tab names
        self.tab_widget.setStyleSheet(
            """
            QTabWidget::tab-bar {
                font-size: 12pt;
            }
            QTabBar::tab {
                font-size: 12pt;
                padding: 8px 16px;
            }
        """
        )

        # STM32 tab
        self.stm32_tab = DeviceTab("STM32", "Binary Files (*.bin *.hex)", self.settings_manager)
        # Apply 12pt font only to STM32 tab
        self.stm32_tab.setStyleSheet(
            """
            QLabel, QPushButton, QRadioButton, QCheckBox, QGroupBox, QComboBox, QLineEdit {
                font-size: 12pt;
            }
        """
        )
        self.stm32_tab.upload_btn.clicked.connect(lambda: self.start_upload("STM32"))
        self.stm32_tab.erase_btn.clicked.connect(lambda: self.erase_flash("STM32"))
        self.tab_widget.addTab(self.stm32_tab, "STM32")

        # ESP32 tab
        self.esp32_tab = ESP32Tab(self.settings_manager)
        self.esp32_tab.upload_btn.clicked.connect(lambda: self.start_upload("ESP32"))
        self.esp32_tab.erase_btn.clicked.connect(lambda: self.erase_flash("ESP32"))
        self.tab_widget.addTab(self.esp32_tab, "ESP32")

        # Connect tab change
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        layout.addWidget(self.tab_widget)

    def start_upload(self, device_type: str):
        """Start upload process."""
        kwargs: dict[str, Any] = {}

        if device_type == "STM32":
            tab = self.stm32_tab
            uploader: Union[STM32Uploader, ESP32Uploader] = self.stm32_uploader
            # Clear STM32 log before starting upload
            self.stm32_tab.clear_log()

            file_path = tab.get_file_path()
            if not file_path:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Warning")
                msg.setText("Please select a firmware file")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
                msg.setModal(True)
                msg.exec()
                return

            # Get STM32 connection settings
            stm32_connection_settings = tab.get_stm32_connection_settings()

            # Check if automatic mode is enabled
            auto_mode = False
            if hasattr(tab, 'auto_mode_checkbox'):
                auto_mode = tab.auto_mode_checkbox.isChecked()

            kwargs.update(
                {
                    "firmware_path": file_path,
                    "port": tab.get_selected_port(),
                    "auto_mode": auto_mode,
                    **stm32_connection_settings,
                }
            )

        else:  # ESP32
            esp32_tab = self.esp32_tab
            uploader = self.esp32_uploader
            # Clear ESP32 log before starting upload
            self.esp32_tab.clear_log()

            firmware_files = esp32_tab.get_firmware_files()
            if not firmware_files:
                msg = QMessageBox(self)
                msg.setIcon(QMessageBox.Icon.Warning)
                msg.setWindowTitle("Warning")
                msg.setText("Please add at least one firmware file")
                msg.setStandardButtons(QMessageBox.StandardButton.Ok)
                msg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
                msg.setModal(True)
                msg.exec()
                return

            # Get connection settings
            connection_settings = esp32_tab.get_connection_settings()

            kwargs.update(
                {
                    "firmware_files": firmware_files,
                    "port": esp32_tab.get_selected_port(),
                    "upload_method": esp32_tab.get_upload_method(),
                    **connection_settings,
                }
            )

        if device_type == "ESP32":
            port = esp32_tab.get_selected_port()
        else:
            port = tab.get_selected_port()
        if not port:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Warning")
            msg.setText("Please select a serial port")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            msg.setModal(True)
            msg.exec()
            return

        # Check if full erase is requested
        current_tab = esp32_tab if device_type == "ESP32" else tab
        full_erase = current_tab.is_full_erase_enabled()

        # Start upload in thread
        thread = UploadWorkerThread(device_type, uploader, full_erase=full_erase, **kwargs)
        thread.progress_update.connect(self.on_progress_update)
        thread.upload_finished.connect(self.on_upload_finished)

        self.upload_threads[device_type] = thread
        current_tab.start_progress()

        if full_erase:
            current_tab.update_status("Erasing and uploading...")
        else:
            current_tab.update_status("Uploading...")

        thread.start()

    def load_settings(self):
        """Load settings from settings manager."""
        # Load window geometry
        x, y, width, height = self.settings_manager.get_window_geometry()
        self.setGeometry(x, y, width, height)

        # Load settings for each tab
        self.stm32_tab.load_settings()
        self.esp32_tab.load_settings()

    def save_settings(self):
        """Save settings to settings manager."""
        # Save window geometry
        geometry = self.geometry()
        self.settings_manager.set_window_geometry(
            geometry.x(), geometry.y(), geometry.width(), geometry.height()
        )

        # Save settings for each tab
        self.stm32_tab.save_settings()
        self.esp32_tab.save_settings()

        # Save to file
        self.settings_manager.save_settings()

    def append_log(self, message: str, device_type: str = ""):
        """Add message to appropriate device log."""
        if device_type == "STM32":
            self.stm32_tab.append_log(message)
        elif device_type == "ESP32":
            self.esp32_tab.append_log(message)
        else:
            # Default behavior for backward compatibility
            # Try to determine device type from current tab or message content
            current_widget = self.tab_widget.currentWidget()
            if current_widget == self.stm32_tab:
                self.stm32_tab.append_log(message)
            elif current_widget == self.esp32_tab:
                self.esp32_tab.append_log(message)

    def on_progress_update(self, device_type: str, message: str):
        """Handle upload progress updates."""
        # Handle special status messages
        if message.startswith("STATUS:"):
            if device_type == "ESP32" and message == "STATUS:PUSH_RESET":
                # Set ESP32 status with only "PUSH RESET !!!" in red
                status_html = (
                    'ESP32: <span style="color: red; font-weight: bold;">' "PUSH RESET !!!</span>"
                )
                self.esp32_tab.status_label.setText(status_html)
                return  # Don't add this to log
            if device_type == "ESP32" and message == "STATUS:CLEAR":
                # Restore ESP32 status to normal
                self.esp32_tab.status_label.setText("ESP32: Ready")
                return  # Don't add this to log

        self.append_log(message, device_type)

    def on_upload_finished(
        self, device_type: str, success: bool, corrected_files: list = None, was_fixed: bool = False
    ):
        """Handle upload completion."""
        # Stop progress bar and re-enable buttons
        if device_type == "STM32":
            self.stm32_tab.finish_progress(success)
        elif device_type == "ESP32":
            self.esp32_tab.finish_progress(success)

        if success:
            self.append_log("Upload completed successfully!", device_type)

            # If ESP32 addresses were auto-fixed, update GUI and save
            if device_type == "ESP32" and was_fixed and corrected_files:
                self.append_log("✓ GUI updated with corrected addresses", device_type)
                self.esp32_tab.firmware_files = corrected_files
                self.esp32_tab.update_file_list()

            # Set PASS background color (dark green)
            if device_type == "STM32":
                self.stm32_tab.set_log_background_color("#1b4332")
            elif device_type == "ESP32":
                self.esp32_tab.set_log_background_color("#1b4332")
            # Save settings on successful upload
            if device_type == "STM32":
                self.stm32_tab.save_settings()
            elif device_type == "ESP32":
                self.esp32_tab.save_settings()
            self.settings_manager.save_settings()
        else:
            self.append_log("Upload failed!", device_type)
            # Set FAIL background color (dark red)
            if device_type == "STM32":
                self.stm32_tab.set_log_background_color("#6a040f")
            elif device_type == "ESP32":
                self.esp32_tab.set_log_background_color("#6a040f")

        # Update status
        if device_type == "STM32":
            self.stm32_tab.update_status("Ready")
        elif device_type == "ESP32":
            self.esp32_tab.update_status("Ready")

    def erase_flash(self, device_type: str):
        """Erase flash for the specified device type."""
        if device_type == "STM32":
            tab = self.stm32_tab
            uploader = self.stm32_uploader
            # Clear STM32 log before erasing
            self.stm32_tab.clear_log()
            port = tab.get_selected_port()
        else:  # ESP32
            tab = self.esp32_tab
            uploader = self.esp32_uploader
            # Clear ESP32 log before erasing
            self.esp32_tab.clear_log()
            port = tab.get_selected_port()

        if not port:
            msg = QMessageBox(self)
            msg.setIcon(QMessageBox.Icon.Warning)
            msg.setWindowTitle("Warning")
            msg.setText("Please select a serial port")
            msg.setStandardButtons(QMessageBox.StandardButton.Ok)
            msg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
            msg.setModal(True)
            msg.exec()
            return

        # Create erase worker thread (erase only, no upload)
        kwargs = {"port": port}
        thread = UploadWorkerThread(device_type, uploader, erase_only=True, **kwargs)
        thread.progress_update.connect(self.on_progress_update)
        thread.upload_finished.connect(self.on_erase_finished)

        self.upload_threads[device_type] = thread
        tab.start_progress()
        tab.update_status("Erasing flash...")

        thread.start()

    def on_erase_finished(
        self, device_type: str, success: bool, corrected_files: list = None, was_fixed: bool = False
    ):
        """Handle erase completion."""
        # Note: corrected_files and was_fixed are not used for erase operations
        # Stop progress bar and re-enable buttons
        if device_type == "STM32":
            self.stm32_tab.finish_progress(success)
        elif device_type == "ESP32":
            self.esp32_tab.finish_progress(success)

        if success:
            self.append_log("Flash erase completed successfully!", device_type)
            # Set PASS background color (dark green)
            if device_type == "STM32":
                self.stm32_tab.set_log_background_color("#1b4332")
            elif device_type == "ESP32":
                self.esp32_tab.set_log_background_color("#1b4332")
        else:
            self.append_log("Flash erase failed!", device_type)
            # Set FAIL background color (dark red)
            if device_type == "STM32":
                self.stm32_tab.set_log_background_color("#6a040f")
            elif device_type == "ESP32":
                self.esp32_tab.set_log_background_color("#6a040f")

        # Update status
        if device_type == "STM32":
            self.stm32_tab.update_status("Ready")
        elif device_type == "ESP32":
            self.esp32_tab.update_status("Ready")

    def on_tab_changed(self, _index: int):
        """Handle tab change event."""
        # Update tab summary when switching

    def closeEvent(self, event):
        """Handle application close event."""
        self.save_settings()
        super().closeEvent(event)
