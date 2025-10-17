"""STM32 firmware upload module."""

import os
import platform
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# Use winreg only on Windows
if platform.system() == "Windows":
    try:
        import winreg as WINREG  # type: ignore
    except ImportError:
        WINREG = None  # type: ignore
else:
    WINREG = None  # type: ignore

# Windows: Hide console window for subprocess calls
# Prevents CMD windows from flashing when calling STM32_Programmer_CLI
if platform.system() == "Windows":
    CREATE_NO_WINDOW = 0x08000000  # subprocess.CREATE_NO_WINDOW
else:
    CREATE_NO_WINDOW = 0  # Not needed on Linux/Mac


class STM32Uploader:
    """Class responsible for STM32 firmware upload."""

    def __init__(self):
        """Initialize STM32Uploader."""
        self.stm32_programmer_cli = self._find_stm32_programmer_cli()
        self.stop_flag = False

    def _find_stm32_programmer_cli(self) -> str:
        """Find STM32_Programmer_CLI path on Windows/Linux."""
        system_type = platform.system()

        if system_type == "Windows":
            # Windows installation paths
            default_paths = [
                (
                    r"C:\Program Files\STMicroelectronics\STM32Cube"
                    r"\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe"
                ),
                (
                    r"C:\Program Files (x86)\STMicroelectronics\STM32Cube"
                    r"\STM32CubeProgrammer\bin\STM32_Programmer_CLI.exe"
                ),
            ]

            # Check paths in order
            for path in default_paths:
                if os.path.exists(path):
                    return path

            # Search in registry (Windows only)
            if WINREG:
                try:
                    with WINREG.OpenKey(  # type: ignore
                        WINREG.HKEY_LOCAL_MACHINE, "SOFTWARE\\STMicroelectronics"  # type: ignore
                    ) as _:
                        pass
                except FileNotFoundError:
                    pass

            return "STM32_Programmer_CLI.exe"

        else:
            # Linux/WSL paths
            linux_paths = [
                "/opt/st/stm32cubeide_1.14.1/plugins/com.st.stm32cube.ide.mcu.externaltools.cubeprogrammer.linux64_2.1.400.202401151627/tools/bin/STM32_Programmer_CLI",
                "/usr/local/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI",
                "/home/" + os.getenv("USER", "") + "/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI",
                # WSL access to Windows installation
                "/mnt/c/Program Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe",
                "/mnt/c/Program Files (x86)/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe",
            ]

            # Check Linux/WSL paths
            for path in linux_paths:
                if os.path.exists(path):
                    return path

            # Try common alternative names
            return "STM32_Programmer_CLI"

    def is_stm32_programmer_cli_available(self) -> bool:
        """Check if STM32_Programmer_CLI is available."""
        try:
            result = subprocess.run(
                [self.stm32_programmer_cli, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                creationflags=CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def get_device_info(self, port: str) -> Optional[Dict[str, Any]]:
        """Get STM32 device information."""
        if not self.is_stm32_programmer_cli_available():
            return None

        try:
            cmd = [
                self.stm32_programmer_cli,
                "-c",
                "port=SWD",
                "-c",
                "mode=HOTPLUG",
                "--get",
                "option_bytes",
            ]
            if port:
                cmd[2] = f"port={port}"

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False, creationflags=CREATE_NO_WINDOW)

            if result.returncode == 0:
                info: Dict[str, Any] = {"connected": True}
                # Extract information from output
                for line in result.stdout.split("\n"):
                    if "Device ID:" in line:
                        info["device_id"] = line.split("Device ID:")[1].strip()
                    elif "Flash size:" in line:
                        info["flash_size"] = line.split("Flash size:")[1].strip()
                return info
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None

    def upload_firmware(
        self,
        firmware_path: str,
        port: str = "SWD",
        flash_address: str = "0x08000000",
        progress_callback: Optional[Callable[[str], None]] = None,
        connection_mode: str = "HOTPLUG",
        hardware_reset: bool = False,
        connection_speed: int = 4000,
        retry_attempts: int = 3,
        auto_mode: bool = False,
    ) -> bool:
        """Upload STM32 firmware.

        Args:
            auto_mode: If True, waits for MCU connection and auto-uploads.
                      This is the "Automatic mode" from STM32CubeProgrammer.
        """
        if not os.path.exists(firmware_path):
            if progress_callback:
                progress_callback(f"Error: Firmware file not found: {firmware_path}")
            return False

        if not self.is_stm32_programmer_cli_available():
            if progress_callback:
                progress_callback("Error: STM32_Programmer_CLI not found")
            return False

        # Use automatic mode if requested
        if auto_mode:
            return self._upload_automatic_mode(
                firmware_path,
                port,
                flash_address,
                connection_mode,
                hardware_reset,
                connection_speed,
                progress_callback,
            )

        try:
            # Build command with configurable options
            for attempt in range(retry_attempts):
                cmd = [
                    self.stm32_programmer_cli,
                    "-c",
                    f"port={port}",
                    "-c",
                    f"mode={connection_mode}",
                ]

                # Add connection speed
                if connection_speed != 4000:  # Only add if not default
                    cmd.extend(["-c", f"freq={connection_speed}"])

                # Add hardware reset option
                if hardware_reset:
                    cmd.extend(["-c", "reset=HWrst"])

                # Add upload command
                # Use -s (start/run) instead of -rst to properly release SWD connection
                # -s makes the MCU run and releases debugger, preventing connection lock
                cmd.extend([
                    "-w",
                    firmware_path,
                    flash_address,
                    "-v",
                    "-s",  # Start MCU application and release debugger
                ])

                if progress_callback:
                    if attempt > 0:
                        progress_callback(f"STM32 upload retry attempt {attempt + 1}/{retry_attempts}")
                    progress_callback(f"Starting STM32 upload: {Path(firmware_path).name}")
                    progress_callback(f"Port: {port}, Address: {flash_address}")
                    progress_callback(f"Mode: {connection_mode}, Speed: {connection_speed}kHz")
                    if hardware_reset:
                        progress_callback("Hardware reset enabled")

                # Try the upload
                success = self._execute_stm32_command(cmd, progress_callback)
                if success:
                    # CRITICAL: Kill any remaining STM32_Programmer_CLI processes
                    # This is necessary because the CLI sometimes keeps background connections
                    import time
                    if progress_callback:
                        progress_callback("Waiting for upload to complete...")
                    time.sleep(0.5)  # Let upload finish cleanly

                    # Kill any lingering STM32_Programmer_CLI processes
                    self._kill_lingering_processes(progress_callback)

                    # Additional delay for hardware to release
                    time.sleep(0.5)

                    # Try explicit disconnect
                    self._disconnect_programmer(port, connection_mode, progress_callback)
                    return True
                elif attempt < retry_attempts - 1:
                    if progress_callback:
                        progress_callback(f"Upload failed, retrying... ({attempt + 1}/{retry_attempts})")
                    # Wait a bit before retry
                    import time
                    time.sleep(0.5)

            # All attempts failed
            return False

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            if progress_callback:
                progress_callback(f"STM32 upload error: {str(e)}")
            return False

    def _upload_automatic_mode(
        self,
        firmware_path: str,
        port: str,
        flash_address: str,
        connection_mode: str,
        hardware_reset: bool,
        connection_speed: int,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Upload firmware in automatic mode.

        Automatic mode continuously polls for MCU connection,
        then automatically uploads firmware when detected.

        This implements STM32CubeProgrammer's "Automatic mode" via polling.

        Workflow:
        1. Poll for MCU connection every 1 second
        2. When MCU detected (power on), automatically upload
        3. Wait for MCU to disconnect
        4. Loop back to step 1 (wait for next MCU)
        """
        import time

        try:
            if progress_callback:
                progress_callback("=" * 70)
                progress_callback("AUTOMATIC MODE ENABLED")
                progress_callback("=" * 70)
                progress_callback("Polling for MCU connections every 1 second...")
                progress_callback("Connect SWD cable and power on MCU to auto-upload")
                progress_callback("")
                progress_callback("To stop: Close application or press Ctrl+C in terminal")
                progress_callback("=" * 70)
                progress_callback(f"Configuration:")
                progress_callback(f"  Firmware: {Path(firmware_path).name}")
                progress_callback(f"  Address: {flash_address}")
                progress_callback(f"  Port: {port}, Mode: {connection_mode}")
                progress_callback("=" * 70)
                progress_callback("")

            upload_count = 0
            last_connected = False

            # Continuous polling loop
            while not self.stop_flag:
                try:
                    # Check if MCU is connected
                    check_cmd = [
                        self.stm32_programmer_cli,
                        "-c",
                        f"port={port}",
                        "-c",
                        f"mode={connection_mode}",
                        "-c",
                        f"freq={connection_speed}",
                    ]

                    # Quick connection check (1 second timeout)
                    result = subprocess.run(
                        check_cmd,
                        capture_output=True,
                        text=True,
                        timeout=1,
                        check=False,
                        creationflags=CREATE_NO_WINDOW,
                    )

                    # Check if connected
                    is_connected = result.returncode == 0

                    if is_connected and not last_connected:
                        # MCU just connected! Upload immediately
                        upload_count += 1
                        if progress_callback:
                            # Reset background color to default (new MCU connected)
                            progress_callback("BACKGROUND:RESET")
                            progress_callback("")
                            progress_callback(f"MCU #{upload_count} DETECTED!")

                        # Perform upload
                        success = self.upload_firmware(
                            firmware_path=firmware_path,
                            port=port,
                            flash_address=flash_address,
                            progress_callback=progress_callback,
                            connection_mode=connection_mode,
                            hardware_reset=hardware_reset,
                            connection_speed=connection_speed,
                            retry_attempts=1,
                            auto_mode=False,  # Don't recurse!
                        )

                        if success:
                            if progress_callback:
                                progress_callback(f"MCU #{upload_count} UPLOAD SUCCESS!")
                                progress_callback("Ready for next board. Waiting for MCU power off...")
                                progress_callback("")
                                # Send special signals
                                progress_callback("COUNTER:INCREMENT_PASS")
                                progress_callback("BACKGROUND:SUCCESS")
                        else:
                            if progress_callback:
                                progress_callback(f"MCU #{upload_count} UPLOAD FAILED!")
                                progress_callback("Waiting for next MCU...")
                                progress_callback("")
                                # Send special signals
                                progress_callback("COUNTER:INCREMENT_FAIL")
                                progress_callback("BACKGROUND:FAILURE")

                        # IMPORTANT: Keep last_connected = True so we wait for disconnect
                        # This prevents immediate re-upload while MCU is still connected
                        # User must power off MCU before next upload
                        last_connected = True

                    elif not is_connected and last_connected:
                        # MCU disconnected
                        if progress_callback:
                            progress_callback("MCU disconnected. Waiting for next MCU...")
                            progress_callback("")
                        last_connected = False

                    elif not is_connected and not last_connected:
                        # Still waiting for connection
                        if progress_callback and upload_count == 0:
                            # Only show on first wait
                            pass  # Already showed message

                    # Wait before next poll
                    time.sleep(1)

                except subprocess.TimeoutExpired:
                    # Connection check timed out - MCU not connected
                    if last_connected:
                        if progress_callback:
                            progress_callback("MCU disconnected. Waiting for next MCU...")
                            progress_callback("")
                        last_connected = False
                    time.sleep(1)

                except KeyboardInterrupt:
                    if progress_callback:
                        progress_callback("")
                        progress_callback("Automatic mode stopped by user (Ctrl+C)")
                    self.stop_flag = False
                    return 2  # Stopped by user

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
                # No uploads completed
                self.stop_flag = False
                return False  # Status code 0: Failure

        except Exception as e:
            if progress_callback:
                progress_callback(f"Automatic mode error: {str(e)}")
            self.stop_flag = False
            return False

    def _kill_lingering_processes(
        self, progress_callback: Optional[Callable[[str], None]] = None
    ) -> bool:
        """Kill any lingering STM32_Programmer_CLI processes.

        Sometimes STM32_Programmer_CLI keeps running in background maintaining SWD lock.
        This forcefully terminates those processes to release the connection.
        """
        try:
            import subprocess

            system_type = platform.system()

            if system_type == "Windows":
                # Windows: Use taskkill
                cmd = ["taskkill", "/F", "/IM", "STM32_Programmer_CLI.exe", "/T"]
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=3, check=False, creationflags=CREATE_NO_WINDOW
                )

                if "SUCCESS" in result.stdout or "not found" in result.stderr.lower():
                    if progress_callback and "SUCCESS" in result.stdout:
                        progress_callback("Terminated lingering programmer processes")
                    return True
            else:
                # Linux/Mac: Use pkill
                cmd = ["pkill", "-9", "STM32_Programmer"]
                subprocess.run(cmd, capture_output=True, text=True, timeout=3, check=False, creationflags=CREATE_NO_WINDOW)

                if progress_callback:
                    progress_callback("Terminated lingering programmer processes")
                return True

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            # Process killing failures are non-critical
            return False

    def _disconnect_programmer(
        self,
        port: str,
        connection_mode: str,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Disconnect STM32 programmer to allow next upload without power cycle.

        The real issue is that ST-Link hardware maintains its connection.
        We need to explicitly tell the programmer to release the target.
        """
        try:
            if progress_callback:
                progress_callback("Releasing ST-Link connection...")

            # Method 1: Hard reset of ST-Link interface itself
            # This is more aggressive and resets the programmer hardware
            reset_cmd = [
                self.stm32_programmer_cli,
                "-c",
                f"port={port}",
                "-c",
                f"mode={connection_mode}",
                "-c",
                "reset=HWrst",  # Hardware reset - more thorough
            ]

            result = subprocess.run(
                reset_cmd, capture_output=True, text=True, timeout=5, check=False, creationflags=CREATE_NO_WINDOW
            )

            # Wait for hardware to settle
            import time
            time.sleep(0.5)

            # Method 2: Now explicitly disconnect by running without commands
            # Just connect and immediately exit - forces clean disconnect
            disconnect_cmd = [
                self.stm32_programmer_cli,
                "-c",
                f"port={port}",
                "-c",
                f"mode={connection_mode}",
            ]

            # Run with very short timeout to force quick exit
            try:
                subprocess.run(disconnect_cmd, capture_output=True, text=True, timeout=1, check=False, creationflags=CREATE_NO_WINDOW)
            except subprocess.TimeoutExpired:
                pass  # Timeout is expected and desired

            if progress_callback:
                progress_callback("ST-Link connection released")

            # Final wait to ensure ST-Link firmware has released the connection
            time.sleep(0.3)

            return True

        except (FileNotFoundError, OSError) as e:
            # Disconnect errors are not critical
            if progress_callback:
                progress_callback(f"Note: Disconnect command issue: {str(e)}")
            return False

    def _execute_stm32_command(self, cmd, progress_callback):
        """Execute STM32 command and handle output."""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="ignore",  # Ignore encoding errors
                creationflags=CREATE_NO_WINDOW,
            )

            while True:
                if process.stdout is None:
                    break
                output = process.stdout.readline()
                if output == "" and process.poll() is not None:
                    break
                if output and progress_callback:
                    output = output.strip()
                    if output and not output.startswith("Note:"):
                        # Filter out progress bar characters and non-ASCII content
                        if any(char in output for char in ["█", "▓", "▒", "░"]) or "%" in output:
                            # Extract percentage if available
                            try:
                                if "%" in output:
                                    percent_pos = output.find("%")
                                    if percent_pos > 0:
                                        # Find the percentage number before %
                                        start = percent_pos - 1
                                        while start >= 0 and (
                                            output[start].isdigit() or output[start] == "."
                                        ):
                                            start -= 1
                                        if start < percent_pos - 1:
                                            percent = output[start + 1 : percent_pos]
                                            progress_callback(f"Programming... {percent}%")
                            except:
                                progress_callback("Programming...")
                        elif "Memory Programming" in output:
                            progress_callback("Programming flash memory...")
                        elif "Download verified successfully" in output:
                            progress_callback("Verification complete")
                        elif "RUNNING" in output:
                            progress_callback("Firmware uploaded successfully")
                        elif "Download in Progress" in output:
                            progress_callback("Starting download...")
                        elif len(output) > 0 and all(ord(c) < 128 for c in output):
                            # Only display ASCII-only output
                            progress_callback(output)

            return_code = process.wait()

            if return_code == 0:
                if progress_callback:
                    progress_callback("STM32 firmware upload completed successfully!")
                return True
            else:
                if progress_callback:
                    progress_callback(f"STM32 upload failed with return code: {return_code}")
                return False

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            if progress_callback:
                progress_callback(f"STM32 command error: {str(e)}")
            return False

    def erase_flash(
        self,
        port: str = "SWD",
        chip: str = "auto",
        baud_rate: int = 921600,
        before_reset: bool = True,
        after_reset: bool = True,
        no_sync: bool = False,
        connect_attempts: int = 1,
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> bool:
        """Erase STM32 flash.

        Note: STM32 ignores ESP32-specific parameters (chip, baud_rate, etc.)
        but accepts them for interface compatibility.
        """
        if not self.is_stm32_programmer_cli_available():
            return False

        try:
            cmd = [
                self.stm32_programmer_cli,
                "-c",
                f"port={port}",
                "-c",
                "mode=HOTPLUG",
                "-e",
                "all",
            ]

            if progress_callback:
                progress_callback(f"Erasing STM32 flash on port {port}...")
                if baud_rate != 921600:
                    progress_callback(f"Note: STM32 ignores baud rate setting ({baud_rate})")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False, creationflags=CREATE_NO_WINDOW)

            if result.returncode == 0:
                if progress_callback:
                    progress_callback("STM32 flash erased successfully!")
                return True
            else:
                if progress_callback:
                    progress_callback(f"STM32 erase failed: {result.stderr}")
                return False
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            if progress_callback:
                progress_callback(f"STM32 erase error: {str(e)}")
            return False
