"""Settings management module."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


class SettingsManager:
    """Manages application settings and configuration."""

    def __init__(self):
        """Initialize settings manager."""
        self.config_file = Path.home() / ".wf_firmware_uploader_config.json"
        self.settings = self._load_default_settings()
        self.load_settings()

    def _load_default_settings(self) -> Dict[str, Any]:
        """Load default settings."""
        return {
            "version": "1.0",
            "window": {"x": 100, "y": 100, "width": 1000, "height": 750},
            "stm32": {
                "last_firmware_path": "",
                "last_port": "SWD",
                "flash_address": "0x08000000",
                "full_erase": False,
                "connection_mode": "HOTPLUG",  # HOTPLUG, UR, Normal
                "hardware_reset": False,
                "connection_speed": 4000,  # kHz
                "retry_attempts": 3,
            },
            "esp32": {
                "last_firmware_files": [],  # List of [address, filepath] pairs
                "last_port": "",
                "full_erase": False,
                "upload_method": "auto",  # "auto" or "manual"
                "baud_rate": 921600,
                "before_reset": True,  # --before default-reset
                "after_reset": True,  # --after hard-reset
                "no_sync": False,  # --before no-reset-no-sync
                "connect_attempts": 1,
            },
        }

    def load_settings(self) -> bool:
        """Load settings from file."""
        try:
            if self.config_file.exists():
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    self._merge_settings(self.settings, loaded_settings)
                return True
        except (json.JSONDecodeError, FileNotFoundError, PermissionError):
            # If loading fails, keep default settings
            pass
        return False

    def save_settings(self) -> bool:
        """Save settings to file."""
        try:
            # Create parent directory if it doesn't exist
            self.config_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            return True
        except (PermissionError, OSError):
            return False

    def _merge_settings(self, target: Dict[str, Any], source: Dict[str, Any]):
        """Merge source settings into target, preserving structure."""
        for key, value in source.items():
            if key in target:
                if isinstance(target[key], dict) and isinstance(value, dict):
                    self._merge_settings(target[key], value)
                else:
                    target[key] = value

    # Window settings
    def get_window_geometry(self) -> Tuple[int, int, int, int]:
        """Get window geometry (x, y, width, height)."""
        w = self.settings["window"]
        return w["x"], w["y"], w["width"], w["height"]

    def set_window_geometry(self, x: int, y: int, width: int, height: int):
        """Set window geometry."""
        self.settings["window"].update({"x": x, "y": y, "width": width, "height": height})

    # STM32 settings
    def get_stm32_last_firmware(self) -> str:
        """Get last STM32 firmware file path."""
        return self.settings["stm32"]["last_firmware_path"]

    def set_stm32_last_firmware(self, path: str):
        """Set last STM32 firmware file path."""
        self.settings["stm32"]["last_firmware_path"] = path

    def get_stm32_last_port(self) -> str:
        """Get last STM32 port."""
        return self.settings["stm32"]["last_port"]

    def set_stm32_last_port(self, port: str):
        """Set last STM32 port."""
        self.settings["stm32"]["last_port"] = port

    def get_stm32_flash_address(self) -> str:
        """Get STM32 flash address."""
        return self.settings["stm32"]["flash_address"]

    def set_stm32_flash_address(self, address: str):
        """Set STM32 flash address."""
        self.settings["stm32"]["flash_address"] = address

    def get_stm32_full_erase(self) -> bool:
        """Get STM32 full erase setting."""
        return self.settings["stm32"]["full_erase"]

    def set_stm32_full_erase(self, enabled: bool):
        """Set STM32 full erase setting."""
        self.settings["stm32"]["full_erase"] = enabled

    def get_stm32_connection_mode(self) -> str:
        """Get STM32 connection mode setting."""
        return self.settings["stm32"]["connection_mode"]

    def set_stm32_connection_mode(self, mode: str):
        """Set STM32 connection mode setting."""
        self.settings["stm32"]["connection_mode"] = mode

    def get_stm32_hardware_reset(self) -> bool:
        """Get STM32 hardware reset setting."""
        return self.settings["stm32"]["hardware_reset"]

    def set_stm32_hardware_reset(self, enabled: bool):
        """Set STM32 hardware reset setting."""
        self.settings["stm32"]["hardware_reset"] = enabled

    def get_stm32_connection_speed(self) -> int:
        """Get STM32 connection speed setting."""
        return self.settings["stm32"]["connection_speed"]

    def set_stm32_connection_speed(self, speed: int):
        """Set STM32 connection speed setting."""
        self.settings["stm32"]["connection_speed"] = speed

    def get_stm32_retry_attempts(self) -> int:
        """Get STM32 retry attempts setting."""
        return self.settings["stm32"]["retry_attempts"]

    def set_stm32_retry_attempts(self, attempts: int):
        """Set STM32 retry attempts setting."""
        self.settings["stm32"]["retry_attempts"] = max(1, attempts)

    # ESP32 settings
    def get_esp32_last_firmware_files(self) -> List[Tuple[str, str]]:
        """Get last ESP32 firmware files as list of (address, filepath) tuples."""
        return list(self.settings["esp32"]["last_firmware_files"])

    def set_esp32_last_firmware_files(self, files: List[Tuple[str, str]]):
        """Set last ESP32 firmware files."""
        self.settings["esp32"]["last_firmware_files"] = [[addr, path] for addr, path in files]

    def get_esp32_last_port(self) -> str:
        """Get last ESP32 port."""
        return self.settings["esp32"]["last_port"]

    def set_esp32_last_port(self, port: str):
        """Set last ESP32 port."""
        self.settings["esp32"]["last_port"] = port

    def get_esp32_full_erase(self) -> bool:
        """Get ESP32 full erase setting."""
        return self.settings["esp32"]["full_erase"]

    def set_esp32_full_erase(self, enabled: bool):
        """Set ESP32 full erase setting."""
        self.settings["esp32"]["full_erase"] = enabled

    def get_esp32_upload_method(self) -> str:
        """Get ESP32 upload method setting."""
        return self.settings["esp32"]["upload_method"]

    def set_esp32_upload_method(self, method: str):
        """Set ESP32 upload method setting."""
        self.settings["esp32"]["upload_method"] = method

    def get_esp32_baud_rate(self) -> int:
        """Get ESP32 baud rate setting."""
        return self.settings["esp32"]["baud_rate"]

    def set_esp32_baud_rate(self, baud_rate: int):
        """Set ESP32 baud rate setting."""
        self.settings["esp32"]["baud_rate"] = baud_rate

    def get_esp32_before_reset(self) -> bool:
        """Get ESP32 before reset setting."""
        return self.settings["esp32"]["before_reset"]

    def set_esp32_before_reset(self, enabled: bool):
        """Set ESP32 before reset setting."""
        self.settings["esp32"]["before_reset"] = enabled

    def get_esp32_after_reset(self) -> bool:
        """Get ESP32 after reset setting."""
        return self.settings["esp32"]["after_reset"]

    def set_esp32_after_reset(self, enabled: bool):
        """Set ESP32 after reset setting."""
        self.settings["esp32"]["after_reset"] = enabled

    def get_esp32_no_sync(self) -> bool:
        """Get ESP32 no-sync setting."""
        return self.settings["esp32"]["no_sync"]

    def set_esp32_no_sync(self, enabled: bool):
        """Set ESP32 no-sync setting."""
        self.settings["esp32"]["no_sync"] = enabled

    def get_esp32_connect_attempts(self) -> int:
        """Get ESP32 connect attempts setting."""
        return self.settings["esp32"]["connect_attempts"]

    def set_esp32_connect_attempts(self, attempts: int):
        """Set ESP32 connect attempts setting."""
        self.settings["esp32"]["connect_attempts"] = max(1, attempts)

    # Validation helpers
    def validate_file_exists(self, filepath: str) -> bool:
        """Check if file exists."""
        return bool(filepath and Path(filepath).exists())

    def cleanup_missing_files(self):
        """Remove missing files from settings."""
        # Clean STM32 file
        stm32_file = self.get_stm32_last_firmware()
        if stm32_file and not self.validate_file_exists(stm32_file):
            self.set_stm32_last_firmware("")

        # Clean ESP32 files
        esp32_files = self.get_esp32_last_firmware_files()
        valid_files = [
            (addr, path) for addr, path in esp32_files if self.validate_file_exists(path)
        ]
        if len(valid_files) != len(esp32_files):
            self.set_esp32_last_firmware_files(valid_files)
