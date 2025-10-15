"""Dashboard tab module."""

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from core.settings import SettingsManager


class DashboardTab(QWidget):
    """Dashboard tab showing overall status and statistics."""

    def __init__(self, settings_manager: Optional[SettingsManager] = None):
        """Initialize Dashboard tab."""
        super().__init__()
        self.settings_manager = settings_manager
        self.init_ui()

    def init_ui(self):
        """Initialize UI."""
        # Set dashboard dark mode styling (same as STM32/ESP32 tabs)
        self.setStyleSheet(
            """
            QWidget#DashboardTab {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
            QGroupBox {
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #2d2d2d;
                font-size: 14pt;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                color: #e0e0e0;
            }
            QGroupBox > QWidget {
                background-color: #2d2d2d;
            }
            QProgressBar {
                border: 2px solid #3a3a3a;
                border-radius: 5px;
                background-color: #1a1a1a;
                color: #e0e0e0;
                text-align: center;
                min-height: 30px;
            }
            QProgressBar::chunk {
                background-color: #4a90e2;
            }
        """
        )
        self.setObjectName("DashboardTab")

        layout = QVBoxLayout(self)
        layout.setSpacing(20)

        # Title
        title_label = QLabel("📊 Production Dashboard")
        title_label.setStyleSheet(
            "font-size: 18pt; font-weight: bold; color: #e0e0e0; padding: 10px;"
        )
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title_label)

        # === TOP ROW: STM32 and ESP32 Status Cards (2 columns) ===
        status_row = QHBoxLayout()
        status_row.setSpacing(15)

        # STM32 Status Card
        self.stm32_card = self.create_status_card("STM32")
        status_row.addWidget(self.stm32_card)

        # ESP32 Status Card
        self.esp32_card = self.create_status_card("ESP32")
        status_row.addWidget(self.esp32_card)

        layout.addLayout(status_row)
        layout.addStretch()

    def create_status_card(self, device_type: str):
        """Create a status card for a device."""
        card = QGroupBox(f"📟 {device_type} Status")
        # Use global styles from DashboardTab (no custom stylesheet)

        card_layout = QVBoxLayout(card)
        card_layout.setSpacing(10)

        # Status indicator box
        status_box = QWidget()
        status_box.setStyleSheet("background-color: #1e1e1e;")
        status_box_layout = QVBoxLayout(status_box)
        status_box_layout.setContentsMargins(10, 10, 10, 10)

        # Status label
        status_label = QLabel("🔴 Ready")
        status_label.setStyleSheet("font-size: 16pt; font-weight: bold; color: #b0b0b0;")
        status_box_layout.addWidget(status_label)

        # Port info
        port_label = QLabel("Port: ---")
        port_label.setStyleSheet("font-size: 11pt; color: #b0b0b0;")
        status_box_layout.addWidget(port_label)

        # Mode info
        mode_label = QLabel("Mode: Manual")
        mode_label.setStyleSheet("font-size: 11pt; color: #b0b0b0;")
        status_box_layout.addWidget(mode_label)

        # Progress bar
        progress_bar = QProgressBar()
        progress_bar.setFixedHeight(25)  # Fixed height to prevent layout shift
        progress_bar.setVisible(False)
        progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: 2px solid #3a3a3a;
                border-radius: 5px;
                text-align: center;
                font-size: 10pt;
                font-weight: bold;
                background-color: #1a1a1a;
                color: #e0e0e0;
            }
            QProgressBar::chunk {
                background-color: #28a745;
                border-radius: 3px;
            }
        """
        )
        status_box_layout.addWidget(progress_bar)

        card_layout.addWidget(status_box)

        # Statistics section
        stats_label = QLabel("📊 Statistics")
        stats_label.setStyleSheet(
            "font-size: 11pt; font-weight: bold; color: #b0b0b0; margin-top: 10px;"
        )
        card_layout.addWidget(stats_label)

        # Statistics grid
        stats_widget = QWidget()
        stats_widget.setStyleSheet("background-color: #1e1e1e;")
        stats_layout = QVBoxLayout(stats_widget)
        stats_layout.setSpacing(8)
        stats_layout.setContentsMargins(15, 15, 15, 15)

        # TOTAL counter (large, prominent)
        total_label = QLabel("TOTAL")
        total_label.setStyleSheet("font-size: 10pt; color: #b0b0b0; font-weight: bold;")
        stats_layout.addWidget(total_label)

        total_value = QLabel("0")
        total_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        total_value.setStyleSheet(
            """
            QLabel {
                background-color: #2d2d2d;
                border-radius: 8px;
                padding: 15px;
                font-size: 28pt;
                font-weight: bold;
                color: #e0e0e0;
            }
            """
        )
        stats_layout.addWidget(total_value)

        # PASS and FAIL counters (side by side)
        pass_fail_layout = QHBoxLayout()
        pass_fail_layout.setSpacing(8)

        # PASS counter
        pass_container = QVBoxLayout()
        pass_label = QLabel("PASS")
        pass_label.setStyleSheet("font-size: 10pt; color: #28a745; font-weight: bold;")

        pass_value = QLabel("0")
        pass_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pass_value.setStyleSheet(
            """
            QLabel {
                background-color: #28a745;
                color: white;
                border-radius: 6px;
                padding: 12px;
                font-size: 18pt;
                font-weight: bold;
            }
            """
        )

        pass_container.addWidget(pass_label)
        pass_container.addWidget(pass_value)

        # FAIL counter
        fail_container = QVBoxLayout()
        fail_label = QLabel("FAIL")
        fail_label.setStyleSheet("font-size: 10pt; color: #dc3545; font-weight: bold;")

        fail_value = QLabel("0")
        fail_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        fail_value.setStyleSheet(
            """
            QLabel {
                background-color: #dc3545;
                color: white;
                border-radius: 6px;
                padding: 12px;
                font-size: 18pt;
                font-weight: bold;
            }
            """
        )

        fail_container.addWidget(fail_label)
        fail_container.addWidget(fail_value)

        pass_fail_layout.addLayout(pass_container)
        pass_fail_layout.addLayout(fail_container)
        stats_layout.addLayout(pass_fail_layout)

        # Success rate
        rate_label = QLabel("Success Rate: N/A")
        rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rate_label.setStyleSheet(
            """
            QLabel {
                font-size: 11pt;
                color: #e0e0e0;
                padding: 8px;
                background-color: #2d2d2d;
                border-radius: 4px;
            }
            """
        )
        stats_layout.addWidget(rate_label)

        card_layout.addWidget(stats_widget)

        # Store references for updating
        if device_type == "STM32":
            self.stm32_status_label = status_label
            self.stm32_port_label = port_label
            self.stm32_mode_label = mode_label
            self.stm32_progress_bar = progress_bar
            self.stm32_total_value = total_value
            self.stm32_pass_value = pass_value
            self.stm32_fail_value = fail_value
            self.stm32_rate_label = rate_label
        else:
            self.esp32_status_label = status_label
            self.esp32_port_label = port_label
            self.esp32_mode_label = mode_label
            self.esp32_progress_bar = progress_bar
            self.esp32_total_value = total_value
            self.esp32_pass_value = pass_value
            self.esp32_fail_value = fail_value
            self.esp32_rate_label = rate_label

        return card

    def update_status(self, device_type: str, status: str, color: str = "#e74c3c"):
        """Update device status."""
        status_icons = {
            "Ready": "🔴",
            "Uploading": "🟡",
            "Success": "🟢",
            "Failed": "❌",
        }
        icon = status_icons.get(status, "🔴")
        full_status = f"{icon} {status}"

        if device_type == "STM32":
            self.stm32_status_label.setText(full_status)
            self.stm32_status_label.setStyleSheet(
                f"font-size: 16pt; font-weight: bold; color: {color};"
            )
        else:
            self.esp32_status_label.setText(full_status)
            self.esp32_status_label.setStyleSheet(
                f"font-size: 16pt; font-weight: bold; color: {color};"
            )

    def update_port(self, device_type: str, port: str):
        """Update port information."""
        if device_type == "STM32":
            self.stm32_port_label.setText(f"Port: {port}")
        else:
            self.esp32_port_label.setText(f"Port: {port}")

    def update_mode(self, device_type: str, mode: str):
        """Update mode information."""
        if device_type == "STM32":
            self.stm32_mode_label.setText(f"Mode: {mode}")
        else:
            self.esp32_mode_label.setText(f"Mode: {mode}")

    def update_progress(
        self, device_type: str, value: int, visible: bool = True, animated: bool = False
    ):
        """Update progress bar.

        Args:
            device_type: "STM32" or "ESP32"
            value: Progress value (0-100)
            visible: Whether to show the progress bar
            animated: If True, show indeterminate animation; if False, show static progress
        """
        if device_type == "STM32":
            progress_bar = self.stm32_progress_bar
        else:
            progress_bar = self.esp32_progress_bar

        if visible:
            if animated:
                # Show indeterminate animation (for active erasing/uploading)
                progress_bar.setRange(0, 0)
            else:
                # Show static progress bar (for waiting state)
                progress_bar.setRange(0, 100)
                progress_bar.setValue(value)
            progress_bar.setVisible(True)
        else:
            # Hide by making invisible but keep layout space
            progress_bar.setRange(0, 100)
            progress_bar.setValue(0)
            progress_bar.setVisible(False)

    def update_statistics(self, device_type: str):
        """Update statistics from settings."""
        if not self.settings_manager:
            return

        total, passed, failed = self.settings_manager.get_counters(device_type)
        success_rate = (passed / total * 100) if total > 0 else 0

        if device_type == "STM32":
            self.stm32_total_value.setText(str(total))
            self.stm32_pass_value.setText(str(passed))
            self.stm32_fail_value.setText(str(failed))
            if total > 0:
                self.stm32_rate_label.setText(f"Success Rate: {success_rate:.1f}%")
            else:
                self.stm32_rate_label.setText("Success Rate: N/A")
        else:
            self.esp32_total_value.setText(str(total))
            self.esp32_pass_value.setText(str(passed))
            self.esp32_fail_value.setText(str(failed))
            if total > 0:
                self.esp32_rate_label.setText(f"Success Rate: {success_rate:.1f}%")
            else:
                self.esp32_rate_label.setText("Success Rate: N/A")

    def refresh_all(self):
        """Refresh all statistics."""
        self.update_statistics("STM32")
        self.update_statistics("ESP32")
