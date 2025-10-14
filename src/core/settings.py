"""Settings management module."""

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple


class SettingsManager:
    """Manages application settings and configuration."""

    def __init__(self):
        """Initialize settings manager."""
        # Use project directory config file instead of home directory
        project_root = Path(__file__).parent.parent.parent  # Go up to project root
        self.config_file = project_root / ".wf_firmware_uploader_config.json"
        self.settings = self._load_default_settings()
        self.load_settings()

    def _load_default_settings(self) -> Dict[str, Any]:
        """Load default settings."""
        return {
            "version": "1.0",
            "window": {"x": 100, "y": 100, "width": 1000, "height": 750},
            "ui": {
                "auto_platform_scale": True,  # Automatically scale based on platform
                "scale_factor": None,  # Custom scale factor (overrides auto scaling)
            },
            "stm32": {
                "last_firmware_path": "",
                "last_port": "SWD",
                "flash_address": "0x08000000",
                "full_erase": False,
                "auto_mode": False,  # Automatic mode for production workflow
                "connection_mode": "HOTPLUG",  # HOTPLUG, UR, Normal
                "hardware_reset": False,
                "connection_speed": 4000,  # kHz
                "retry_attempts": 3,
            },
            "esp32": {
                "last_firmware_files": [],  # List of [address, filepath] pairs
                "last_port": "",
                "full_erase": False,
                "auto_mode": False,  # Automatic mode for production workflow
                "baud_rate": 921600,
                "before_reset": True,  # --before default-reset
                "after_reset": True,  # --after hard-reset
                "no_sync": False,  # --before no-reset-no-sync
                "connect_attempts": 1,
            },
            "counters": {
                "stm32": {"total": 0, "pass": 0, "fail": 0},
                "esp32": {"total": 0, "pass": 0, "fail": 0},
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

    def get_stm32_auto_mode(self) -> bool:
        """Get STM32 automatic mode setting."""
        return self.settings["stm32"].get("auto_mode", False)

    def set_stm32_auto_mode(self, enabled: bool):
        """Set STM32 automatic mode setting."""
        self.settings["stm32"]["auto_mode"] = enabled

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

    def get_esp32_auto_mode(self) -> bool:
        """Get ESP32 automatic mode setting."""
        return self.settings["esp32"].get("auto_mode", False)

    def set_esp32_auto_mode(self, enabled: bool):
        """Set ESP32 automatic mode setting."""
        self.settings["esp32"]["auto_mode"] = enabled

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

    # Upload counters
    def get_counters(self, device_type: str) -> Tuple[int, int, int]:
        """Get upload counters for device type.

        Args:
            device_type: "stm32" or "esp32"

        Returns:
            Tuple of (total, pass, fail)
        """
        device_key = device_type.lower()
        if device_key not in self.settings["counters"]:
            return (0, 0, 0)

        counters = self.settings["counters"][device_key]
        return (
            counters.get("total", 0),
            counters.get("pass", 0),
            counters.get("fail", 0),
        )

    def set_counters(self, device_type: str, total: int, passed: int, failed: int):
        """Set upload counters for device type.

        Args:
            device_type: "stm32" or "esp32"
            total: Total upload count
            passed: Successful upload count
            failed: Failed upload count
        """
        device_key = device_type.lower()
        if device_key not in self.settings["counters"]:
            self.settings["counters"][device_key] = {}

        self.settings["counters"][device_key] = {
            "total": total,
            "pass": passed,
            "fail": failed,
        }

    def increment_counter_pass(self, device_type: str):
        """Increment pass counter for device type.

        Args:
            device_type: "stm32" or "esp32"
        """
        total, passed, failed = self.get_counters(device_type)
        self.set_counters(device_type, total + 1, passed + 1, failed)

    def increment_counter_fail(self, device_type: str):
        """Increment fail counter for device type.

        Args:
            device_type: "stm32" or "esp32"
        """
        total, passed, failed = self.get_counters(device_type)
        self.set_counters(device_type, total + 1, passed, failed + 1)

    def reset_counters(self, device_type: str):
        """Reset all counters for device type to zero.

        Args:
            device_type: "stm32" or "esp32"
        """
        self.set_counters(device_type, 0, 0, 0)
