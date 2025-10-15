"""Test individual stylesheets to find problematic ones."""

from PySide6.QtWidgets import QApplication, QWidget, QPushButton, QGroupBox, QLabel
import sys

app = QApplication(sys.argv)

# Test 1: Main widget stylesheet
print("\n=== Testing main widget stylesheet ===")
w1 = QWidget()
try:
    w1.setStyleSheet(
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
    print("[OK] Main widget stylesheet OK")
except Exception as e:
    print(f"[FAIL] Main widget stylesheet FAILED: {e}")

# Test 2: Auto mode checkbox
print("\n=== Testing auto mode checkbox stylesheet ===")
w2 = QWidget()
try:
    w2.setStyleSheet("QCheckBox { font-weight: bold; color: #ff6b00; font-size: 11pt; }")
    print("[OK] Auto mode checkbox stylesheet OK")
except Exception as e:
    print(f"[FAIL] Auto mode checkbox stylesheet FAILED: {e}")

# Test 3: Upload button
print("\n=== Testing upload button stylesheet ===")
btn = QPushButton()
try:
    btn.setStyleSheet(
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
    print("[OK] Upload button stylesheet OK")
except Exception as e:
    print(f"[FAIL] Upload button stylesheet FAILED: {e}")

# Test 4: Log group
print("\n=== Testing log group stylesheet ===")
group = QGroupBox()
group.setProperty("class", "log-group")
try:
    group.setStyleSheet(
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
    print("[OK] Log group stylesheet OK")
except Exception as e:
    print(f"[FAIL] Log group stylesheet FAILED: {e}")

# Test 5: Clear log button
print("\n=== Testing clear log button stylesheet ===")
btn2 = QPushButton()
btn2.setProperty("class", "log-widget")
try:
    btn2.setStyleSheet(
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
    print("[OK] Clear log button stylesheet OK")
except Exception as e:
    print(f"[FAIL] Clear log button stylesheet FAILED: {e}")

print("\n=== All stylesheet tests completed ===\n")
sys.exit(0)
