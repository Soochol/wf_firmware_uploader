"""Settings management module."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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
            "window": {"x": 100, "y": 100, "width": 800, "height": 600},
            "stm32": {
                "last_firmware_path": "",
                "last_port": "SWD",
                "flash_address": "0x08000000",
                "full_erase": False,
            },
            "esp32": {
                "last_firmware_files": [],  # List of [address, filepath] pairs
                "last_port": "",
                "full_erase": False,
                "upload_method": "auto",  # "auto" or "manual"
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

    # ESP32 settings
    def get_esp32_last_firmware_files(self) -> List[Tuple[str, str]]:
        """Get last ESP32 firmware files as list of (address, filepath) tuples."""
        return [(addr, path) for addr, path in self.settings["esp32"]["last_firmware_files"]]

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
