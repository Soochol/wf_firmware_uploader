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

    def _check_port_accessibility(
        self, port: str, progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Check if serial port is accessible without ESP32 communication."""
        if not port:
            if progress_callback:
                progress_callback("Error: No port specified")
            return False

        try:
            import serial

            if progress_callback:
                progress_callback(f"Checking port accessibility: {port}")

            # Try to open and close the port quickly
            with serial.Serial(port, 115200, timeout=0.1) as ser:
                if progress_callback:
                    progress_callback(f"Port {port} is accessible")
                return True

        except (serial.SerialException, OSError) as e:
            if progress_callback:
                progress_callback(f"Error: Cannot access port {port}: {str(e)}")
            return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error checking port accessibility: {str(e)}")
            return False

    def _check_port_connection(
        self, port: str, progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Check if ESP32 is connected to the specified port."""
        if not port:
            if progress_callback:
                progress_callback("Error: No port specified")
            return False

        try:
            if progress_callback:
                progress_callback(f"Checking ESP32 connection on {port}...")

            cmd = [sys.executable, "-m", "esptool", "--port", port, "chip_id"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)

            if result.returncode == 0:
                if progress_callback:
                    progress_callback("ESP32 board detected successfully")
                return True
            else:
                if progress_callback:
                    if "could not open port" in result.stderr.lower():
                        progress_callback(
                            f"Error: Could not open port {port}. Check if board is connected and port is not in use."
                        )
                    elif "no serial data received" in result.stderr.lower():
                        progress_callback(
                            f"Error: No response from ESP32 on {port}. Check board connection and try pressing reset button."
                        )
                    else:
                        progress_callback(f"Error: Failed to detect ESP32 on {port}")
                return False

        except subprocess.TimeoutExpired:
            if progress_callback:
                progress_callback(
                    f"Timeout checking ESP32 connection on {port}. Board may not be connected."
                )
            return False
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error checking ESP32 connection: {str(e)}")
            return False

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
        firmware_path=None,
        port: str = "",
        baud_rate: int = 921600,
        flash_address: str = "0x10000",
        chip: str = "auto",
        progress_callback: Optional[Callable[[str], None]] = None,
        firmware_files: Optional[list] = None,
        upload_method: str = "auto",
    ) -> bool:
        """Upload ESP32 firmware.

        Args:
            firmware_path: Single firmware file path (legacy support)
            port: Serial port
            baud_rate: Baud rate for upload
            flash_address: Flash address for single file (legacy support)
            chip: ESP32 chip type
            progress_callback: Progress callback function
            firmware_files: List of (address, filepath) tuples for multiple files
            upload_method: 'auto' for automatic reset or 'manual' for DTR/RTS control
        """
        # Handle both single file (legacy) and multiple files
        if firmware_files:
            files_to_upload = firmware_files
        elif firmware_path:
            files_to_upload = [(flash_address, firmware_path)]
        else:
            if progress_callback:
                progress_callback("Error: No firmware files specified")
            return False

        # Validate all files exist
        for address, filepath in files_to_upload:
            if not os.path.exists(filepath):
                if progress_callback:
                    progress_callback(f"Error: Firmware file not found: {filepath}")
                return False

        if not self.is_esptool_available():
            if progress_callback:
                progress_callback("Error: esptool not found. Install with: pip install esptool")
            return False

        # Use different upload method based on selection
        if upload_method == "manual":
            # For manual mode, only check basic port accessibility
            if progress_callback:
                progress_callback("Using manual DTR/RTS control")
            if not self._check_port_accessibility(port, progress_callback):
                return False
            return self._upload_with_manual_control(
                files_to_upload, port, baud_rate, chip, progress_callback
            )
        else:
            # Check port connection before auto upload
            if not self._check_port_connection(port, progress_callback):
                return False
            return self._upload_with_auto_control(
                files_to_upload, port, baud_rate, chip, progress_callback
            )

    def _upload_with_auto_control(
        self,
        files_to_upload: list,
        port: str,
        baud_rate: int,
        chip: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Upload firmware with automatic reset control (original method)."""
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
        ]

        # Add all address-file pairs
        for address, filepath in files_to_upload:
            cmd.extend([address, filepath])

        return self._execute_esptool_command(
            cmd, files_to_upload, port, baud_rate, progress_callback
        )

    def _upload_with_manual_control(
        self,
        files_to_upload: list,
        port: str,
        baud_rate: int,
        chip: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Upload firmware with manual DTR/RTS control."""
        from .serial_boot_controller import SerialBootController

        try:
            if progress_callback:
                progress_callback("Using manual DTR/RTS control for ESP32 upload")

            # For TTL-RS232 modules, use lower baud rate for better compatibility
            upload_baud_rate = 115200 if baud_rate > 115200 else baud_rate
            if upload_baud_rate != baud_rate and progress_callback:
                progress_callback(f"Using {upload_baud_rate} baud for TTL-RS232 compatibility")

            # Step 1: Enter boot mode using DTR/RTS control
            controller = SerialBootController(port, upload_baud_rate)
            if not controller.open_connection():
                if progress_callback:
                    progress_callback("Error: Could not open serial connection for DTR/RTS control")
                    progress_callback(
                        "Check: 1) Port is not in use 2) TTL-RS232 module connected 3) Correct port selected"
                    )
                return False

            if progress_callback:
                progress_callback("Entering ESP32 boot mode via DTR/RTS control...")

            if not controller.enter_boot_mode(progress_callback):
                controller.close_connection()
                if progress_callback:
                    progress_callback(
                        "Failed to enter boot mode. Check DTR→GPIO0 and RTS→EN wiring"
                    )
                return False

            # Verify if ESP32 actually entered boot mode
            boot_mode_verified = controller.verify_boot_mode(progress_callback)
            controller.close_connection()

            if not boot_mode_verified:
                if progress_callback:
                    progress_callback("Boot mode verification failed!")
                    progress_callback("Possible issues:")
                    progress_callback("1. DTR not connected to GPIO0")
                    progress_callback("2. RTS not connected to EN/RST")
                    progress_callback("3. TX/RX wires swapped")
                    progress_callback("4. ESP32 hardware problem")
                    progress_callback("5. Try physical BOOT+RESET buttons")
                # Continue anyway - esptool might still work
                if progress_callback:
                    progress_callback("Continuing upload attempt...")

            # Longer delay to ensure ESP32 is stable in boot mode for TTL-RS232
            import time

            time.sleep(0.5)  # Increased stabilization time

            # Step 2: Use esptool with manual reset options
            cmd = [
                sys.executable,
                "-m",
                "esptool",
                "--chip",
                chip,
                "--port",
                port,
                "--baud",
                str(upload_baud_rate),  # Use the compatible baud rate
                "--before",
                "no-reset",  # Don't reset before
                "--after",
                "no-reset",  # Don't reset after
                "write-flash",
            ]

            # Add all address-file pairs
            for address, filepath in files_to_upload:
                cmd.extend([address, filepath])

            result = self._execute_esptool_command(
                cmd, files_to_upload, port, upload_baud_rate, progress_callback
            )

            # If upload failed, try once more with boot mode re-entry
            if not result and progress_callback:
                progress_callback("Upload failed, retrying with boot mode re-entry...")

                # Re-enter boot mode
                controller = SerialBootController(port, upload_baud_rate)
                if controller.open_connection():
                    if controller.enter_boot_mode(progress_callback):
                        # Verify boot mode on retry as well
                        retry_verified = controller.verify_boot_mode(progress_callback)
                        controller.close_connection()

                        if not retry_verified:
                            if progress_callback:
                                progress_callback("Retry: Boot mode verification failed again")
                                progress_callback("Hardware connection issue likely - check wiring")

                        time.sleep(0.5)  # Consistent stabilization time

                        if progress_callback:
                            progress_callback("Retrying upload after boot mode re-entry...")
                        result = self._execute_esptool_command(
                            cmd, files_to_upload, port, upload_baud_rate, progress_callback
                        )
                    else:
                        controller.close_connection()

            # Step 3: Normal boot after upload (if successful)
            if result:
                controller = SerialBootController(port, upload_baud_rate)
                if controller.open_connection():
                    controller.normal_boot(progress_callback)
                    controller.close_connection()

            return result

        except Exception as e:
            if progress_callback:
                progress_callback(f"Manual control upload error: {str(e)}")
            return False

    def _execute_esptool_command(
        self,
        cmd: list,
        files_to_upload: list,
        port: str,
        baud_rate: int,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Execute esptool command with progress monitoring."""
        try:
            if progress_callback:
                file_list = ", ".join([Path(fp).name for _, fp in files_to_upload])
                progress_callback(f"Starting ESP32 upload: {file_list}")
                progress_callback(f"Port: {port}, Baud: {baud_rate}")
                for address, filepath in files_to_upload:
                    progress_callback(f"  {address}: {Path(filepath).name}")

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

        except subprocess.TimeoutExpired:
            if progress_callback:
                progress_callback("ESP32 upload timeout - check board connection and try again")
            return False
        except FileNotFoundError:
            if progress_callback:
                progress_callback("Error: esptool not found. Install with: pip install esptool")
            return False
        except OSError as e:
            if progress_callback:
                if "could not open port" in str(e).lower():
                    progress_callback(
                        f"ESP32 connection error: Port may be in use or board not connected"
                    )
                else:
                    progress_callback(f"ESP32 system error: {str(e)}")
            return False
        except Exception as e:
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
