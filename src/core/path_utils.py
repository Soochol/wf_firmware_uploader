"""Path utility functions for finding firmware and resource files."""

import sys
from pathlib import Path


def get_application_path() -> Path:
    """
    Get the application's base path.

    Returns the correct path whether running from source or as a bundled executable.

    Returns:
        Path: Base path of the application
            - Development: Project root directory
            - Production: Directory containing the .exe file
    """
    if getattr(sys, 'frozen', False):
        # Running as compiled executable (PyInstaller)
        # sys.executable points to WF_Firmware_Uploader.exe
        return Path(sys.executable).parent
    else:
        # Running from source code
        # Go up from src/ to project root
        return Path(__file__).parent.parent.parent


def get_firmwares_path() -> Path:
    """
    Get the path to the firmwares directory.

    Returns:
        Path: Path to firmwares/ directory
    """
    return get_application_path() / "firmwares"


def get_esp32_firmware_path() -> Path:
    """
    Get the path to ESP32 firmware directory.

    Returns:
        Path: Path to firmwares/esp32/ directory
    """
    return get_firmwares_path() / "esp32"


def get_stm32_firmware_path() -> Path:
    """
    Get the path to STM32 firmware directory.

    Returns:
        Path: Path to firmwares/stm32/ directory
    """
    return get_firmwares_path() / "stm32"


def get_default_esp32_files() -> list[tuple[str, str]]:
    """
    Get default ESP32 firmware files with their flash addresses.

    Returns:
        list: List of (address, file_path) tuples
            Example: [("0x0", "C:/path/bootloader.bin"), ...]
    """
    esp32_path = get_esp32_firmware_path()

    return [
        ("0x0", str(esp32_path / "bootloader.bin")),
        ("0x8000", str(esp32_path / "partitions.bin")),
        ("0x10000", str(esp32_path / "firmware.bin")),
    ]


def get_default_stm32_file() -> str:
    """
    Get default STM32 firmware file path.

    Returns:
        str: Path to default STM32 firmware file (WithForce_1.00.34.hex)
    """
    stm32_path = get_stm32_firmware_path()
    return str(stm32_path / "WithForce_1.00.34.hex")


def validate_firmware_exists() -> dict[str, bool]:
    """
    Check if firmware files exist.

    Returns:
        dict: Status of firmware files
            {
                "esp32_bootloader": True/False,
                "esp32_partitions": True/False,
                "esp32_firmware": True/False,
                "stm32_firmware": True/False
            }
    """
    esp32_path = get_esp32_firmware_path()
    stm32_path = get_stm32_firmware_path()

    return {
        "esp32_bootloader": (esp32_path / "bootloader.bin").exists(),
        "esp32_partitions": (esp32_path / "partitions.bin").exists(),
        "esp32_firmware": (esp32_path / "firmware.bin").exists(),
        "stm32_firmware": (stm32_path / "WithForce_1.00.34.hex").exists(),
    }
