"""Centralized theme styles for the application."""


# Dark mode stylesheet for device tabs (STM32/ESP32)
DEVICE_TAB_DARK_STYLE = """
QWidget:not(#counter-widget) {
    background-color: #1e1e1e;
    color: #e0e0e0;
}
QLabel:not(.log-widget),
QPushButton:not(.log-widget),
QRadioButton, QCheckBox,
QComboBox, QLineEdit {
    font-size: 10pt;
    color: #e0e0e0;
    background-color: #2d2d2d;
}
QGroupBox:not(#counter-widget) {
    border: 2px solid #3a3a3a;
    border-radius: 8px;
    margin-top: 10px;
    padding-top: 15px;
    background-color: #2d2d2d;
}
QGroupBox::title {
    color: #e0e0e0;
}
QLineEdit, QComboBox {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 5px;
    color: #e0e0e0;
}
QLineEdit:focus, QComboBox:focus {
    border: 1px solid #4a90e2;
}
QComboBox::drop-down {
    border: none;
}
QComboBox::down-arrow {
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid #e0e0e0;
    margin-right: 5px;
}
QCheckBox, QRadioButton {
    color: #e0e0e0;
}
QCheckBox::indicator, QRadioButton::indicator {
    width: 18px;
    height: 18px;
    border: 2px solid #3a3a3a;
    border-radius: 3px;
    background-color: #2d2d2d;
}
QCheckBox::indicator:checked, QRadioButton::indicator:checked {
    background-color: #4a90e2;
    border-color: #4a90e2;
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

# ESP32-specific additions (includes QListWidget styling)
ESP32_TAB_DARK_STYLE = DEVICE_TAB_DARK_STYLE + """
QListWidget {
    background-color: #2d2d2d;
    border: 1px solid #3a3a3a;
    border-radius: 4px;
    padding: 5px;
    color: #e0e0e0;
}
QListWidget::item {
    padding: 5px;
    color: #e0e0e0;
}
QListWidget::item:selected {
    background-color: #4a90e2;
}
"""

# Log group box style (used in both STM32 and ESP32 tabs)
LOG_GROUP_STYLE = """
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

# Log button style
LOG_BUTTON_CLEAR_STYLE = """
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

LOG_BUTTON_SAVE_STYLE = """
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

# Log text area style
LOG_TEXT_STYLE = """
QTextEdit {
    background-color: #2b2b2b;
    color: #ffffff;
    border: 1px solid #555;
    border-radius: 4px;
    padding: 5px;
    font-family: 'Courier New', monospace;
}
"""


def get_log_text_style_with_color(color: str) -> str:
    """Get log text style with custom background color.

    Args:
        color: Background color (e.g., "#2b2b2b", "#1b4332" for success, "#6a040f" for failure)

    Returns:
        Stylesheet string with the specified background color
    """
    return f"""
    QTextEdit {{
        background-color: {color};
        color: #ffffff;
        border: 1px solid #555;
        border-radius: 4px;
        padding: 5px;
        font-family: 'Courier New', monospace;
    }}
    """


# Upload button style (green)
UPLOAD_BUTTON_STYLE = """
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

# Dashboard tab style
DASHBOARD_TAB_STYLE = """
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

# Tab widget style
TAB_WIDGET_STYLE = """
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

# STM32 automatic mode checkbox style
STM32_AUTO_MODE_CHECKBOX_STYLE = """
QCheckBox {
    font-weight: bold;
    color: #ff6b00;
    font-size: 11pt;
}
"""

# ESP32 automatic mode checkbox style
ESP32_AUTO_MODE_CHECKBOX_STYLE = """
font-weight: bold;
color: #ff6b00;
margin-bottom: 10px;
"""

# ESP32 reset guidance label style
ESP32_RESET_GUIDANCE_STYLE = """
QLabel {
    background-color: #ff5722;
    color: white;
    padding: 10px;
    border-radius: 6px;
    border: 3px solid #d32f2f;
    font-size: 14px;
    font-weight: bold;
}
"""
