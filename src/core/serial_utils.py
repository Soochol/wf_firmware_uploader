"""Serial port management module."""

import platform
from typing import Dict, List

import serial
import serial.tools.list_ports


class SerialPortManager:
    """Class responsible for serial port management."""

    @staticmethod
    def get_available_ports() -> List[Dict[str, str]]:
        """Return information for all available serial ports."""
        ports = []
        for port in serial.tools.list_ports.comports():
            port_info = {
                "device": port.device,
                "description": port.description,
                "hwid": port.hwid if port.hwid else "Unknown",
                "manufacturer": getattr(port, "manufacturer", "Unknown"),
                "product": getattr(port, "product", "Unknown"),
                "vid": getattr(port, "vid", None),
                "pid": getattr(port, "pid", None),
            }
            ports.append(port_info)
        return ports

    @staticmethod
    def get_port_names() -> List[str]:
        """Return list of available serial port names."""
        return [port.device for port in serial.tools.list_ports.comports()]

    @staticmethod
    def is_port_available(port_name: str) -> bool:
        """Check if the specified port is available."""
        available_ports = SerialPortManager.get_port_names()
        return port_name in available_ports

    @staticmethod
    def get_stm32_ports() -> List[Dict[str, str]]:
        """Find STM32-related serial ports."""
        stm32_ports = []
        for port in SerialPortManager.get_available_ports():
            description = port["description"].lower()
            hwid = port["hwid"].lower()

            if any(
                keyword in description or keyword in hwid
                for keyword in ["st-link", "stlink", "stm32", "st micro"]
            ):
                stm32_ports.append(port)

        return stm32_ports

    @staticmethod
    def get_esp32_ports() -> List[Dict[str, str]]:
        """Find ESP32-related serial ports."""
        esp32_ports = []
        for port in SerialPortManager.get_available_ports():
            description = port["description"].lower()
            hwid = port["hwid"].lower()

            if any(
                keyword in description or keyword in hwid
                for keyword in ["cp210", "ch340", "ftdi", "silicon labs", "esp32", "esp8266"]
            ):
                esp32_ports.append(port)

            vid_list = [0x10C4, 0x1A86, 0x0403, 0x239A]
            pid_list = [0xEA60, 0x7523, 0x6001, 0x6014]
            if port["vid"] in vid_list or port["pid"] in pid_list:
                esp32_ports.append(port)

        return esp32_ports

    @staticmethod
    def test_port_connection(port_name: str, baudrate: int = 9600, timeout: float = 1.0) -> bool:
        """Test serial port connection."""
        try:
            with serial.Serial(port_name, baudrate, timeout=timeout) as ser:
                return ser.is_open
        except (serial.SerialException, OSError):
            return False

    @staticmethod
    def get_default_baudrates() -> List[int]:
        """Return list of default baud rates."""
        return [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

    @staticmethod
    def format_port_display(port_info: Dict[str, str]) -> str:
        """Format port information for display to users."""
        device = port_info["device"]
        description = port_info["description"]

        if len(description) > 40:
            description = description[:37] + "..."

        return f"{device} - {description}"

    @staticmethod
    def get_system_info() -> Dict[str, str]:
        """Return system information."""
        return {
            "platform": platform.system(),
            "release": platform.release(),
            "architecture": platform.architecture()[0],
        }
