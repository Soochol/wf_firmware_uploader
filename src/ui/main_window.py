"""Main window module."""

from typing import Any, Optional, Union

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.esp32_uploader import ESP32Uploader
from core.settings import SettingsManager
from core.stm32_uploader import STM32Uploader
from ui.tabs import DashboardTab, ESP32Tab, STM32Tab
from ui.workers import UploadWorkerThread


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
        # Apply 12pt font to tab names and remove focus outline
        self.tab_widget.setStyleSheet(
            """
            QTabWidget::pane {
                border: none;
            }
            QTabWidget::tab-bar {
                font-size: 12pt;
            }
            QTabBar {
                background-color: #2d2d2d;
            }
            QTabBar::tab {
                background-color: #2d2d2d;
                color: #e0e0e0;
                font-size: 12pt;
                padding: 8px 16px;
                outline: none;
                border: 1px solid #3a3a3a;
                border-bottom: none;
            }
            QTabBar::tab:selected {
                background-color: #1e1e1e;
                color: #ffffff;
            }
            QTabBar::tab:hover {
                background-color: #3a3a3a;
            }
            QTabBar::tab:focus {
                outline: none;
            }
        """
        )

        # Dashboard tab (FIRST TAB)
        self.dashboard_tab = DashboardTab(self.settings_manager)
        self.tab_widget.addTab(self.dashboard_tab, "📊 Dashboard")

        # STM32 tab
        self.stm32_tab = STM32Tab("STM32", "Binary Files (*.bin *.hex)", self.settings_manager)
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
        """Start upload process (or stop if already running in automatic mode)."""
        kwargs: dict[str, Any] = {}

        # Check if this is ESP32 automatic mode with an already running upload
        if device_type == "ESP32":
            esp32_tab = self.esp32_tab
            auto_mode = esp32_tab.auto_mode_checkbox.isChecked()

            # If automatic mode is enabled and thread is already running, this is a STOP request
            if auto_mode and device_type in self.upload_threads and self.upload_threads[device_type].isRunning():
                # Stop the automatic mode
                self.upload_threads[device_type].request_stop()
                esp32_tab.append_log("Stopping automatic mode...")
                esp32_tab.update_status("Stopping...")
                # Button state will be restored in on_upload_finished()
                return

        # Check if this is STM32 automatic mode with an already running upload
        if device_type == "STM32":
            stm32_tab = self.stm32_tab
            auto_mode = False
            if hasattr(stm32_tab, "auto_mode_checkbox"):
                auto_mode = stm32_tab.auto_mode_checkbox.isChecked()

            # If automatic mode is enabled and thread is already running, this is a STOP request
            if auto_mode and device_type in self.upload_threads and self.upload_threads[device_type].isRunning():
                # Stop the automatic mode
                self.upload_threads[device_type].request_stop()
                stm32_tab.append_log("Stopping automatic mode...")
                stm32_tab.update_status("Stopping...")
                # Button state will be restored in on_upload_finished()
                return

        if device_type == "STM32":
            tab = self.stm32_tab
            uploader: Union[STM32Uploader, ESP32Uploader] = self.stm32_uploader

            # Check if automatic mode
            auto_mode = False
            if hasattr(tab, "auto_mode_checkbox"):
                auto_mode = tab.auto_mode_checkbox.isChecked()

            # Clear log only if NOT in automatic mode (to preserve background color)
            if not auto_mode:
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
            if hasattr(tab, "auto_mode_checkbox"):
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

            # Check if automatic mode
            auto_mode = False
            if hasattr(esp32_tab, "auto_mode_checkbox"):
                auto_mode = esp32_tab.auto_mode_checkbox.isChecked()

            # Clear log only if NOT in automatic mode (to preserve background color)
            if not auto_mode:
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

            # Check if automatic mode is enabled
            auto_mode = False
            if hasattr(esp32_tab, "auto_mode_checkbox"):
                auto_mode = esp32_tab.auto_mode_checkbox.isChecked()

            kwargs.update(
                {
                    "firmware_files": firmware_files,
                    "port": esp32_tab.get_selected_port(),
                    "auto_mode": auto_mode,
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

        # Update dashboard status
        self.dashboard_tab.update_status(device_type, "Uploading", "#f39c12")
        self.dashboard_tab.update_progress(device_type, 0, visible=True, animated=True)

        # Update dashboard port and mode info
        port_display = port if port != "SWD" else "SWD"
        self.dashboard_tab.update_port(device_type, port_display)
        auto_mode = kwargs.get("auto_mode", False)
        mode_display = "Automatic" if auto_mode else "Manual"
        self.dashboard_tab.update_mode(device_type, mode_display)

        # If ESP32 automatic mode, change button to "Stop" state and re-enable it
        if device_type == "ESP32" and auto_mode:
            self.esp32_tab.set_upload_button_uploading()
            # Re-enable upload button for automatic mode (so user can click to stop)
            self.esp32_tab.upload_btn.setEnabled(True)

        # If STM32 automatic mode, change button to "Stop" state and re-enable it
        if device_type == "STM32" and auto_mode:
            self.stm32_tab.set_upload_button_uploading()
            # Re-enable upload button for automatic mode (so user can click to stop)
            self.stm32_tab.upload_btn.setEnabled(True)

        thread.start()

    def load_settings(self):
        """Load settings from settings manager."""
        # Load window geometry
        x, y, width, height = self.settings_manager.get_window_geometry()
        self.setGeometry(x, y, width, height)

        # Load settings for each tab
        self.stm32_tab.load_settings()
        self.esp32_tab.load_settings()

        # Initialize dashboard with current statistics
        self.dashboard_tab.refresh_all()

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
        # Check if message indicates active erasing or uploading
        message_lower = message.lower()
        is_active = any(
            keyword in message_lower
            for keyword in [
                "erasing",
                "uploading",
                "writing",
                "flashing",
                "programming",
                "download",
            ]
        )

        # Update progress bar animation state
        if device_type == "STM32":
            tab = self.stm32_tab
        elif device_type == "ESP32":
            tab = self.esp32_tab
        else:
            tab = None

        if tab and tab.progress_bar.isVisible():
            if is_active:
                # Active operation - show indeterminate animation
                tab.progress_bar.setRange(0, 0)
            else:
                # Waiting or other state - show static progress bar
                tab.progress_bar.setRange(0, 100)
                tab.progress_bar.setValue(100)

        # Update dashboard progress bar animation state
        if self.dashboard_tab.stm32_progress_bar.isVisible() and device_type == "STM32":
            self.dashboard_tab.update_progress(
                device_type, value=100, visible=True, animated=is_active
            )
        elif self.dashboard_tab.esp32_progress_bar.isVisible() and device_type == "ESP32":
            self.dashboard_tab.update_progress(
                device_type, value=100, visible=True, animated=is_active
            )

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

        # Handle special counter increment messages
        if message.startswith("COUNTER:"):
            if message == "COUNTER:INCREMENT_PASS":
                if device_type == "STM32" and self.stm32_tab.counter_widget:
                    self.stm32_tab.counter_widget.increment_pass()
                    self.settings_manager.increment_counter_pass(device_type)
                    self.settings_manager.save_settings()
                elif device_type == "ESP32" and self.esp32_tab.counter_widget:
                    self.esp32_tab.counter_widget.increment_pass()
                    self.settings_manager.increment_counter_pass(device_type)
                    self.settings_manager.save_settings()
                return  # Don't add this to log
            elif message == "COUNTER:INCREMENT_FAIL":
                if device_type == "STM32" and self.stm32_tab.counter_widget:
                    self.stm32_tab.counter_widget.increment_fail()
                    self.settings_manager.increment_counter_fail(device_type)
                    self.settings_manager.save_settings()
                elif device_type == "ESP32" and self.esp32_tab.counter_widget:
                    self.esp32_tab.counter_widget.increment_fail()
                    self.settings_manager.increment_counter_fail(device_type)
                    self.settings_manager.save_settings()
                return  # Don't add this to log

        # Handle special background color messages (for automatic mode)
        if message.startswith("BACKGROUND:"):
            if message == "BACKGROUND:RESET":
                # Reset to default background color (new MCU connected)
                if device_type == "STM32":
                    self.stm32_tab.set_log_background_color("")  # Empty string = default
                elif device_type == "ESP32":
                    self.esp32_tab.set_log_background_color("")  # Empty string = default
                return  # Don't add this to log
            elif message == "BACKGROUND:SUCCESS":
                # Set SUCCESS background color (dark green)
                if device_type == "STM32":
                    self.stm32_tab.set_log_background_color("#1b4332")
                elif device_type == "ESP32":
                    self.esp32_tab.set_log_background_color("#1b4332")
                return  # Don't add this to log
            elif message == "BACKGROUND:FAILURE":
                # Set FAILURE background color (dark red)
                if device_type == "STM32":
                    self.stm32_tab.set_log_background_color("#6a040f")
                elif device_type == "ESP32":
                    self.esp32_tab.set_log_background_color("#6a040f")
                return  # Don't add this to log

        self.append_log(message, device_type)

    def on_upload_finished(
        self, device_type: str, success: bool, corrected_files: list = None, was_fixed: bool = False
    ):
        """Handle upload completion."""
        # Set progress bar to 100% (stop animation, keep visible)
        if device_type == "STM32":
            tab = self.stm32_tab
        elif device_type == "ESP32":
            tab = self.esp32_tab
        else:
            tab = None

        if tab:
            # Stop animation and show 100%
            tab.progress_bar.setRange(0, 100)
            tab.progress_bar.setValue(100)
            tab.set_upload_enabled(True)

        # Update dashboard with final status
        if success == 2:
            # Stopped by user (status code 2)
            self.dashboard_tab.update_status(device_type, "Stopped", "#ff9800")  # Orange
        elif success:
            # Success (status code 1 or True)
            self.dashboard_tab.update_status(device_type, "Success", "#27ae60")
        else:
            # Failure (status code 0 or False)
            self.dashboard_tab.update_status(device_type, "Failed", "#e74c3c")

        # Set dashboard progress bar to 100% (stop animation, keep visible)
        self.dashboard_tab.update_progress(device_type, 100, visible=True, animated=False)

        # Refresh dashboard statistics
        self.dashboard_tab.update_statistics(device_type)

        if success == 2:
            # Stopped by user - don't increment counters
            # Note: "Automatic mode stopped by user" message already sent by uploader

            # Set STOPPED background color (dark orange)
            if device_type == "STM32":
                self.stm32_tab.set_log_background_color("#4a3000")
            elif device_type == "ESP32":
                self.esp32_tab.set_log_background_color("#4a3000")

        elif success == 1 or success == True:
            self.append_log("Upload completed successfully!", device_type)

            # Increment PASS counter
            if device_type == "STM32" and self.stm32_tab.counter_widget:
                self.stm32_tab.counter_widget.increment_pass()
                # Save counter to settings
                self.settings_manager.increment_counter_pass(device_type)
                self.settings_manager.save_settings()
            elif device_type == "ESP32" and self.esp32_tab.counter_widget:
                self.esp32_tab.counter_widget.increment_pass()
                # Save counter to settings
                self.settings_manager.increment_counter_pass(device_type)
                self.settings_manager.save_settings()

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

            # Increment FAIL counter
            if device_type == "STM32" and self.stm32_tab.counter_widget:
                self.stm32_tab.counter_widget.increment_fail()
                # Save counter to settings
                self.settings_manager.increment_counter_fail(device_type)
                self.settings_manager.save_settings()
            elif device_type == "ESP32" and self.esp32_tab.counter_widget:
                self.esp32_tab.counter_widget.increment_fail()
                # Save counter to settings
                self.settings_manager.increment_counter_fail(device_type)
                self.settings_manager.save_settings()

            # Set FAIL background color (dark red)
            if device_type == "STM32":
                self.stm32_tab.set_log_background_color("#6a040f")
            elif device_type == "ESP32":
                self.esp32_tab.set_log_background_color("#6a040f")

        # Update status
        if device_type == "STM32":
            self.stm32_tab.update_status("Ready")
            # Restore upload button to ready state (for automatic mode)
            self.stm32_tab.set_upload_button_ready()
        elif device_type == "ESP32":
            self.esp32_tab.update_status("Ready")
            # Restore upload button to ready state (for automatic mode)
            self.esp32_tab.set_upload_button_ready()

    def erase_flash(self, device_type: str):
        """Erase flash for the specified device type."""
        if device_type == "STM32":
            tab = self.stm32_tab
            uploader = self.stm32_uploader
            # Clear STM32 log before erasing
            self.stm32_tab.clear_log()
            port = tab.get_selected_port()

            # Get STM32 connection settings for erase
            stm32_connection_settings = tab.get_stm32_connection_settings()
        else:  # ESP32
            tab = self.esp32_tab
            uploader = self.esp32_uploader
            # Clear ESP32 log before erasing
            self.esp32_tab.clear_log()
            port = tab.get_selected_port()
            stm32_connection_settings = {}

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
        if device_type == "STM32":
            kwargs.update(stm32_connection_settings)
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

    def on_tab_changed(self, index: int):
        """Handle tab change event."""
        # Refresh dashboard statistics when switching to dashboard tab
        if index == 0:  # Dashboard tab is first (index 0)
            self.dashboard_tab.refresh_all()

    def closeEvent(self, event):
        """Handle application close event."""
        self.save_settings()

        # Stop all running upload threads
        for device_type, thread in self.upload_threads.items():
            if thread.isRunning():
                thread.request_stop()

        # Wait for threads to finish (with timeout)
        for device_type, thread in self.upload_threads.items():
            if thread.isRunning():
                thread.wait(2000)  # Wait up to 2 seconds
                if thread.isRunning():
                    # Force terminate if still running
                    thread.terminate()
                    thread.wait()

        super().closeEvent(event)
