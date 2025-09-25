"""Main window module."""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union, cast

from PySide6.QtCore import Qt, QThread, QTimer, Signal
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
    upload_finished = Signal(str, bool)  # device_type, success

    def __init__(self, device_type, uploader, full_erase=False, **kwargs):
        """Initialize worker thread."""
        super().__init__()
        self.device_type = device_type
        self.uploader = uploader
        self.full_erase = full_erase
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

            # Step 1: Full erase if requested
            if self.full_erase:
                progress_callback("Starting full flash erase...")
                port = self.kwargs.get("port", "")
                erase_success = self.uploader.erase_flash(port, progress_callback=progress_callback)
                if not erase_success:
                    progress_callback("Flash erase failed")
                    self.upload_finished.emit(self.device_type, False)
                    return
                progress_callback("Flash erase completed successfully")

            # Step 2: Upload firmware
            progress_callback("Starting firmware upload...")
            success = self.uploader.upload_firmware(
                progress_callback=progress_callback, **self.kwargs
            )
            self.upload_finished.emit(self.device_type, success)

        except Exception as e:
            try:
                error_msg = f"Upload error: {str(e)}"
                self.progress_update.emit(self.device_type, error_msg)
                self.upload_finished.emit(self.device_type, False)
            except Exception:
                # If even error reporting fails, just emit failure
                try:
                    self.upload_finished.emit(self.device_type, False)
                except Exception:
                    # Last resort - do nothing if everything fails
                    pass


class DualUploadWorkerThread(QThread):
    """Worker thread for dual upload tasks."""

    progress_update = Signal(str, str)  # device_type, message
    upload_finished = Signal(str, bool)  # device_type, success
    dual_finished = Signal(bool)  # overall success

    def __init__(self, stm32_uploader, esp32_uploader, stm32_kwargs, esp32_kwargs):
        """Initialize dual upload worker thread."""
        super().__init__()
        self.stm32_uploader = stm32_uploader
        self.esp32_uploader = esp32_uploader
        self.stm32_kwargs = stm32_kwargs
        self.esp32_kwargs = esp32_kwargs
        self.stm32_success = False
        self.esp32_success = False
        self.completed_count = 0

    def run(self):
        """Execute dual upload task."""

        def stm32_progress_callback(message):
            try:
                self.progress_update.emit("STM32", message)
            except Exception:
                pass

        def esp32_progress_callback(message):
            try:
                self.progress_update.emit("ESP32", message)
            except Exception:
                pass

        def on_upload_finished(device_type, success):
            """Handle individual upload completion."""
            self.progress_update.emit("DUAL", f"[DEBUG] {device_type} upload finished: {success}")
            self.completed_count += 1
            if device_type == "STM32":
                self.stm32_success = success
            elif device_type == "ESP32":
                self.esp32_success = success

            self.upload_finished.emit(device_type, success)

            # Check if both uploads are completed
            self.progress_update.emit("DUAL", f"[DEBUG] Completed count: {self.completed_count}/2")
            if self.completed_count >= 2:
                overall_success = self.stm32_success and self.esp32_success
                self.progress_update.emit("DUAL", f"[DEBUG] Both uploads complete. Overall success: {overall_success}")
                self.dual_finished.emit(overall_success)

        try:
            self.progress_update.emit("DUAL", "[DEBUG] Starting dual upload process...")

            # Start STM32 upload in separate thread
            self.progress_update.emit("DUAL", "[DEBUG] Creating STM32 upload thread...")
            self.stm32_thread = UploadWorkerThread(
                "STM32", self.stm32_uploader, **self.stm32_kwargs
            )
            self.stm32_thread.progress_update.connect(
                lambda device, msg: stm32_progress_callback(msg)
            )
            self.stm32_thread.upload_finished.connect(
                lambda device, success: on_upload_finished("STM32", success)
            )

            # Start ESP32 upload in separate thread
            self.progress_update.emit("DUAL", "[DEBUG] Creating ESP32 upload thread...")
            self.esp32_thread = UploadWorkerThread(
                "ESP32", self.esp32_uploader, **self.esp32_kwargs
            )
            self.esp32_thread.progress_update.connect(
                lambda device, msg: esp32_progress_callback(msg)
            )
            self.esp32_thread.upload_finished.connect(
                lambda device, success: on_upload_finished("ESP32", success)
            )

            # Start both uploads
            self.progress_update.emit("DUAL", "[DEBUG] Starting both upload threads...")
            self.stm32_thread.start()
            self.esp32_thread.start()
            self.progress_update.emit("DUAL", "[DEBUG] Both threads started successfully")

            # Note: Removed wait() calls to prevent UI blocking
            # Completion is handled through signals in on_upload_finished()

        except Exception as e:
            # Clean up threads on exception
            self.progress_update.emit("DUAL", f"[DEBUG] Exception in dual upload: {str(e)}")
            if hasattr(self, "stm32_thread"):
                self.stm32_thread.terminate()
                self.progress_update.emit("DUAL", "[DEBUG] STM32 thread terminated")
            if hasattr(self, "esp32_thread"):
                self.esp32_thread.terminate()
                self.progress_update.emit("DUAL", "[DEBUG] ESP32 thread terminated")
            self.progress_update.emit("DUAL", f"Dual upload error: {str(e)}")
            self.dual_finished.emit(False)


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
        # Set 10pt font for all widgets in device tab
        self.setStyleSheet("""
            QLabel, QPushButton, QRadioButton, QCheckBox, QGroupBox, QComboBox, QLineEdit {
                font-size: 10pt;
            }
        """)

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

        # STM32-specific Advanced Connection Settings
        if self.device_type == "STM32":
            self.init_stm32_advanced_settings(layout)

        # Upload controls
        upload_layout = QHBoxLayout()

        self.upload_btn = QPushButton(f"Upload {self.device_type}")
        self.upload_btn.setMinimumHeight(60)
        self.upload_btn.setStyleSheet("""
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
        """)
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
        if hasattr(self, 'hotplug_radio') and self.hotplug_radio.isChecked():
            self.settings_manager.set_stm32_connection_mode("HOTPLUG")
        elif hasattr(self, 'ur_radio') and self.ur_radio.isChecked():
            self.settings_manager.set_stm32_connection_mode("UR")
        elif hasattr(self, 'normal_radio') and self.normal_radio.isChecked():
            self.settings_manager.set_stm32_connection_mode("Normal")

        # Save hardware reset
        if hasattr(self, 'hardware_reset_checkbox'):
            self.settings_manager.set_stm32_hardware_reset(self.hardware_reset_checkbox.isChecked())

        # Save connection speed
        if hasattr(self, 'speed_combo'):
            speed_text = self.speed_combo.currentText()
            speed = int(speed_text.split()[0])  # Extract number from "4000 kHz"
            self.settings_manager.set_stm32_connection_speed(speed)

        # Save retry attempts
        if hasattr(self, 'retry_combo'):
            retry = int(self.retry_combo.currentText())
            self.settings_manager.set_stm32_retry_attempts(retry)

    def load_stm32_advanced_settings(self):
        """Load STM32 advanced connection settings."""
        if not self.settings_manager or self.device_type != "STM32":
            return

        # Load connection mode
        mode = self.settings_manager.get_stm32_connection_mode()
        if hasattr(self, 'hotplug_radio'):
            if mode == "HOTPLUG":
                self.hotplug_radio.setChecked(True)
            elif mode == "UR":
                self.ur_radio.setChecked(True)
            elif mode == "Normal":
                self.normal_radio.setChecked(True)

        # Load hardware reset
        if hasattr(self, 'hardware_reset_checkbox'):
            hardware_reset = self.settings_manager.get_stm32_hardware_reset()
            self.hardware_reset_checkbox.setChecked(hardware_reset)

        # Load connection speed
        if hasattr(self, 'speed_combo'):
            speed = self.settings_manager.get_stm32_connection_speed()
            speed_text = f"{speed} kHz"
            index = self.speed_combo.findText(speed_text)
            if index >= 0:
                self.speed_combo.setCurrentIndex(index)

        # Load retry attempts
        if hasattr(self, 'retry_combo'):
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
        if hasattr(self, 'hotplug_radio'):
            if self.hotplug_radio.isChecked():
                settings["connection_mode"] = "HOTPLUG"
            elif self.ur_radio.isChecked():
                settings["connection_mode"] = "UR"
            elif self.normal_radio.isChecked():
                settings["connection_mode"] = "Normal"

        # Hardware reset
        if hasattr(self, 'hardware_reset_checkbox'):
            settings["hardware_reset"] = self.hardware_reset_checkbox.isChecked()

        # Connection speed
        if hasattr(self, 'speed_combo'):
            speed_text = self.speed_combo.currentText()
            settings["connection_speed"] = int(speed_text.split()[0])

        # Retry attempts
        if hasattr(self, 'retry_combo'):
            settings["retry_attempts"] = int(self.retry_combo.currentText())

        return settings


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
        self.setStyleSheet("""
            QLabel, QPushButton, QRadioButton, QCheckBox, QGroupBox, QComboBox {
                font-size: 12pt;
            }
        """)

        layout = QVBoxLayout(self)

        # Multi-file selection group
        file_group = QGroupBox("ESP32 Firmware Files")
        file_layout = QVBoxLayout(file_group)

        # File list
        self.file_list = QListWidget()
        self.file_list.setMaximumHeight(150)
        # Increase font size for firmware file list
        self.file_list.setStyleSheet("QListWidget { font-size: 11pt; }")
        file_layout.addWidget(QLabel("Files to upload:"))
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
        self.upload_btn.setStyleSheet("""
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
        """)
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

        self.reset_guidance_label.setStyleSheet("""
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
        """)
        self.reset_guidance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.reset_guidance_label)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel("ESP32: Ready")
        layout.addWidget(self.status_label)

        layout.addStretch()

        # Initialize ports
        self.refresh_ports()

    def add_firmware_file(self):
        """Add a firmware file with address."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select ESP32 Firmware File", "", "Binary Files (*.bin);;All Files (*)"
        )
        if file_path:
            # Simple address dialog - you could make this more sophisticated
            address = self.get_address_for_file(file_path)
            if address:
                self.firmware_files.append((address, file_path))
                self.update_file_list()
                # Auto-save settings when file is added
                self.save_settings()
                if self.settings_manager:
                    self.settings_manager.save_settings()

    def get_address_for_file(self, file_path: str) -> str:
        """Get flash address for file (simple heuristic)."""
        filename = Path(file_path).name.lower()

        # Common ESP32 file patterns
        if "bootloader" in filename:
            return "0x1000"
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
        """Quick setup for full ESP32 build directory."""
        dir_path = QFileDialog.getExistingDirectory(self, "Select ESP32 Build Directory")
        if dir_path:
            build_path = Path(dir_path)
            self.firmware_files = []

            # Look for common ESP32 build files
            files_to_check = [
                ("0x1000", "bootloader.bin"),
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


class DualUploadTab(QWidget):
    """Dual upload tab for uploading both STM32 and ESP32 simultaneously."""

    def __init__(self, stm32_tab, esp32_tab, settings_manager: Optional[SettingsManager] = None):
        """Initialize dual upload tab."""
        super().__init__()
        self.stm32_tab = stm32_tab
        self.esp32_tab = esp32_tab
        self.settings_manager = settings_manager
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        # Set 12pt font for all widgets in dual upload tab
        self.setStyleSheet("""
            QLabel, QPushButton, QRadioButton, QCheckBox, QGroupBox, QComboBox, QProgressBar {
                font-size: 12pt;
            }
        """)

        layout = QVBoxLayout(self)

        # Settings summary section
        summary_group = QGroupBox("Current Settings")
        summary_layout = QVBoxLayout(summary_group)

        # STM32 settings summary
        stm32_summary_layout = QHBoxLayout()
        stm32_summary_layout.addWidget(QLabel("STM32:"))
        self.stm32_summary_label = QLabel("No firmware selected")
        self.stm32_summary_label.setStyleSheet("color: gray;")
        stm32_summary_layout.addWidget(self.stm32_summary_label)
        stm32_summary_layout.addStretch()

        stm32_config_btn = QPushButton("Configure in STM32 Tab")
        stm32_config_btn.clicked.connect(lambda: self.switch_to_tab("STM32"))
        stm32_summary_layout.addWidget(stm32_config_btn)
        summary_layout.addLayout(stm32_summary_layout)

        # ESP32 settings summary
        esp32_summary_layout = QHBoxLayout()
        esp32_summary_layout.addWidget(QLabel("ESP32:"))
        self.esp32_summary_label = QLabel("No firmware files added")
        self.esp32_summary_label.setStyleSheet("color: gray;")
        esp32_summary_layout.addWidget(self.esp32_summary_label)
        esp32_summary_layout.addStretch()

        esp32_config_btn = QPushButton("Configure in ESP32 Tab")
        esp32_config_btn.clicked.connect(lambda: self.switch_to_tab("ESP32"))
        esp32_summary_layout.addWidget(esp32_config_btn)
        summary_layout.addLayout(esp32_summary_layout)

        layout.addWidget(summary_group)

        # Upload controls
        controls_group = QGroupBox("Upload Controls")
        controls_layout = QVBoxLayout(controls_group)

        # Main upload button
        self.upload_both_btn = QPushButton("🚀 Upload Both Devices")
        self.upload_both_btn.setMinimumHeight(100)
        self.upload_both_btn.setStyleSheet(
            """
            QPushButton {
                font-size: 16px;
                font-weight: bold;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 8px;
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
        controls_layout.addWidget(self.upload_both_btn)

        # Individual upload buttons
        individual_layout = QHBoxLayout()
        self.upload_stm32_btn = QPushButton("Upload STM32 Only")
        self.upload_stm32_btn.setMinimumHeight(60)
        self.upload_stm32_btn.setStyleSheet("""
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
        """)

        self.upload_esp32_btn = QPushButton("Upload ESP32 Only")
        self.upload_esp32_btn.setMinimumHeight(60)
        self.upload_esp32_btn.setStyleSheet("""
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
        """)
        individual_layout.addWidget(self.upload_stm32_btn)
        individual_layout.addWidget(self.upload_esp32_btn)
        controls_layout.addLayout(individual_layout)

        # Cancel button
        self.cancel_btn = QPushButton("Cancel Upload")
        self.cancel_btn.setVisible(False)
        self.cancel_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
        """
        )
        controls_layout.addWidget(self.cancel_btn)

        layout.addWidget(controls_group)

        # Progress section
        progress_group = QGroupBox("Upload Progress")
        progress_layout = QVBoxLayout(progress_group)

        # STM32 progress
        stm32_progress_layout = QVBoxLayout()
        stm32_progress_layout.addWidget(QLabel("STM32 Progress:"))
        self.stm32_progress_bar = QProgressBar()
        self.stm32_progress_bar.setVisible(False)
        stm32_progress_layout.addWidget(self.stm32_progress_bar)
        self.stm32_status_label = QLabel("STM32: Ready")
        stm32_progress_layout.addWidget(self.stm32_status_label)
        progress_layout.addLayout(stm32_progress_layout)

        # ESP32 progress
        esp32_progress_layout = QVBoxLayout()
        esp32_progress_layout.addWidget(QLabel("ESP32 Progress:"))
        self.esp32_progress_bar = QProgressBar()
        self.esp32_progress_bar.setVisible(False)
        esp32_progress_layout.addWidget(self.esp32_progress_bar)
        self.esp32_status_label = QLabel("ESP32: Ready")
        esp32_progress_layout.addWidget(self.esp32_status_label)
        progress_layout.addLayout(esp32_progress_layout)

        # Overall progress
        overall_progress_layout = QVBoxLayout()
        overall_progress_layout.addWidget(QLabel("Overall Progress:"))
        self.overall_progress_bar = QProgressBar()
        self.overall_progress_bar.setVisible(False)
        overall_progress_layout.addWidget(self.overall_progress_bar)
        self.overall_status_label = QLabel("Ready to upload")
        overall_progress_layout.addWidget(self.overall_status_label)
        progress_layout.addLayout(overall_progress_layout)

        layout.addWidget(progress_group)
        layout.addStretch()

        # Update initial summary
        self.update_settings_summary()

    def switch_to_tab(self, tab_name: str):
        """Switch to specified tab for configuration."""
        # This will be connected to MainWindow's tab switching logic
        parent = self.parent()
        while parent and not hasattr(parent, "tab_widget"):
            parent = parent.parent()
        if parent and hasattr(parent, "tab_widget"):
            # Type cast to MainWindow to access specific attributes
            main_window = cast("MainWindow", parent)
            if hasattr(main_window, "stm32_tab") and hasattr(main_window, "esp32_tab"):
                if tab_name == "STM32":
                    main_window.tab_widget.setCurrentWidget(main_window.stm32_tab)
                elif tab_name == "ESP32":
                    main_window.tab_widget.setCurrentWidget(main_window.esp32_tab)

    def update_settings_summary(self):
        """Update the settings summary display."""
        # STM32 summary
        stm32_file = self.stm32_tab.get_file_path()
        stm32_port = self.stm32_tab.get_selected_port()
        stm32_erase = self.stm32_tab.is_full_erase_enabled()

        if stm32_file:
            stm32_filename = Path(stm32_file).name
            erase_text = " (Full Erase)" if stm32_erase else ""
            stm32_text = f"{stm32_filename} → {stm32_port}{erase_text}"
            self.stm32_summary_label.setStyleSheet("color: black;")
        else:
            stm32_text = "No firmware selected"
            self.stm32_summary_label.setStyleSheet("color: gray;")
        self.stm32_summary_label.setText(stm32_text)

        # ESP32 summary
        esp32_files = self.esp32_tab.get_firmware_files()
        esp32_port = self.esp32_tab.get_selected_port()
        esp32_erase = self.esp32_tab.is_full_erase_enabled()

        if esp32_files:
            file_count = len(esp32_files)
            erase_text = " (Full Erase)" if esp32_erase else ""
            esp32_text = f"{file_count} file(s) → {esp32_port}{erase_text}"
            self.esp32_summary_label.setStyleSheet("color: black;")
        else:
            esp32_text = "No firmware files added"
            self.esp32_summary_label.setStyleSheet("color: gray;")
        self.esp32_summary_label.setText(esp32_text)

        # Update button states
        stm32_ready = bool(stm32_file and stm32_port)
        esp32_ready = bool(esp32_files and esp32_port)

        self.upload_stm32_btn.setEnabled(stm32_ready)
        self.upload_esp32_btn.setEnabled(esp32_ready)
        self.upload_both_btn.setEnabled(stm32_ready and esp32_ready)

    def start_progress(self, device_type: str):
        """Start progress display for specified device."""
        if device_type == "STM32":
            self.stm32_progress_bar.setRange(0, 0)
            self.stm32_progress_bar.setVisible(True)
        elif device_type == "ESP32":
            self.esp32_progress_bar.setRange(0, 0)
            self.esp32_progress_bar.setVisible(True)
        elif device_type == "BOTH":
            self.overall_progress_bar.setRange(0, 0)
            self.overall_progress_bar.setVisible(True)

    def finish_progress(self, device_type: str, success: bool):
        """Finish progress display for specified device."""
        if device_type == "STM32":
            self.stm32_progress_bar.setRange(0, 1)
            self.stm32_progress_bar.setValue(1 if success else 0)
        elif device_type == "ESP32":
            self.esp32_progress_bar.setRange(0, 1)
            self.esp32_progress_bar.setValue(1 if success else 0)
        elif device_type == "BOTH":
            self.overall_progress_bar.setRange(0, 1)
            self.overall_progress_bar.setValue(1 if success else 0)

    def update_status(self, device_type: str, message: str):
        """Update status message for specified device."""
        if device_type == "STM32":
            self.stm32_status_label.setText(f"STM32: {message}")
        elif device_type == "ESP32":
            self.esp32_status_label.setText(f"ESP32: {message}")
        elif device_type == "OVERALL":
            self.overall_status_label.setText(message)

    def set_upload_enabled(self, enabled: bool):
        """Set upload button states."""
        self.upload_both_btn.setEnabled(enabled)
        self.upload_stm32_btn.setEnabled(enabled)
        self.upload_esp32_btn.setEnabled(enabled)
        self.cancel_btn.setVisible(not enabled)

    def cancel_upload(self):
        """Cancel ongoing upload."""
        # This will be connected to MainWindow's cancel logic
        parent = self.parent()
        while parent and not hasattr(parent, "cancel_dual_upload"):
            parent = parent.parent()
        if parent and hasattr(parent, "cancel_dual_upload"):
            # Type cast to MainWindow to access cancel_dual_upload method
            main_window = cast("MainWindow", parent)
            main_window.cancel_dual_upload()


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
        self.tab_widget.setStyleSheet("""
            QTabWidget::tab-bar {
                font-size: 12pt;
            }
            QTabBar::tab {
                font-size: 12pt;
                padding: 8px 16px;
            }
        """)

        # STM32 tab
        self.stm32_tab = DeviceTab("STM32", "Binary Files (*.bin *.hex)", self.settings_manager)
        # Apply 12pt font only to STM32 tab
        self.stm32_tab.setStyleSheet("""
            QLabel, QPushButton, QRadioButton, QCheckBox, QGroupBox, QComboBox, QLineEdit {
                font-size: 12pt;
            }
        """)
        self.stm32_tab.upload_btn.clicked.connect(lambda: self.start_upload("STM32"))
        self.stm32_tab.erase_btn.clicked.connect(lambda: self.erase_flash("STM32"))
        self.tab_widget.addTab(self.stm32_tab, "STM32")

        # ESP32 tab
        self.esp32_tab = ESP32Tab(self.settings_manager)
        self.esp32_tab.upload_btn.clicked.connect(lambda: self.start_upload("ESP32"))
        self.esp32_tab.erase_btn.clicked.connect(lambda: self.erase_flash("ESP32"))
        self.tab_widget.addTab(self.esp32_tab, "ESP32")

        # Dual Upload tab
        self.dual_tab = DualUploadTab(self.stm32_tab, self.esp32_tab, self.settings_manager)
        self.dual_tab.upload_both_btn.clicked.connect(self.start_dual_upload)
        self.dual_tab.upload_stm32_btn.clicked.connect(lambda: self.start_upload_from_dual("STM32"))
        self.dual_tab.upload_esp32_btn.clicked.connect(lambda: self.start_upload_from_dual("ESP32"))
        self.dual_tab.cancel_btn.clicked.connect(self.cancel_dual_upload)
        self.tab_widget.addTab(self.dual_tab, "Dual Upload")

        # Connect tab change to update dual tab summary
        self.tab_widget.currentChanged.connect(self.on_tab_changed)

        layout.addWidget(self.tab_widget)

        # Log viewer
        log_group = QGroupBox("Log")
        # Apply 12pt font to log group title
        log_group.setStyleSheet("QGroupBox { font-size: 12pt; }")
        log_layout = QVBoxLayout(log_group)

        log_controls = QHBoxLayout()
        clear_btn = QPushButton("Clear Log")
        clear_btn.setStyleSheet("QPushButton { font-size: 12pt; }")
        clear_btn.clicked.connect(self.clear_log)
        log_controls.addWidget(clear_btn)

        log_controls.addStretch()

        save_btn = QPushButton("Save Log")
        save_btn.setStyleSheet("QPushButton { font-size: 12pt; }")
        save_btn.clicked.connect(self.save_log)
        log_controls.addWidget(save_btn)

        log_layout.addLayout(log_controls)

        self.log_text = QTextEdit()
        self.log_text.setMinimumHeight(100)  # 최소 높이만 설정
        self.log_text.setFont(QFont("Courier", 12))
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

    def start_upload(self, device_type: str):
        """Start upload process."""
        kwargs: dict[str, Any] = {}

        if device_type == "STM32":
            tab = self.stm32_tab
            uploader: Union[STM32Uploader, ESP32Uploader] = self.stm32_uploader

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
            kwargs.update({
                "firmware_path": file_path,
                "port": tab.get_selected_port(),
                **stm32_connection_settings
            })

        else:  # ESP32
            esp32_tab = self.esp32_tab
            uploader = self.esp32_uploader

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

    def start_dual_upload(self):
        """Start dual upload process."""
        # Validate STM32 settings
        stm32_file = self.stm32_tab.get_file_path()
        stm32_port = self.stm32_tab.get_selected_port()
        if not stm32_file or not stm32_port:
            self.show_warning(
                "STM32 Configuration", "Please configure STM32 firmware and port in the STM32 tab"
            )
            return

        # Validate ESP32 settings
        esp32_files = self.esp32_tab.get_firmware_files()
        esp32_port = self.esp32_tab.get_selected_port()
        if not esp32_files or not esp32_port:
            self.show_warning(
                "ESP32 Configuration",
                "Please configure ESP32 firmware files and port in the ESP32 tab",
            )
            return

        # Prepare STM32 kwargs
        stm32_kwargs = {
            "firmware_path": stm32_file,
            "port": stm32_port,
            "full_erase": self.stm32_tab.is_full_erase_enabled(),
        }

        # Prepare ESP32 kwargs
        connection_settings = self.esp32_tab.get_connection_settings()
        esp32_kwargs = {
            "firmware_files": esp32_files,
            "port": esp32_port,
            "full_erase": self.esp32_tab.is_full_erase_enabled(),
            "upload_method": self.esp32_tab.get_upload_method(),
            **connection_settings,
        }

        # Start dual upload thread
        self.dual_upload_thread = DualUploadWorkerThread(
            self.stm32_uploader, self.esp32_uploader, stm32_kwargs, esp32_kwargs
        )
        self.dual_upload_thread.progress_update.connect(self.on_dual_progress_update)
        self.dual_upload_thread.upload_finished.connect(self.on_dual_upload_finished)
        self.dual_upload_thread.dual_finished.connect(self.on_dual_complete)

        # Update UI
        self.dual_tab.start_progress("BOTH")
        self.dual_tab.start_progress("STM32")
        self.dual_tab.start_progress("ESP32")
        self.dual_tab.update_status("STM32", "Starting...")
        self.dual_tab.update_status("ESP32", "Starting...")
        self.dual_tab.update_status("OVERALL", "Uploading both devices...")
        self.dual_tab.set_upload_enabled(False)

        self.dual_upload_thread.start()

    def start_upload_from_dual(self, device_type: str):
        """Start single upload from dual tab."""
        # Update dual tab settings summary first
        self.dual_tab.update_settings_summary()

        # Use existing start_upload logic
        self.start_upload(device_type)

    def on_dual_progress_update(self, device_type: str, message: str):
        """Handle dual upload progress updates."""
        self.dual_tab.update_status(device_type, message)
        self.append_log(message, device_type)

    def on_dual_upload_finished(self, device_type: str, success: bool):
        """Handle individual device upload completion in dual mode."""
        self.dual_tab.finish_progress(device_type, success)

        if success:
            self.dual_tab.update_status(device_type, "Upload completed")
        else:
            self.dual_tab.update_status(device_type, "Upload failed")

    def on_dual_complete(self, overall_success: bool):
        """Handle dual upload completion."""
        self.dual_tab.finish_progress("BOTH", overall_success)
        self.dual_tab.set_upload_enabled(True)

        if overall_success:
            self.dual_tab.update_status("OVERALL", "Both devices uploaded successfully!")
            self.append_log("Dual upload completed successfully", "DUAL")
            # Save settings on successful upload
            self.stm32_tab.save_settings()
            self.esp32_tab.save_settings()
            self.settings_manager.save_settings()
        else:
            self.dual_tab.update_status("OVERALL", "One or more uploads failed")
            self.append_log("Dual upload failed", "DUAL")

    def cancel_dual_upload(self):
        """Cancel ongoing dual upload."""
        if hasattr(self, "dual_upload_thread") and self.dual_upload_thread.isRunning():
            self.dual_upload_thread.terminate()
            self.dual_upload_thread.wait(5000)  # Wait up to 5 seconds for termination

            # Reset UI
            self.dual_tab.finish_progress("STM32", False)
            self.dual_tab.finish_progress("ESP32", False)
            self.dual_tab.finish_progress("BOTH", False)
            self.dual_tab.update_status("STM32", "Upload cancelled")
            self.dual_tab.update_status("ESP32", "Upload cancelled")
            self.dual_tab.update_status("OVERALL", "Upload cancelled")
            self.dual_tab.set_upload_enabled(True)

            self.append_log("Dual upload cancelled by user", "DUAL")

    def show_warning(self, title: str, message: str):
        """Show warning message box."""
        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle(title)
        msg.setText(message)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        msg.setModal(True)
        msg.exec()

    def erase_flash(self, device_type: str):
        """Erase flash memory."""
        if device_type == "STM32":
            tab = self.stm32_tab
            uploader: Union[STM32Uploader, ESP32Uploader] = self.stm32_uploader
            port = tab.get_selected_port()
        else:
            esp32_tab = self.esp32_tab
            uploader = self.esp32_uploader
            port = esp32_tab.get_selected_port()
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

        try:
            if device_type == "STM32":
                tab.update_status("Erasing...")

                # Log detailed STM32 erase start information
                self.append_log("Starting flash erase...", device_type)

                # Get and log STM32 connection settings
                stm32_settings = tab.get_stm32_connection_settings()
                connection_mode = stm32_settings.get("connection_mode", "HOTPLUG")
                hardware_reset = stm32_settings.get("hardware_reset", False)
                connection_speed = stm32_settings.get("connection_speed", 4000)
                retry_attempts = stm32_settings.get("retry_attempts", 3)

                self.append_log(f"Erasing STM32 flash on port {port}...", device_type)
                self.append_log(f"Connection mode: {connection_mode}, Speed: {connection_speed}kHz", device_type)
                self.append_log(f"Hardware reset: {'enabled' if hardware_reset else 'disabled'}", device_type)
                self.append_log(f"Retry attempts: {retry_attempts}", device_type)

                success = uploader.erase_flash(
                    port, progress_callback=lambda msg: self.append_log(msg, device_type)
                )
                if success:
                    tab.update_status("Erase completed")
                    self.append_log("Flash erase completed", device_type)
                else:
                    tab.update_status("Erase failed")
                    self.append_log("Flash erase failed", device_type)
            else:
                esp32_tab.update_status("Erasing...")

                # Log detailed ESP32 erase start information
                self.append_log("Starting flash erase...", device_type)

                # Get and log ESP32 connection settings
                connection_settings = esp32_tab.get_connection_settings()
                baud_rate = connection_settings.get("baud_rate", 921600)
                before_reset = "default-reset" if connection_settings.get("before_reset", True) else "no-reset"
                after_reset = "hard-reset" if connection_settings.get("after_reset", True) else "no-reset"
                connect_attempts = connection_settings.get("connect_attempts", 1)

                self.append_log(f"Erasing ESP32 flash on port {port}...", device_type)
                self.append_log(f"Connection settings: Baud={baud_rate}, Before={before_reset}, After={after_reset}", device_type)
                self.append_log(f"Connection attempts: {connect_attempts}", device_type)
                self.append_log("Note: This may take a while depending on flash size", device_type)

                success = uploader.erase_flash(
                    port,
                    progress_callback=lambda msg: self._handle_esp32_progress(msg, device_type),
                    **connection_settings,
                )
                if success:
                    esp32_tab.update_status("Erase completed")
                    self.append_log("Flash erase completed", device_type)
                else:
                    esp32_tab.update_status("Erase failed")
                    self.append_log("Flash erase failed", device_type)
        except Exception as e:
            if device_type == "STM32":
                tab.update_status("Erase error")
            else:
                esp32_tab.update_status("Erase error")
            self.append_log(f"Erase error: {str(e)}", device_type)

    def _handle_esp32_progress(self, message: str, device_type: str):
        """Handle ESP32 progress updates with smart reset guidance."""
        # Show reset guidance when checking connection
        if "Checking ESP32 connection" in message:
            if device_type == "ESP32":
                # Force hide first, then show to ensure visibility
                self.esp32_tab.hide_reset_guidance()
                self.esp32_tab.show_reset_guidance()

        # Hide reset guidance on successful connection
        elif any(keyword in message for keyword in [
            "Connected to ESP32", "Chip detected", "Detecting chip type", "Chip type:",
            "Stub flasher is already running", "Changed.", "Writing at"
        ]):
            if device_type == "ESP32":
                self.esp32_tab.hide_reset_guidance()

        # Also hide on completion messages
        elif any(keyword in message for keyword in [
            "completed successfully", "Hash of data verified", "Hard resetting"
        ]):
            if device_type == "ESP32":
                self.esp32_tab.hide_reset_guidance()

        # Always log the message
        self.append_log(message, device_type)

    def on_progress_update(self, device_type: str, message: str):
        """Handle progress updates."""
        if device_type == "ESP32":
            self._handle_esp32_progress(message, device_type)
        else:
            self.append_log(message, device_type)

    def on_upload_finished(self, device_type: str, success: bool):
        """Handle upload completion."""
        if device_type == "STM32":
            tab = self.stm32_tab
            tab.finish_progress(success)
        else:
            esp32_tab = self.esp32_tab
            esp32_tab.finish_progress(success)
            # Always hide reset guidance when ESP32 upload finishes
            esp32_tab.hide_reset_guidance()
        if success:
            if device_type == "STM32":
                tab.update_status("Upload completed")
                tab.save_settings()
            else:
                esp32_tab.update_status("Upload completed")
                esp32_tab.save_settings()
            self.append_log("Upload completed successfully", device_type)
            self.settings_manager.save_settings()
        else:
            if device_type == "STM32":
                tab.update_status("Upload failed")
            else:
                esp32_tab.update_status("Upload failed")
            self.append_log("Upload failed", device_type)

        # Clean up thread
        if device_type in self.upload_threads:
            del self.upload_threads[device_type]

    def append_log(self, message: str, device_type: str = ""):
        """Add message to log."""
        # Get current time
        current_time = datetime.now().strftime("%H:%M:%S")

        if device_type:
            formatted_msg = f"[{current_time}] [{device_type}] {message}"
        else:
            formatted_msg = f"[{current_time}] {message}"

        self.log_text.append(formatted_msg)

        # Auto-scroll to bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.log_text.setTextCursor(cursor)
        self.log_text.ensureCursorVisible()

    def clear_log(self):
        """Clear log."""
        self.log_text.clear()

    def save_log(self):
        """Save log to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Log File", "upload_log.txt", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(self.log_text.toPlainText())
                self.append_log(f"Log saved to: {file_path}")
            except Exception as e:
                self.append_log(f"Failed to save log: {str(e)}")

    def load_settings(self):
        """Load application settings."""
        # Load window geometry
        x, y, width, height = self.settings_manager.get_window_geometry()
        self.setGeometry(x, y, width, height)

        # Clean up missing files
        self.settings_manager.cleanup_missing_files()

        # Load settings for each tab
        self.stm32_tab.load_settings()
        self.esp32_tab.load_settings()

    def save_settings(self):
        """Save application settings."""
        # Save window geometry
        geometry = self.geometry()
        self.settings_manager.set_window_geometry(
            geometry.x(), geometry.y(), geometry.width(), geometry.height()
        )

        # Save settings from each tab
        self.stm32_tab.save_settings()
        self.esp32_tab.save_settings()

        # Write to file
        self.settings_manager.save_settings()

    def on_tab_changed(self, _index: int):
        """Handle tab change event."""
        # Update dual tab summary when switching to it
        current_widget = self.tab_widget.currentWidget()
        if current_widget == self.dual_tab:
            self.dual_tab.update_settings_summary()

    def closeEvent(self, event):
        """Handle application close event."""
        self.save_settings()
        super().closeEvent(event)
