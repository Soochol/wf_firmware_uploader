"""UI component module."""

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
        self.indicator.setFrameStyle(QFrame.Box)
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
        self.log_text.setFont(QFont("Courier", 9))
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
