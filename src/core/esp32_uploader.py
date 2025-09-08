"""ESP32 firmware upload module."""

import os
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional


class ESP32Uploader:
    """Class responsible for ESP32 firmware upload."""

    def __init__(self):
        """Initialize ESP32Uploader."""
        self.esptool_cmd = "esptool.py"

    def is_esptool_available(self) -> bool:
        """Check if esptool is installed."""
        try:
            result = subprocess.run(
                [sys.executable, "-c", "import esptool"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_chip_info(self, port: str) -> Optional[dict]:
        """Get ESP32 chip information."""
        if not self.is_esptool_available():
            return None

        try:
            cmd = [sys.executable, "-m", "esptool", "--port", port, "chip_id"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)

            if result.returncode == 0:
                info = {}
                for line in result.stdout.split("\n"):
                    if "Chip is" in line:
                        info["chip"] = line.split("Chip is ")[1].strip()
                    elif "MAC:" in line:
                        info["mac"] = line.split("MAC: ")[1].strip()
                return info
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def upload_firmware(
        self,
        firmware_path: str,
        port: str,
        baud_rate: int = 921600,
        flash_address: str = "0x1000",
        chip: str = "auto",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Upload ESP32 firmware."""
        if not os.path.exists(firmware_path):
            if progress_callback:
                progress_callback(f"Error: Firmware file not found: {firmware_path}")
            return False

        if not self.is_esptool_available():
            if progress_callback:
                progress_callback("Error: esptool not found. Install with: pip install esptool")
            return False

        try:
            cmd = [
                sys.executable,
                "-m",
                "esptool",
                "--chip",
                chip,
                "--port",
                port,
                "--baud",
                str(baud_rate),
                "write_flash",
                flash_address,
                firmware_path,
            ]

            if progress_callback:
                progress_callback(f"Starting ESP32 upload: {Path(firmware_path).name}")
                progress_callback(f"Port: {port}, Baud: {baud_rate}, Address: {flash_address}")

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
            )

            while True:
                if process.stdout is None:
                    break
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output and progress_callback:
                    output = output.strip()
                    if output:
                        progress_callback(output)

            return_code = process.wait()

            if return_code == 0:
                if progress_callback:
                    progress_callback("ESP32 firmware upload completed successfully!")
                return True
            else:
                if progress_callback:
                    progress_callback(f"ESP32 upload failed with return code: {return_code}")
                return False

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            if progress_callback:
                progress_callback(f"ESP32 upload error: {str(e)}")
            return False

    def erase_flash(
        self,
        port: str,
        chip: str = "auto",
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Erase ESP32 flash."""
        if not self.is_esptool_available():
            return False

        try:
            cmd = [sys.executable, "-m", "esptool", "--chip", chip, "--port", port, "erase_flash"]

            if progress_callback:
                progress_callback(f"Erasing ESP32 flash on port {port}...")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)

            if result.returncode == 0:
                if progress_callback:
                    progress_callback("ESP32 flash erased successfully!")
                return True
            else:
                if progress_callback:
                    progress_callback(f"ESP32 erase failed: {result.stderr}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            if progress_callback:
                progress_callback(f"ESP32 erase error: {str(e)}")
            return False

    def read_flash_info(self, port: str, chip: str = "auto") -> Optional[dict]:
        """Read ESP32 flash information."""
        if not self.is_esptool_available():
            return None

        try:
            cmd = [sys.executable, "-m", "esptool", "--chip", chip, "--port", port, "flash_id"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)

            if result.returncode == 0:
                info = {}
                for line in result.stdout.split("\n"):
                    if "Manufacturer:" in line:
                        info["manufacturer"] = line.split("Manufacturer: ")[1].strip()
                    elif "Device:" in line:
                        info["device"] = line.split("Device: ")[1].strip()
                    elif "Detected flash size:" in line:
                        info["size"] = line.split("Detected flash size: ")[1].strip()
                return info
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
