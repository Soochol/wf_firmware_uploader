"""UI component module."""

from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.serial_utils import SerialPortManager


class StatusIndicator(QWidget):
    """Indicator widget that displays device status."""

    def __init__(self, device_name: str):
        """Initialize StatusIndicator."""
        super().__init__()
        self.device_name = device_name
        self.status = "Disconnected"
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.status_label = QLabel(f"{self.device_name}: {self.status}")
        self.status_label.setMinimumWidth(150)
        layout.addWidget(self.status_label)

        self.indicator = QFrame()
        self.indicator.setFixedSize(12, 12)
        self.indicator.setFrameStyle(QFrame.Shape.Box)
        self.set_status("Disconnected")
        layout.addWidget(self.indicator)

    def set_status(self, status: str):
        """Set device status."""
        self.status = status
        self.status_label.setText(f"{self.device_name}: {status}")

        if status == "Connected":
            self.indicator.setStyleSheet("background-color: green; border-radius: 6px;")
        elif status == "Uploading":
            self.indicator.setStyleSheet("background-color: orange; border-radius: 6px;")
        elif status == "Error":
            self.indicator.setStyleSheet("background-color: red; border-radius: 6px;")
        else:
            self.indicator.setStyleSheet("background-color: gray; border-radius: 6px;")


class FirmwareFileSelector(QWidget):
    """Widget for selecting firmware files."""

    file_selected = Signal(str)

    def __init__(self, device_type: str, file_filter: str):
        """Initialize FirmwareFileSelector."""
        super().__init__()
        self.device_type = device_type
        self.file_filter = file_filter
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        group = QGroupBox(f"{self.device_type} Firmware File")
        group_layout = QHBoxLayout(group)

        self.file_path = QLineEdit()
        self.file_path.setPlaceholderText(f"Select {self.device_type} firmware file")
        self.file_path.textChanged.connect(self.file_selected.emit)
        group_layout.addWidget(self.file_path)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_file)
        group_layout.addWidget(browse_btn)

        layout.addWidget(group)

    def browse_file(self):
        """Browse for firmware file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            f"Select {self.device_type} Firmware File",
            "",
            f"{self.file_filter};;All Files (*)",
        )
        if file_path:
            self.file_path.setText(file_path)

    def get_file_path(self) -> str:
        """Get selected file path."""
        return self.file_path.text()

    def set_file_path(self, path: str):
        """Set file path."""
        self.file_path.setText(path)


class UploadProgressWidget(QWidget):
    """Widget for showing upload progress."""

    def __init__(self, device_name: str):
        """Initialize UploadProgressWidget."""
        super().__init__()
        self.device_name = device_name
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Status label
        self.status_label = QLabel(f"{self.device_name}: Ready")
        layout.addWidget(self.status_label)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # Upload button
        self.upload_btn = QPushButton(f"Upload {self.device_name}")
        layout.addWidget(self.upload_btn)

    def start_upload(self):
        """Start upload process."""
        self.upload_btn.setEnabled(False)
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(True)
        self.status_label.setText(f"{self.device_name}: Uploading...")

    def finish_upload(self, success: bool):
        """Finish upload process."""
        self.upload_btn.setEnabled(True)
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1 if success else 0)

        status = "Upload Complete" if success else "Upload Failed"
        self.status_label.setText(f"{self.device_name}: {status}")

        QTimer.singleShot(3000, self.reset_progress)

    def reset_progress(self):
        """Reset progress display."""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"{self.device_name}: Ready")


class SerialPortSelector(QWidget):
    """Widget for selecting serial ports."""

    port_changed = Signal(str)

    def __init__(self):
        """Initialize SerialPortSelector."""
        super().__init__()
        self.init_ui()
        self.refresh_timer = QTimer()
        self.refresh_timer.timeout.connect(self.auto_refresh)
        self.refresh_timer.start(2000)

    def init_ui(self):
        """Initialize UI."""
        layout = QHBoxLayout(self)

        layout.addWidget(QLabel("Serial Port:"))

        self.port_combo = QComboBox()
        self.port_combo.currentTextChanged.connect(self.port_changed.emit)
        layout.addWidget(self.port_combo)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_ports)
        layout.addWidget(refresh_btn)

        self.refresh_ports()

    def refresh_ports(self):
        """Refresh port list."""
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

    def auto_refresh(self):
        """Auto refresh ports."""
        self.refresh_ports()

    def get_selected_port(self) -> str:
        """Get selected port."""
        return self.port_combo.currentData() or ""

    def set_selected_port(self, port: str):
        """Set selected port."""
        index = self.port_combo.findData(port)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)


class LogViewer(QWidget):
    """Widget for viewing logs."""

    def __init__(self):
        """Initialize LogViewer."""
        super().__init__()
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Control buttons
        control_layout = QHBoxLayout()

        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_log)
        control_layout.addWidget(clear_btn)

        control_layout.addStretch()

        save_btn = QPushButton("Save Log")
        save_btn.clicked.connect(self.save_log)
        control_layout.addWidget(save_btn)

        layout.addLayout(control_layout)

        # Log text area
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setFont(QFont("Courier", 10))
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

    def append_log(self, message: str, device_type: str = ""):
        """Append message to log."""
        if device_type:
            formatted_msg = f"[{device_type}] {message}"
        else:
            formatted_msg = message

        self.log_text.append(formatted_msg)

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
            except Exception as e:
                self.append_log(f"Failed to save log: {str(e)}")


class CounterWidget(QGroupBox):
    """Upload statistics counter widget with TOTAL, PASS, FAIL counters."""

    counters_reset = Signal()  # Emitted when reset button clicked

    def __init__(self, device_type: str = "STM32", parent: Optional[QWidget] = None):
        """Initialize counter widget.

        Args:
            device_type: Device type name (STM32 or ESP32)
            parent: Parent widget
        """
        super().__init__("📊 Upload Statistics", parent)
        self.device_type = device_type

        # Counter values
        self.total = 0
        self.passed = 0
        self.failed = 0

        self._init_ui()
        self._apply_styles()

    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # TOTAL counter (large, prominent)
        self.total_label = QLabel("TOTAL")
        self.total_label.setStyleSheet(
            "font-size: 10pt; color: #6c757d; font-weight: bold;"
        )

        self.total_value = QLabel("0")
        self.total_value.setStyleSheet(
            """
            QLabel {
                background-color: #f8f9fa;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                padding: 15px;
                font-size: 28pt;
                font-weight: bold;
                color: #495057;
                qproperty-alignment: AlignCenter;
            }
            """
        )

        layout.addWidget(self.total_label)
        layout.addWidget(self.total_value)
        layout.addSpacing(10)

        # PASS and FAIL counters (side by side)
        pass_fail_layout = QHBoxLayout()

        # PASS counter
        pass_container = QVBoxLayout()
        self.pass_label = QLabel("PASS")
        self.pass_label.setStyleSheet("font-size: 10pt; color: #28a745; font-weight: bold;")

        self.pass_value = QLabel("0")
        self.pass_value.setStyleSheet(
            """
            QLabel {
                background-color: #28a745;
                color: white;
                border-radius: 6px;
                padding: 12px;
                font-size: 18pt;
                font-weight: bold;
                qproperty-alignment: AlignCenter;
            }
            """
        )

        pass_container.addWidget(self.pass_label)
        pass_container.addWidget(self.pass_value)

        # FAIL counter
        fail_container = QVBoxLayout()
        self.fail_label = QLabel("FAIL")
        self.fail_label.setStyleSheet("font-size: 10pt; color: #dc3545; font-weight: bold;")

        self.fail_value = QLabel("0")
        self.fail_value.setStyleSheet(
            """
            QLabel {
                background-color: #dc3545;
                color: white;
                border-radius: 6px;
                padding: 12px;
                font-size: 18pt;
                font-weight: bold;
                qproperty-alignment: AlignCenter;
            }
            """
        )

        fail_container.addWidget(self.fail_label)
        fail_container.addWidget(self.fail_value)

        pass_fail_layout.addLayout(pass_container)
        pass_fail_layout.addLayout(fail_container)
        layout.addLayout(pass_fail_layout)

        # Success rate
        self.success_rate_label = QLabel("Success Rate: N/A")
        self.success_rate_label.setStyleSheet(
            """
            QLabel {
                font-size: 11pt;
                color: #495057;
                padding: 8px;
                background-color: #f8f9fa;
                border-radius: 4px;
                qproperty-alignment: AlignCenter;
            }
            """
        )
        layout.addWidget(self.success_rate_label)
        layout.addSpacing(10)

        # Buttons
        button_layout = QVBoxLayout()
        button_layout.setSpacing(5)

        self.reset_button = QPushButton("Reset Counter")
        self.reset_button.clicked.connect(self._on_reset_clicked)
        self.reset_button.setStyleSheet(
            """
            QPushButton {
                background-color: #6c757d;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #5a6268;
            }
            QPushButton:pressed {
                background-color: #545b62;
            }
            """
        )

        button_layout.addWidget(self.reset_button)
        layout.addLayout(button_layout)

        layout.addStretch()
        self.setLayout(layout)

    def _apply_styles(self):
        """Apply group box styles."""
        self.setStyleSheet(
            """
            QGroupBox {
                font-weight: bold;
                border: 2px solid #dee2e6;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            """
        )

    def increment_pass(self):
        """Increment pass counter (also increments total)."""
        self.total += 1
        self.passed += 1
        self._update_display()

    def increment_fail(self):
        """Increment fail counter (also increments total)."""
        self.total += 1
        self.failed += 1
        self._update_display()

    def reset_counters(self):
        """Reset all counters to zero."""
        self.total = 0
        self.passed = 0
        self.failed = 0
        self._update_display()

    def set_counters(self, total: int, passed: int, failed: int):
        """Set counter values.

        Args:
            total: Total upload count
            passed: Successful upload count
            failed: Failed upload count
        """
        self.total = total
        self.passed = passed
        self.failed = failed
        self._update_display()

    def get_counters(self) -> tuple:
        """Get current counter values.

        Returns:
            Tuple of (total, passed, failed)
        """
        return (self.total, self.passed, self.failed)

    def _update_display(self):
        """Update counter display labels."""
        self.total_value.setText(str(self.total))
        self.pass_value.setText(str(self.passed))
        self.fail_value.setText(str(self.failed))

        # Update success rate
        if self.total > 0:
            rate = (self.passed / self.total) * 100
            self.success_rate_label.setText(f"Success Rate: {rate:.1f}%")
        else:
            self.success_rate_label.setText("Success Rate: N/A")

    def _on_reset_clicked(self):
        """Handle reset button click."""
        # Show confirmation dialog
        reply = QMessageBox.question(
            self,
            "Reset Counters",
            f"Reset all {self.device_type} upload counters?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.reset_counters()
            self.counters_reset.emit()
