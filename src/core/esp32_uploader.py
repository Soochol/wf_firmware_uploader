"""ESP32 firmware upload module."""

import os
import platform
import subprocess
import sys
from pathlib import Path
from typing import Callable, Optional

# Windows: Hide console window for subprocess calls
# Prevents CMD windows from flashing when calling esptool
if platform.system() == "Windows":
    CREATE_NO_WINDOW = 0x08000000  # subprocess.CREATE_NO_WINDOW
else:
    CREATE_NO_WINDOW = 0  # Not needed on Linux/Mac


class ESP32Uploader:
    """Class responsible for ESP32 firmware upload."""

    def __init__(self):
        """Initialize ESP32Uploader."""
        self.stop_flag = False

    def _check_bootloader_address(
        self,
        files_to_upload: list,
        chip_info: dict,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> tuple[list, bool]:
        """Check and auto-fix bootloader address if needed.

        Returns:
            tuple: (corrected_files_list, was_fixed)
        """
        chip_name = chip_info.get("chip", "").upper()

        # Determine expected bootloader address based on chip type
        if any(variant in chip_name for variant in ["S3", "C3", "C6", "H2", "C2"]):
            expected_addr = "0x0"
            chip_family = "ESP32-S3/C3/C6/H2"
        else:
            expected_addr = "0x1000"
            chip_family = "ESP32 Classic"

        # Check if there's a bootloader file and its address
        corrected_files = files_to_upload.copy()
        was_fixed = False

        for i, (addr, filepath) in enumerate(corrected_files):
            filename = Path(filepath).name.lower()
            if "bootloader" in filename:
                # Normalize addresses for comparison (remove leading zeros)
                addr_int = int(addr, 16)
                expected_int = int(expected_addr, 16)

                if addr_int != expected_int:
                    if progress_callback:
                        progress_callback(
                            f"⚠ WARNING: Bootloader address mismatch detected for {chip_name}"
                        )
                        progress_callback(
                            f"⚠ Auto-fixing: {addr} → {expected_addr} (correct for {chip_family})"
                        )

                    # Fix the address
                    corrected_files[i] = (expected_addr, filepath)
                    was_fixed = True
                else:
                    if progress_callback:
                        progress_callback(f"✓ Bootloader address {addr} is correct for {chip_name}")
                break

        return corrected_files, was_fixed

    def _check_esp32_data(
        self,
        ser,
        wait_for_power_on: bool = False,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Check if ESP32 is powered on by monitoring serial data.

        Args:
            ser: Open serial port object (kept open throughout automatic mode)
            wait_for_power_on: If True, wait for incoming data (MCU power-on detection).
                              If False, check if data stopped (MCU power-off detection).
            progress_callback: Optional callback for debug messages

        This method monitors an already-opened serial port:
        1. wait_for_power_on=True: Wait for data from MCU bootloader (power-on)
        2. wait_for_power_on=False: Check if data flow stopped (power-off)

        Production workflow: Port stays open, monitor data flow to detect MCU power cycles.
        """
        try:
            import time

            if wait_for_power_on:
                # MODE 1: Waiting for NEW MCU to power on
                # Monitor for NEW incoming serial data (MCU bootloader sends data on boot)
                # IMPORTANT: We need to detect FRESH data, not leftover data

                # First, check if there's any data waiting
                waiting = ser.in_waiting

                if waiting > 0:
                    # Read and check if this is bootloader data (not app data)
                    data = ser.read(waiting)

                    # ESP32 bootloader sends specific patterns on boot
                    # Look for bootloader markers like "rst:", "boot:", "ets", etc.
                    data_str = str(data)
                    is_bootloader = any(marker in data_str for marker in [
                        'rst:', 'boot:', 'ets', 'waiting for download', 'ESP-ROM'
                    ])

                    if is_bootloader:
                        if progress_callback:
                            progress_callback(
                                f"DEBUG: Detected bootloader data ({len(data)} bytes) - New MCU!"
                            )
                            progress_callback(f"[BOOTLOADER DATA] {data_str}")
                        return True
                    else:
                        # Application data - ignore and clear
                        if progress_callback:
                            progress_callback(f"DEBUG: Ignoring app data ({len(data)} bytes)")
                            progress_callback(f"[APP DATA] {data_str}")
                        return False

                # No data = MCU not powered yet
                return False

            else:
                # MODE 2: Waiting for current MCU to power off
                # Check CTS (Clear To Send) signal - typically goes LOW when MCU powers off
                try:
                    # Check modem status lines (CTS/DSR)
                    # When MCU powers off, these signals may change
                    cts = ser.getCTS() if hasattr(ser, 'getCTS') else None
                    dsr = ser.getDSR() if hasattr(ser, 'getDSR') else None

                    # If both CTS and DSR are False, MCU likely powered off
                    if cts is False and dsr is False:
                        if progress_callback:
                            progress_callback("DEBUG: CTS/DSR low - MCU powered off")
                        return False

                    # Also check for data - if bootloader was running and now silent
                    # Clear old data first
                    if ser.in_waiting > 0:
                        ser.read(ser.in_waiting)  # Discard

                    # MCU still appears to be powered
                    return True
                except (OSError, AttributeError):
                    # Port error = MCU powered off or disconnected
                    return False

        except Exception as e:
            # Any error likely means connection lost
            if progress_callback:
                progress_callback(f"DEBUG: Serial check error: {str(e)[:100]}")
            return False

    def _upload_automatic_mode(
        self,
        firmware_path,
        port: str,
        baud_rate: int,
        flash_address: str,
        chip: str,
        firmware_files: Optional[list],
        before_reset: bool,
        after_reset: bool,
        no_sync: bool,
        connect_attempts: int,
        progress_callback: Optional[Callable[[str], None]] = None,
        full_erase: bool = False,
    ) -> bool:
        """Automatic mode: Monitor serial port for MCU power cycles.

        This mode opens serial port once and monitors incoming data to detect
        when MCU powers on. Perfect for production workflow:
        1. Click Upload button (port opens and stays open)
        2. Power on ESP32 (bootloader sends data)
        3. Upload starts automatically
        4. Replace board and repeat
        """
        import time
        import serial

        if progress_callback:
            progress_callback("=" * 60)
            progress_callback("AUTOMATIC MODE ENABLED")
            progress_callback("=" * 60)
            progress_callback("Opening serial port for monitoring...")
            progress_callback("")
            progress_callback("Production Workflow:")
            progress_callback("  1. USB stays connected")
            progress_callback("  2. Power on ESP32")
            progress_callback("  3. Upload starts automatically!")
            progress_callback("  4. Power off, replace board and repeat")
            progress_callback("")
            progress_callback("Press 'Stop' button to exit automatic mode")
            progress_callback("=" * 60)

        # Open serial port once and keep it open
        try:
            ser = serial.Serial(port, 115200, timeout=0.1)
            if progress_callback:
                progress_callback(f"Serial port {port} opened for monitoring")
                progress_callback("Waiting for ESP32 to power on...")
                progress_callback("")
        except Exception as e:
            if progress_callback:
                progress_callback(f"Failed to open port {port}: {str(e)}")
            return False

        last_connected = False
        upload_count = 0
        check_count = 0

        try:
            while not self.stop_flag:
                try:
                    check_count += 1

                    # Monitor serial data to detect MCU power cycles
                    wait_for_power_on = not last_connected
                    debug_callback = progress_callback if check_count % 5 == 0 else None
                    is_connected = self._check_esp32_data(
                        ser, wait_for_power_on, debug_callback
                    )

                    # Show periodic status update every 5 seconds
                    if check_count % 5 == 0 and progress_callback:
                        if wait_for_power_on:
                            progress_callback(
                                f"Waiting for new MCU... ({check_count} checks)"
                            )
                        else:
                            progress_callback(
                                f"Monitoring for power-off... ({check_count} checks)"
                            )

                    # Detect rising edge: ESP32 just powered on
                    if is_connected and not last_connected:
                        # Close monitoring port before upload
                        ser.close()

                        upload_count += 1
                        if progress_callback:
                            # Reset background color to default (new MCU connected)
                            progress_callback("BACKGROUND:RESET")
                            progress_callback("")
                            progress_callback("=" * 60)
                            progress_callback(f"ESP32 #{upload_count} DETECTED!")
                            progress_callback("=" * 60)
                            progress_callback(f"Port: {port} - ESP32 is responding")

                        # If Full Erase is enabled, perform it first
                        if full_erase:
                            if progress_callback:
                                progress_callback("")
                                progress_callback("Starting full flash erase...")

                            erase_success = self.erase_flash(
                                port=port,
                                chip=chip,
                                baud_rate=baud_rate,
                                before_reset=True,
                                after_reset=True,
                                no_sync=False,
                                connect_attempts=connect_attempts,
                                progress_callback=progress_callback,
                                skip_connection_check=True,  # Skip check in auto mode
                            )

                            if not erase_success:
                                if progress_callback:
                                    progress_callback("")
                                    progress_callback("=" * 60)
                                    progress_callback(f"ESP32 #{upload_count} ERASE FAILED!")
                                    progress_callback("=" * 60)
                                    progress_callback("Check board connection and try again...")
                                    progress_callback("")
                                    # Send special signal to increment fail counter
                                    progress_callback("COUNTER:INCREMENT_FAIL")
                                # Reopen port and continue
                                try:
                                    ser = serial.Serial(port, 115200, timeout=0.1)
                                except Exception as e:
                                    if progress_callback:
                                        progress_callback(f"Failed to reopen port: {str(e)}")
                                    break
                                last_connected = True
                                time.sleep(1)
                                continue

                            if progress_callback:
                                progress_callback("Flash erase completed successfully")
                                progress_callback("")

                        # Upload firmware
                        result = self.upload_firmware(
                            firmware_path=firmware_path,
                            port=port,
                            baud_rate=baud_rate,
                            flash_address=flash_address,
                            chip=chip,
                            progress_callback=progress_callback,
                            firmware_files=firmware_files,
                            before_reset=True,
                            after_reset=True,
                            no_sync=False,
                            connect_attempts=connect_attempts,
                            auto_mode=False,
                            skip_connection_check=True,  # Skip check in auto mode
                        )

                        # upload_firmware returns (success, corrected_files, was_fixed)
                        success = result[0] if isinstance(result, tuple) else result

                        if success:
                            if progress_callback:
                                progress_callback("")
                                progress_callback("=" * 60)
                                progress_callback(f"ESP32 #{upload_count} UPLOAD SUCCESS!")
                                progress_callback("=" * 60)
                                progress_callback("Ready for next board. Waiting for MCU power off...")
                                progress_callback("")
                                # Send special signals
                                progress_callback("COUNTER:INCREMENT_PASS")
                                progress_callback("BACKGROUND:SUCCESS")
                        else:
                            if progress_callback:
                                progress_callback("")
                                progress_callback("=" * 60)
                                progress_callback(f"ESP32 #{upload_count} UPLOAD FAILED!")
                                progress_callback("=" * 60)
                                progress_callback("Check board connection and try again...")
                                progress_callback("")
                                # Send special signals
                                progress_callback("COUNTER:INCREMENT_FAIL")
                                progress_callback("BACKGROUND:FAILURE")

                        # IMPORTANT: Keep last_connected = True so we wait for disconnect
                        last_connected = True

                        # Reopen serial port for monitoring next cycle
                        try:
                            ser = serial.Serial(port, 115200, timeout=0.1)
                            if progress_callback:
                                progress_callback(f"Port {port} reopened for monitoring")

                            # CRITICAL: Clear all existing data from application running after upload
                            # Wait for data to settle, then flush buffer completely
                            time.sleep(0.5)  # Let ESP32 boot and send initial data
                            if ser.in_waiting > 0:
                                discarded = ser.read(ser.in_waiting)
                                if progress_callback:
                                    progress_callback(f"DEBUG: Cleared {len(discarded)} bytes from buffer")

                        except Exception as e:
                            if progress_callback:
                                progress_callback(f"Failed to reopen port: {str(e)}")
                            break

                    # Detect falling edge: ESP32 disconnected (no more data)
                    elif not is_connected and last_connected:
                        if progress_callback:
                            progress_callback("")
                            progress_callback(f"ESP32 #{upload_count} powered off")
                            progress_callback("Waiting for next board to be powered on...")
                            progress_callback("")
                        # Update state: now waiting for new MCU
                        last_connected = False

                    # Poll interval: 1 second
                    time.sleep(1)

                except KeyboardInterrupt:
                    if progress_callback:
                        progress_callback("")
                        progress_callback("Automatic mode stopped by user")
                    break
                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Error in automatic mode: {str(e)}")
                    time.sleep(1)

        finally:
            # Always close port when exiting automatic mode
            try:
                if ser and ser.is_open:
                    ser.close()
                    if progress_callback:
                        progress_callback(f"Serial port {port} closed")
            except:
                pass

        # Determine return status based on how automatic mode ended
        if self.stop_flag:
            # User clicked Stop button
            if progress_callback:
                progress_callback("")
                progress_callback("Automatic mode stopped by user")
            self.stop_flag = False
            return 2  # Status code 2: Stopped by user
        elif upload_count > 0:
            # At least one upload succeeded
            self.stop_flag = False
            return True  # Status code 1: Success
        else:
            # No uploads completed (port open error or immediate exit)
            self.stop_flag = False
            return False  # Status code 0: Failure

    def _check_port_connection(
        self, port: str, progress_callback: Optional[Callable[[str], None]] = None
    ) -> tuple[bool, Optional[dict]]:
        """Check if ESP32 is connected to the specified port and return chip info.

        Returns:
            tuple: (success: bool, chip_info: Optional[dict])
                   chip_info contains 'chip' and optionally 'mac' if successful
        """
        if not port:
            if progress_callback:
                progress_callback("Error: No port specified")
            return False, None

        try:
            if progress_callback:
                progress_callback(f"Checking ESP32 connection on {port}...")
                # Send special status message to show RESET button guidance
                progress_callback("STATUS:PUSH_RESET")

            # Use sys.executable with -m flag for both dev and PyInstaller
            # PyInstaller includes esptool module, so this works in both environments
            cmd = [sys.executable, "-m", "esptool", "--port", port, "chip_id"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False, creationflags=CREATE_NO_WINDOW)

            if result.returncode == 0:
                # Parse chip information from output
                chip_info = {}
                output = result.stdout + result.stderr
                for line in output.split("\n"):
                    if "Chip is" in line:
                        chip_info["chip"] = line.split("Chip is ")[1].strip()
                    elif "Detecting chip type" in line and "chip" not in chip_info:
                        # Alternative format
                        parts = line.split("...")
                        if len(parts) > 1 and "ESP32" in parts[1]:
                            chip_info["chip"] = parts[1].strip()
                    elif "MAC:" in line:
                        chip_info["mac"] = line.split("MAC: ")[1].strip()

                if progress_callback:
                    progress_callback("ESP32 board detected successfully")
                    if "chip" in chip_info:
                        progress_callback(f"Detected chip: {chip_info['chip']}")
                    # Send status clear message to restore normal status
                    progress_callback("STATUS:CLEAR")
                return True, chip_info if chip_info else None
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
                    # Send status clear message to restore normal status
                    progress_callback("STATUS:CLEAR")
                return False, None

        except subprocess.TimeoutExpired:
            if progress_callback:
                progress_callback(
                    f"Timeout checking ESP32 connection on {port}. Board may not be connected."
                )
                progress_callback("STATUS:CLEAR")
            return False, None
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error checking ESP32 connection: {str(e)}")
                progress_callback("STATUS:CLEAR")
            return False, None

    def is_esptool_available(self) -> bool:
        """Check if esptool is installed."""
        try:
            # Use sys.executable with -m flag for both dev and PyInstaller
            # PyInstaller includes esptool module, so this works in both environments
            result = subprocess.run(
                [sys.executable, "-m", "esptool", "version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
                creationflags=CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_chip_info(
        self, port: str, progress_callback: Optional[Callable[[str], None]] = None
    ) -> Optional[dict]:
        """Get ESP32 chip information."""
        if not self.is_esptool_available():
            if progress_callback:
                progress_callback("Error: esptool not available")
            return None

        try:
            if progress_callback:
                progress_callback(f"Querying chip info on {port}...")

            # Use sys.executable with -m flag for both dev and PyInstaller
            # PyInstaller includes esptool module, so this works in both environments
            cmd = [sys.executable, "-m", "esptool", "--port", port, "chip_id"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False, creationflags=CREATE_NO_WINDOW)

            if result.returncode == 0:
                info = {}
                for line in result.stdout.split("\n"):
                    if "Chip is" in line:
                        chip_str = line.split("Chip is ")[1].strip()
                        info["chip"] = chip_str
                        if progress_callback:
                            progress_callback(f"Found chip: {chip_str}")
                    elif "MAC:" in line:
                        info["mac"] = line.split("MAC: ")[1].strip()

                # Also check stderr for chip detection (esptool sometimes outputs there)
                for line in result.stderr.split("\n"):
                    if "Detecting chip type" in line and "chip" not in info:
                        # Try to extract chip type from detecting message
                        if "ESP32" in line:
                            parts = line.split("...")
                            if len(parts) > 1:
                                chip_type = parts[1].strip()
                                if chip_type:
                                    info["chip"] = chip_type

                if info:
                    return info

                if progress_callback:
                    progress_callback("Chip detection failed: No chip info in response")
                    progress_callback(f"stdout: {result.stdout[:200]}")
                    progress_callback(f"stderr: {result.stderr[:200]}")
            else:
                if progress_callback:
                    progress_callback(f"esptool returned error code: {result.returncode}")
                    if result.stderr:
                        progress_callback(f"Error: {result.stderr[:200]}")

            return None
        except subprocess.TimeoutExpired:
            if progress_callback:
                progress_callback("Error: Chip detection timed out after 15 seconds")
            return None
        except FileNotFoundError:
            if progress_callback:
                progress_callback("Error: esptool command not found")
            return None
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error detecting chip: {str(e)}")
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
        before_reset: bool = True,
        after_reset: bool = True,
        no_sync: bool = False,
        connect_attempts: int = 1,
        auto_mode: bool = False,
        full_erase: bool = False,
        skip_connection_check: bool = False,
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
            auto_mode: If True, continuously poll for ESP32 connection and auto-upload
            skip_connection_check: If True, skip initial connection check (auto mode)
        """
        # If auto mode is enabled, use automatic detection and upload
        if auto_mode:
            return self._upload_automatic_mode(
                firmware_path,
                port,
                baud_rate,
                flash_address,
                chip,
                firmware_files,
                before_reset,
                after_reset,
                no_sync,
                connect_attempts,
                progress_callback,
                full_erase,
            )

        # Handle both single file (legacy) and multiple files
        if firmware_files:
            files_to_upload = firmware_files
        elif firmware_path:
            files_to_upload = [(flash_address, firmware_path)]
        else:
            if progress_callback:
                progress_callback("Error: No firmware files specified")
            return False, [], False

        # Sort files by flash address (ascending order) for proper flashing sequence
        # Convert hex addresses to int for sorting, then keep as strings
        def get_address_value(addr_str):
            """Convert hex address string to integer for sorting."""
            try:
                return int(addr_str, 16)
            except ValueError:
                return 0

        files_to_upload = sorted(files_to_upload, key=lambda x: get_address_value(x[0]))

        if progress_callback and len(files_to_upload) > 1:
            progress_callback(f"Files sorted by address: {[addr for addr, _ in files_to_upload]}")

        # Validate all files exist
        for _, filepath in files_to_upload:
            if not os.path.exists(filepath):
                if progress_callback:
                    progress_callback(f"Error: Firmware file not found: {filepath}")
                return False, files_to_upload, False

        if not self.is_esptool_available():
            if progress_callback:
                progress_callback("Error: esptool not found. Install with: pip install esptool")
            return False, files_to_upload, False

        # Check port connection before upload and get chip info (skip in automatic mode)
        address_was_fixed = False
        if not skip_connection_check:
            connected, chip_info = self._check_port_connection(port, progress_callback)
            if not connected:
                return False, files_to_upload, False

            # Check for bootloader address mismatch and auto-fix
            if chip_info and "chip" in chip_info:
                files_to_upload, address_was_fixed = self._check_bootloader_address(
                    files_to_upload, chip_info, progress_callback
                )

        success = self._upload_with_auto_control(
            files_to_upload,
            port,
            baud_rate,
            chip,
            progress_callback,
            before_reset,
            after_reset,
            no_sync,
            connect_attempts,
        )

        # Return success status, corrected files, and whether address was fixed
        return success, files_to_upload, address_was_fixed

    def _upload_with_auto_control(
        self,
        files_to_upload: list,
        port: str,
        baud_rate: int,
        chip: str,
        progress_callback: Optional[Callable[[str], None]] = None,
        before_reset: bool = True,
        after_reset: bool = True,
        no_sync: bool = False,
        connect_attempts: int = 1,
    ) -> bool:
        """Upload firmware with automatic reset control (original method)."""
        # Use sys.executable with -m flag for both dev and PyInstaller
        # PyInstaller includes esptool module, so this works in both environments
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
        ]

        # Add before reset option
        if no_sync:
            cmd.extend(["--before", "no-reset-no-sync"])
        elif not before_reset:
            cmd.extend(["--before", "no-reset"])
        else:
            cmd.extend(["--before", "default-reset"])

        # Add after reset option
        if not after_reset:
            cmd.extend(["--after", "no-reset"])
        else:
            cmd.extend(["--after", "hard-reset"])

        # Add connect attempts if > 1
        if connect_attempts > 1:
            cmd.extend(["--connect-attempts", str(connect_attempts)])

        # Add write_flash command with flash configuration
        cmd.extend(
            [
                "write_flash",
                "-z",  # Compress data (faster upload)
                "--flash_mode",
                "dio",  # Standard flash mode for most ESP32
                "--flash_freq",
                "40m",  # 40MHz flash frequency (safe default)
                "--flash_size",
                "detect",  # Auto-detect flash size
            ]
        )

        # Add all address-file pairs
        for address, filepath in files_to_upload:
            cmd.extend([address, filepath])

        return self._execute_esptool_command(
            cmd, files_to_upload, port, baud_rate, progress_callback
        )

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
                text=False,  # Binary mode for unbuffered output
                bufsize=0,   # Unbuffered - get output immediately
                creationflags=CREATE_NO_WINDOW,
            )

            output_buffer = ""
            while True:
                if process.stdout is None:
                    break

                # Read one byte at a time for real-time output
                chunk = process.stdout.read(1)
                if chunk == b"" and process.poll() is not None:
                    break

                if chunk and progress_callback:
                    try:
                        char = chunk.decode('utf-8', errors='ignore')
                        output_buffer += char

                        # Send output immediately on newline
                        if char == '\n':
                            output_buffer = output_buffer.strip()
                            if output_buffer:
                                progress_callback(output_buffer)
                            output_buffer = ""
                        elif char == '.':
                            # Send dots immediately for "Connecting..." messages
                            # Don't clear buffer - keep accumulating for complete line
                            if 'Connecting' in output_buffer or 'Writing at' in output_buffer:
                                progress_callback(output_buffer.strip())
                    except Exception:
                        pass

            # Send any remaining buffer
            if output_buffer.strip() and progress_callback:
                progress_callback(output_buffer.strip())

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
        baud_rate: int = 921600,
        before_reset: bool = True,
        after_reset: bool = True,
        no_sync: bool = False,
        connect_attempts: int = 1,
        progress_callback: Optional[Callable[[str], None]] = None,
        skip_connection_check: bool = False,
    ) -> bool:
        """Erase ESP32 flash.

        Args:
            skip_connection_check: If True, skip initial connection check (used in automatic mode)
        """
        if not self.is_esptool_available():
            return False

        # Skip connection check if ESP32 already detected (automatic mode)
        if not skip_connection_check:
            # First, try to connect to verify ESP32 is accessible (like upload does)
            connected, chip_info = self._check_port_connection(port, progress_callback)
            if not connected:
                if progress_callback:
                    progress_callback("Failed to connect to ESP32 for erase operation")
                    progress_callback("Trying alternative connection approach...")
            elif chip_info and "chip" in chip_info and progress_callback:
                # Log chip info during erase
                progress_callback(f"Chip type: {chip_info['chip']}")

        # Try erase with multiple attempts and progressive fallback
        for attempt in range(max(1, connect_attempts)):
            try:
                if attempt > 0 and progress_callback:
                    progress_callback(f"Erase attempt {attempt + 1}/{connect_attempts}")

                # Use lower baud rate on retry attempts
                current_baud = baud_rate if attempt == 0 else min(115200, baud_rate)

                # Use sys.executable with -m flag for both dev and PyInstaller
                # PyInstaller includes esptool module, so this works in both environments
                cmd = [
                    sys.executable,
                    "-m",
                    "esptool",
                    "--chip",
                    chip,
                    "--port",
                    port,
                    "--baud",
                    str(current_baud),
                ]

                # Add before reset option
                if no_sync:
                    cmd.extend(["--before", "no-reset-no-sync"])
                elif not before_reset:
                    cmd.extend(["--before", "no-reset"])
                else:
                    cmd.extend(["--before", "default-reset"])

                # Add after reset option
                if not after_reset:
                    cmd.extend(["--after", "no-reset"])
                else:
                    cmd.extend(["--after", "hard-reset"])

                # Always add connect attempts for erase (more aggressive)
                cmd.extend(["--connect-attempts", str(max(3, connect_attempts))])

                cmd.append("erase-flash")

                if progress_callback:
                    progress_callback(f"Erasing ESP32 flash on port {port}...")
                    progress_callback(f"Using baud rate: {current_baud}")

                # Use Popen for better control and real-time output
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True,
                    creationflags=CREATE_NO_WINDOW,
                )

                # Read output in real-time
                while True:
                    if process.stdout is None:
                        break
                    output = process.stdout.readline()
                    if output == "" and process.poll() is not None:
                        break
                    if output and progress_callback:
                        output = output.strip()
                        if output:
                            # Filter out some verbose esptool messages
                            if not any(
                                skip in output.lower()
                                for skip in ["mac address:", "chip is", "features:"]
                            ):
                                progress_callback(f"Erase: {output}")

                return_code = process.wait()

                if return_code == 0:
                    if progress_callback:
                        progress_callback("ESP32 flash erased successfully!")
                    return True
                else:
                    if attempt == connect_attempts - 1:  # Last attempt
                        if progress_callback:
                            progress_callback(
                                f"ESP32 erase failed after {connect_attempts} attempts"
                            )
                    else:
                        if progress_callback:
                            progress_callback(f"Erase attempt {attempt + 1} failed, retrying...")
                        continue  # Try next attempt

            except subprocess.TimeoutExpired:
                if attempt == connect_attempts - 1:
                    if progress_callback:
                        progress_callback("ESP32 erase timeout - operation took too long")
                    return False
                else:
                    if progress_callback:
                        progress_callback(
                            f"Attempt {attempt + 1} timed out, retrying with different settings..."
                        )
                    continue

            except Exception as e:
                if attempt == connect_attempts - 1:
                    if progress_callback:
                        progress_callback(f"ESP32 erase error: {str(e)}")
                    return False
                else:
                    if progress_callback:
                        progress_callback(f"Attempt {attempt + 1} error: {str(e)}, retrying...")
                    continue

        # If we get here, all attempts failed
        if progress_callback:
            progress_callback("ESP32 erase failed: All connection attempts exhausted")
            progress_callback(
                "Try: 1) Check board connection 2) Press RESET button 3) Use manual upload mode"
            )
        return False

    def read_flash_info(self, port: str, chip: str = "auto") -> Optional[dict]:
        """Read ESP32 flash information."""
        if not self.is_esptool_available():
            return None

        try:
            # Use sys.executable with -m flag for both dev and PyInstaller
            # PyInstaller includes esptool module, so this works in both environments
            cmd = [sys.executable, "-m", "esptool", "--chip", chip, "--port", port, "flash_id"]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False, creationflags=CREATE_NO_WINDOW)

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
