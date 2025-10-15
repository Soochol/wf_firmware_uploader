"""Counter widget module."""

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


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

        # Set object name BEFORE init (no need for custom styles - use tab's global styles)
        self.setObjectName("counter-widget")
        self._init_ui()
        # Don't apply custom styles - let tab's global styles handle it

    def _init_ui(self):
        """Initialize UI components."""
        layout = QVBoxLayout()
        layout.setSpacing(10)

        # TOTAL counter (large, prominent)
        self.total_label = QLabel("TOTAL")
        self.total_label.setStyleSheet("font-size: 10pt; color: #b0b0b0; font-weight: bold;")

        self.total_value = QLabel("0")
        self.total_value.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Set alignment via Python
        self.total_value.setStyleSheet(
            """
            QLabel {
                background-color: #2d2d2d;
                border: 2px solid #3a3a3a;
                border-radius: 8px;
                padding: 15px;
                font-size: 28pt;
                font-weight: bold;
                color: #e0e0e0;
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
        self.pass_value.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Set alignment via Python
        self.pass_value.setStyleSheet(
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

        pass_container.addWidget(self.pass_label)
        pass_container.addWidget(self.pass_value)

        # FAIL counter
        fail_container = QVBoxLayout()
        self.fail_label = QLabel("FAIL")
        self.fail_label.setStyleSheet("font-size: 10pt; color: #dc3545; font-weight: bold;")

        self.fail_value = QLabel("0")
        self.fail_value.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Set alignment via Python
        self.fail_value.setStyleSheet(
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

        fail_container.addWidget(self.fail_label)
        fail_container.addWidget(self.fail_value)

        pass_fail_layout.addLayout(pass_container)
        pass_fail_layout.addLayout(fail_container)
        layout.addLayout(pass_fail_layout)

        # Success rate
        self.success_rate_label = QLabel("Success Rate: N/A")
        self.success_rate_label.setAlignment(Qt.AlignmentFlag.AlignCenter)  # Set alignment via Python
        self.success_rate_label.setStyleSheet(
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
