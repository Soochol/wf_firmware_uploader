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


class STM32Uploader:
    """Class responsible for STM32 firmware upload."""

    def __init__(self):
        """Initialize STM32Uploader."""
        self.stm32_programmer_cli = self._find_stm32_programmer_cli()

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

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15, check=False)

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
    ) -> bool:
        """Upload STM32 firmware."""
        if not os.path.exists(firmware_path):
            if progress_callback:
                progress_callback(f"Error: Firmware file not found: {firmware_path}")
            return False

        if not self.is_stm32_programmer_cli_available():
            if progress_callback:
                progress_callback("Error: STM32_Programmer_CLI not found")
            return False

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
                cmd.extend([
                    "-w",
                    firmware_path,
                    flash_address,
                    "-v",
                    "-rst",
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
                    return True
                elif attempt < retry_attempts - 1:
                    if progress_callback:
                        progress_callback(f"Upload failed, retrying... ({attempt + 1}/{retry_attempts})")

            # All attempts failed
            return False

        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            if progress_callback:
                progress_callback(f"STM32 upload error: {str(e)}")
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

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)

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
