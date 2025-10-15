"""Upload worker thread module."""

from PySide6.QtCore import QThread, Signal


class UploadWorkerThread(QThread):
    """Worker thread for firmware upload tasks."""

    progress_update = Signal(str, str)  # device_type, message
    upload_finished = Signal(
        str, bool, list, bool
    )  # device_type, success, corrected_files, was_fixed

    def __init__(self, device_type, uploader, full_erase=False, erase_only=False, **kwargs):
        """Initialize worker thread."""
        super().__init__()
        self.device_type = device_type
        self.uploader = uploader
        self.full_erase = full_erase
        self.erase_only = erase_only
        self.kwargs = kwargs
        self._stop_requested = False

    def request_stop(self):
        """Request the thread to stop."""
        self._stop_requested = True
        # Set stop flag in uploader if it has one
        if hasattr(self.uploader, "stop_flag"):
            self.uploader.stop_flag = True

    def run(self):
        """Execute upload task with optional full erase."""

        def progress_callback(message):
            try:
                self.progress_update.emit(self.device_type, message)
            except Exception:
                # Silent fail for GUI update errors
                pass

        try:
            success = True
            corrected_files = []
            was_fixed = False

            # Check if automatic mode is enabled
            auto_mode = self.kwargs.get("auto_mode", False)

            # If automatic mode is enabled, let the uploader handle full erase
            # Otherwise, handle full erase here (traditional workflow)
            if auto_mode:
                # Pass full_erase flag to uploader for automatic mode
                # Automatic mode will handle: detect MCU -> erase (if enabled) -> upload -> repeat
                if self.erase_only:
                    # Erase-only doesn't make sense with automatic mode
                    progress_callback("Erase-only mode is not compatible with automatic mode")
                    self.upload_finished.emit(self.device_type, False, [], False)
                    return

                # Step: Upload firmware with automatic mode (includes erase if enabled)
                progress_callback("Starting firmware upload...")

                # ESP32 uploader returns tuple with corrected files info
                if self.device_type == "ESP32":
                    # Add full_erase to kwargs for ESP32 automatic mode only
                    self.kwargs["full_erase"] = self.full_erase
                    result = self.uploader.upload_firmware(
                        progress_callback=progress_callback, **self.kwargs
                    )
                    if isinstance(result, tuple) and len(result) == 3:
                        success, corrected_files, was_fixed = result
                    else:
                        success = result
                else:
                    # STM32 doesn't support full_erase parameter in auto mode yet
                    success = self.uploader.upload_firmware(
                        progress_callback=progress_callback, **self.kwargs
                    )

            else:
                # Traditional workflow: erase first (if requested), then upload
                # Step 1: Full erase if requested
                if self.full_erase or self.erase_only:
                    progress_callback("Starting full flash erase...")
                    port = self.kwargs.get("port", "")
                    erase_success = self.uploader.erase_flash(
                        port, progress_callback=progress_callback
                    )
                    if not erase_success:
                        progress_callback("Flash erase failed")
                        self.upload_finished.emit(self.device_type, False, [], False)
                        return
                    progress_callback("Flash erase completed successfully")

                    # If erase-only mode, we're done
                    if self.erase_only:
                        self.upload_finished.emit(self.device_type, True, [], False)
                        return

                # Step 2: Upload firmware (only if not erase-only)
                progress_callback("Starting firmware upload...")

                # ESP32 uploader returns tuple with corrected files info
                if self.device_type == "ESP32":
                    result = self.uploader.upload_firmware(
                        progress_callback=progress_callback, **self.kwargs
                    )
                    if isinstance(result, tuple) and len(result) == 3:
                        success, corrected_files, was_fixed = result
                    else:
                        success = result
                else:
                    success = self.uploader.upload_firmware(
                        progress_callback=progress_callback, **self.kwargs
                    )

            self.upload_finished.emit(self.device_type, success, corrected_files, was_fixed)

        except Exception as e:
            try:
                error_msg = f"Upload error: {str(e)}"
                self.progress_update.emit(self.device_type, error_msg)
                self.upload_finished.emit(self.device_type, False, [], False)
            except Exception:
                # If even error reporting fails, just emit failure
                try:
                    self.upload_finished.emit(self.device_type, False, [], False)
                except Exception:
                    # Last resort - do nothing if everything fails
                    pass
