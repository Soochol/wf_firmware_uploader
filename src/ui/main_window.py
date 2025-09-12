"""Main window module."""

from typing import Union

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.esp32_uploader import ESP32Uploader
from core.serial_utils import SerialPortManager
from core.stm32_uploader import STM32Uploader


class UploadWorkerThread(QThread):
    """Worker thread for firmware upload tasks."""

    progress_update = Signal(str, str)  # device_type, message
    upload_finished = Signal(str, bool)  # device_type, success

    def __init__(self, device_type, uploader, **kwargs):
        """Initialize worker thread."""
        super().__init__()
        self.device_type = device_type
        self.uploader = uploader
        self.kwargs = kwargs

    def run(self):
        """Execute upload task."""

        def progress_callback(message):
            self.progress_update.emit(self.device_type, message)

        try:
            success = self.uploader.upload_firmware(
                progress_callback=progress_callback, **self.kwargs
            )
            self.upload_finished.emit(self.device_type, success)
        except Exception as e:
            self.progress_update.emit(self.device_type, f"Error: {str(e)}")
            self.upload_finished.emit(self.device_type, False)


class DeviceTab(QWidget):
    """Device-specific tab widget."""

    def __init__(self, device_type: str, file_filter: str):
        """Initialize device tab."""
        super().__init__()
        self.device_type = device_type
        self.file_filter = file_filter
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
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

        # Upload controls
        upload_layout = QHBoxLayout()

        self.upload_btn = QPushButton(f"Upload {self.device_type}")
        upload_layout.addWidget(self.upload_btn)

        self.erase_btn = QPushButton("Erase Flash")
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

    def get_file_path(self) -> str:
        """Return selected file path."""
        return self.file_path_edit.text()

    def get_selected_port(self) -> str:
        """Return selected port."""
        return self.port_combo.currentData() or ""

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


class MainWindow(QMainWindow):
    """Main window class."""

    def __init__(self):
        """Initialize main window."""
        super().__init__()
        self.stm32_uploader = STM32Uploader()
        self.esp32_uploader = ESP32Uploader()
        self.upload_threads = {}
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        self.setWindowTitle("WF Firmware Uploader")
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        layout = QVBoxLayout(central_widget)

        # Tab widget
        self.tab_widget = QTabWidget()

        # STM32 tab
        self.stm32_tab = DeviceTab("STM32", "Binary Files (*.bin *.hex)")
        self.stm32_tab.upload_btn.clicked.connect(lambda: self.start_upload("STM32"))
        self.stm32_tab.erase_btn.clicked.connect(lambda: self.erase_flash("STM32"))
        self.tab_widget.addTab(self.stm32_tab, "STM32")

        # ESP32 tab
        self.esp32_tab = DeviceTab("ESP32", "Binary Files (*.bin)")
        self.esp32_tab.upload_btn.clicked.connect(lambda: self.start_upload("ESP32"))
        self.esp32_tab.erase_btn.clicked.connect(lambda: self.erase_flash("ESP32"))
        self.tab_widget.addTab(self.esp32_tab, "ESP32")

        layout.addWidget(self.tab_widget)

        # Log viewer
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout(log_group)

        log_controls = QHBoxLayout()
        clear_btn = QPushButton("Clear Log")
        clear_btn.clicked.connect(self.clear_log)
        log_controls.addWidget(clear_btn)

        log_controls.addStretch()

        save_btn = QPushButton("Save Log")
        save_btn.clicked.connect(self.save_log)
        log_controls.addWidget(save_btn)

        log_layout.addLayout(log_controls)

        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(200)
        self.log_text.setFont(QFont("Courier", 9))
        self.log_text.setReadOnly(True)
        log_layout.addWidget(self.log_text)

        layout.addWidget(log_group)

    def start_upload(self, device_type: str):
        """Start upload process."""
        if device_type == "STM32":
            tab = self.stm32_tab
            uploader: Union[STM32Uploader, ESP32Uploader] = self.stm32_uploader
        else:
            tab = self.esp32_tab
            uploader = self.esp32_uploader

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

        # Start upload in thread
        kwargs = {"firmware_path": file_path, "port": port}
        thread = UploadWorkerThread(device_type, uploader, **kwargs)
        thread.progress_update.connect(self.on_progress_update)
        thread.upload_finished.connect(self.on_upload_finished)

        self.upload_threads[device_type] = thread
        tab.start_progress()
        tab.update_status("Uploading...")

        thread.start()

    def erase_flash(self, device_type: str):
        """Erase flash memory."""
        if device_type == "STM32":
            tab = self.stm32_tab
            uploader: Union[STM32Uploader, ESP32Uploader] = self.stm32_uploader
        else:
            tab = self.esp32_tab
            uploader = self.esp32_uploader

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

        try:
            tab.update_status("Erasing...")
            success = uploader.erase_flash(
                port, progress_callback=lambda msg: self.append_log(msg, device_type)
            )
            if success:
                tab.update_status("Erase completed")
                self.append_log("Flash erase completed", device_type)
            else:
                tab.update_status("Erase failed")
                self.append_log("Flash erase failed", device_type)
        except Exception as e:
            tab.update_status("Erase error")
            self.append_log(f"Erase error: {str(e)}", device_type)

    def on_progress_update(self, device_type: str, message: str):
        """Handle progress updates."""
        self.append_log(message, device_type)

    def on_upload_finished(self, device_type: str, success: bool):
        """Handle upload completion."""
        if device_type == "STM32":
            tab = self.stm32_tab
        else:
            tab = self.esp32_tab

        tab.finish_progress(success)

        if success:
            tab.update_status("Upload completed")
            self.append_log("Upload completed successfully", device_type)
        else:
            tab.update_status("Upload failed")
            self.append_log("Upload failed", device_type)

        # Clean up thread
        if device_type in self.upload_threads:
            del self.upload_threads[device_type]

    def append_log(self, message: str, device_type: str = ""):
        """Add message to log."""
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
                self.append_log(f"Log saved to: {file_path}")
            except Exception as e:
                self.append_log(f"Failed to save log: {str(e)}")
