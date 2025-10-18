"""STM32 tab module."""

from typing import Optional

from PySide6.QtCore import Qt
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
    QProgressBar,
    QPushButton,
    QRadioButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.serial_utils import SerialPortManager
from core.settings import SettingsManager
from ui.widgets.counter_widget import CounterWidget


class STM32Tab(QWidget):
    """STM32-specific tab widget."""

    def __init__(
        self, device_type: str, file_filter: str, settings_manager: Optional[SettingsManager] = None
    ):
        """Initialize STM32 tab."""
        super().__init__()
        self.device_type = device_type
        self.file_filter = file_filter
        self.settings_manager = settings_manager
        self.counter_widget = None  # Will be initialized in init_ui
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        # Set 10pt font for all widgets in this tab
        # Note: Log widgets override this with their own specific styles
        self.setStyleSheet(
            """
            QLabel, QPushButton, QRadioButton, QCheckBox,
            QGroupBox, QComboBox, QLineEdit {
                font-size: 10pt;
            }
        """
        )

        layout = QVBoxLayout(self)

        # === TOP ROW: 2-COLUMN LAYOUT (Firmware Upload | Counter) ===
        top_row_layout = QHBoxLayout()

        # LEFT COLUMN: Firmware Upload Section (60% width)
        upload_container = QWidget()
        upload_layout = QVBoxLayout(upload_container)
        upload_layout.setContentsMargins(0, 0, 0, 0)

        # File selection group
        file_group = QGroupBox(f"{self.device_type} Firmware File")
        file_layout = QHBoxLayout(file_group)

        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText(f"Select {self.device_type} firmware file")
        file_layout.addWidget(self.file_path_edit)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        file_layout.addWidget(browse_btn)

        upload_layout.addWidget(file_group)

        # Port selection
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Serial Port:"))

        self.port_combo = QComboBox()
        port_layout.addWidget(self.port_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        port_layout.addWidget(refresh_btn)

        upload_layout.addLayout(port_layout)

        # Full Erase option
        self.full_erase_checkbox = QCheckBox("Full Erase before Upload")
        self.full_erase_checkbox.setToolTip("Erase entire flash memory before uploading firmware")
        upload_layout.addWidget(self.full_erase_checkbox)

        # STM32-specific options
        if self.device_type == "STM32":
            # Automatic Mode option
            self.auto_mode_checkbox = QCheckBox("Automatic Mode")
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
            upload_layout.addWidget(self.auto_mode_checkbox)

        upload_layout.addStretch()  # Push content to top

        # RIGHT COLUMN: Counter Widget (40% width)
        self.counter_widget = CounterWidget(device_type=self.device_type)
        # Load saved counters
        if self.settings_manager:
            total, passed, failed = self.settings_manager.get_counters(self.device_type)
            self.counter_widget.set_counters(total, passed, failed)

        # Connect counter signals
        self.counter_widget.counters_reset.connect(self.on_counters_reset)

        # Add to top row with stretch factors (60/40 split)
        top_row_layout.addWidget(upload_container, 60)
        top_row_layout.addWidget(self.counter_widget, 40)

        layout.addLayout(top_row_layout)

        # === BOTTOM SECTION: 1-COLUMN LAYOUT ===

        # STM32 Advanced Connection Settings
        if self.device_type == "STM32":
            self.init_stm32_advanced_settings(layout)

        # Upload controls
        upload_buttons_layout = QHBoxLayout()

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
        upload_buttons_layout.addWidget(self.upload_btn)

        self.erase_btn = QPushButton("Erase Flash")
        self.erase_btn.setMinimumHeight(60)
        upload_buttons_layout.addWidget(self.erase_btn)

        layout.addLayout(upload_buttons_layout)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel(f"{self.device_type}: Ready")
        layout.addWidget(self.status_label)

        # Device log section (moved below upload buttons)
        self.log_group = QGroupBox(f"{self.device_type} Log")
        # Note: Qt CSS class selectors may not work as expected, using direct styling instead
        self.log_group.setStyleSheet(
            """
            QGroupBox {
                font-size: 12pt !important;
                font-weight: bold !important;
                border: 2px solid #cccccc;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
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
        self.clear_log_btn.setStyleSheet(
            """
            QPushButton {
                font-size: 10pt !important;
                padding: 5px 10px;
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
        """
        )
        self.clear_log_btn.clicked.connect(self.clear_log)
        log_controls.addWidget(self.clear_log_btn)

        log_controls.addStretch()

        self.save_log_btn = QPushButton(f"Save {self.device_type} Log")
        self.save_log_btn.setStyleSheet(
            """
            QPushButton {
                font-size: 10pt !important;
                padding: 5px 10px;
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 4px;
            }
            QPushButton:hover {
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

            # Load automatic mode setting
            if hasattr(self, "auto_mode_checkbox"):
                auto_mode = self.settings_manager.get_stm32_auto_mode()
                self.auto_mode_checkbox.setChecked(auto_mode)

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

            # Save automatic mode setting
            if hasattr(self, "auto_mode_checkbox"):
                self.settings_manager.set_stm32_auto_mode(self.auto_mode_checkbox.isChecked())

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
        # Use default color if empty string is provided
        if not color:
            color = "#2b2b2b"

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

    def on_counters_reset(self):
        """Handle counter reset signal."""
        # Save reset counters to settings
        if self.settings_manager:
            self.settings_manager.reset_counters(self.device_type)
            self.settings_manager.save_settings()
        self.append_log(f"{self.device_type} counters reset")

    def set_upload_button_uploading(self):
        """Set upload button to 'uploading/stop' state (red)."""
        self.upload_btn.setText("Stop Automatic Mode")
        self.upload_btn.setStyleSheet(
            """
            QPushButton {
                background-color: #f44336;
                color: white;
                font-weight: bold;
                border-radius: 8px;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: #d32f2f;
            }
            QPushButton:pressed {
                background-color: #b71c1c;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """
        )

    def set_upload_button_ready(self):
        """Set upload button to 'ready' state (green)."""
        self.upload_btn.setText(f"Upload {self.device_type}")
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
