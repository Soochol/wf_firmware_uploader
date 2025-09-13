"""Serial boot controller for ESP32 TTL-RS232 manual reset."""

import time
from typing import Callable, Optional

import serial


class SerialBootController:
    """Controls ESP32 boot mode through DTR/RTS signals."""

    def __init__(self, port: str, baud_rate: int = 115200):
        """Initialize serial boot controller.

        Args:
            port: Serial port name
            baud_rate: Baud rate for communication
        """
        self.port = port
        self.baud_rate = baud_rate
        self.serial_connection: Optional[serial.Serial] = None

    def open_connection(self) -> bool:
        """Open serial connection.

        Returns:
            True if connection opened successfully
        """
        try:
            self.serial_connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1,
                write_timeout=1,
                # Important: Disable hardware flow control to prevent interference
                rtscts=False,
                dsrdtr=False,
            )
            return True
        except (serial.SerialException, OSError):
            return False

    def close_connection(self):
        """Close serial connection."""
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
            self.serial_connection = None

    def enter_boot_mode(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Enter ESP32 boot/programming mode.

        Boot mode sequence:
        1. GPIO0 = LOW (DTR = True)
        2. EN = LOW (RTS = True) - Reset
        3. EN = HIGH (RTS = False) - Release reset while GPIO0 still LOW
        4. GPIO0 can be released after a short delay

        Returns:
            True if sequence completed successfully
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            if progress_callback:
                progress_callback("Error: Serial connection not open")
            return False

        try:
            if progress_callback:
                progress_callback("Entering ESP32 boot mode...")

            # Step 1: Pull GPIO0 LOW (DTR = True, active low)
            self.serial_connection.dtr = True  # GPIO0 = LOW
            time.sleep(0.25)  # Increased for TTL-RS232 compatibility

            # Step 2: Reset the chip (RTS = True, active low)
            self.serial_connection.rts = True  # EN = LOW (reset)
            time.sleep(0.25)  # Increased reset hold time

            # Step 3: Release reset while GPIO0 is still LOW
            self.serial_connection.rts = False  # EN = HIGH (release reset)
            time.sleep(0.25)  # Increased stabilization time

            # Step 4: Keep GPIO0 LOW for a bit more, then release
            time.sleep(0.05)  # Additional hold time
            self.serial_connection.dtr = False  # GPIO0 can be released

            if progress_callback:
                progress_callback("DTR/RTS boot sequence completed")

            return True

        except (serial.SerialException, OSError) as e:
            if progress_callback:
                progress_callback(f"Error entering boot mode: {str(e)}")
            return False

    def verify_boot_mode(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Verify if ESP32 actually entered boot mode by testing communication."""
        if not self.serial_connection or not self.serial_connection.is_open:
            if progress_callback:
                progress_callback("Error: Serial connection not open for verification")
            return False

        try:
            if progress_callback:
                progress_callback("Verifying ESP32 boot mode...")

            # Send a simple command to check if ESP32 responds in boot mode
            # ESP32 bootloader responds to sync commands
            sync_command = b"\xc0\x00\x08\x24\x00\x00\x00\x00\x00\x07\x07\x12\x20\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\x55\xc0"

            # Clear any existing data
            self.serial_connection.reset_input_buffer()
            self.serial_connection.reset_output_buffer()

            # Send sync command
            self.serial_connection.write(sync_command)
            self.serial_connection.flush()

            # Wait for response
            import time

            time.sleep(0.1)

            # Check if we got any response
            if self.serial_connection.in_waiting > 0:
                response = self.serial_connection.read(self.serial_connection.in_waiting)
                if len(response) > 0:
                    if progress_callback:
                        progress_callback("ESP32 boot mode verified - device responding")
                    return True

            if progress_callback:
                progress_callback("Warning: No response from ESP32 - may not be in boot mode")
            return False

        except Exception as e:
            if progress_callback:
                progress_callback(f"Boot mode verification failed: {str(e)}")
            return False

    def normal_boot(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Boot ESP32 in normal mode (run application).

        Normal boot sequence:
        1. GPIO0 = HIGH (or floating)
        2. Reset pulse on EN

        Returns:
            True if sequence completed successfully
        """
        if not self.serial_connection or not self.serial_connection.is_open:
            if progress_callback:
                progress_callback("Error: Serial connection not open")
            return False

        try:
            if progress_callback:
                progress_callback("Performing normal ESP32 boot...")

            # Step 1: Ensure GPIO0 is HIGH (normal boot)
            self.serial_connection.dtr = False  # GPIO0 = HIGH

            # Step 2: Reset pulse
            self.serial_connection.rts = True  # EN = LOW (reset)
            time.sleep(0.1)
            self.serial_connection.rts = False  # EN = HIGH (release reset)
            time.sleep(0.1)

            if progress_callback:
                progress_callback("ESP32 normal boot completed")

            return True

        except (serial.SerialException, OSError) as e:
            if progress_callback:
                progress_callback(f"Error during normal boot: {str(e)}")
            return False

    def test_connection(self, progress_callback: Optional[Callable[[str], None]] = None) -> bool:
        """Test serial connection and signal control.

        Returns:
            True if connection and control signals work
        """
        if not self.open_connection():
            if progress_callback:
                progress_callback("Failed to open serial connection")
            return False

        try:
            if progress_callback:
                progress_callback("Testing DTR/RTS control signals...")

            # Test DTR control
            self.serial_connection.dtr = True
            time.sleep(0.25)  # Increased for better visibility
            self.serial_connection.dtr = False
            time.sleep(0.25)

            # Test RTS control
            self.serial_connection.rts = True
            time.sleep(0.25)  # Increased for better visibility
            self.serial_connection.rts = False
            time.sleep(0.25)

            if progress_callback:
                progress_callback("DTR/RTS control test completed")

            return True

        except (serial.SerialException, OSError) as e:
            if progress_callback:
                progress_callback(f"Control signal test failed: {str(e)}")
            return False
        finally:
            self.close_connection()

    def get_signal_mapping_info(self) -> str:
        """Get information about signal mapping.

        Returns:
            String describing the expected signal connections
        """
        return """Expected TTL-RS232 Module Connections:
        
DTR → GPIO0 (Boot pin)
RTS → EN/RST (Reset pin)
TX ↔ RX (Data) ⚠️ Critical for communication
RX ↔ TX (Data) ⚠️ Critical for communication  
GND ↔ GND ⚠️ Must be connected
VCC → 3.3V (Power - if needed)

Signal Logic:
- DTR/RTS are active LOW
- DTR=True → GPIO0=LOW (boot mode)
- RTS=True → EN=LOW (reset)

Boot Sequence:
1. DTR=True (GPIO0=LOW)
2. RTS=True (EN=LOW, reset)  
3. RTS=False (EN=HIGH, release reset)
4. DTR=False (GPIO0=HIGH, optional)

Troubleshooting:
- If "No response" error: Check TX/RX wiring
- If boot fails: Check DTR/RTS connections
- Test with multimeter on ESP32 GPIO0/EN pins"""

    def __enter__(self):
        """Context manager entry."""
        if self.open_connection():
            return self
        raise serial.SerialException(f"Could not open serial port {self.port}")

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close_connection()
