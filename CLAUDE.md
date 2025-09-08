# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Development Setup
- `uv sync --dev` - Install all dependencies including development tools
- `./setup_dev_tools.sh` - Alternative setup script for development tools via pipx/pip

### Code Quality
- `black src/` - Format code (line length: 100)
- `isort src/` - Sort imports (black-compatible profile)
- `flake8 src/` - Style checking
- `pylint src/` - Code analysis
- `mypy src/` - Type checking

### Running the Application
- `python src/main.py` - Run the GUI firmware uploader
- `uv run python src/main.py` - Run via uv (recommended in development)

## Architecture Overview

### Core Components
The application follows a modular architecture with clear separation of concerns:

**UI Layer** (`src/ui/`)
- `main_window.py`: Main PySide6 GUI with tabbed interface for STM32/ESP32
- `components.py`: Reusable UI components
- Uses Qt's threading model with `UploadWorkerThread` for background firmware uploads

**Core Layer** (`src/core/`)
- `stm32_uploader.py`: STM32 firmware upload using STM32_Programmer_CLI
- `esp32_uploader.py`: ESP32 firmware upload using esptool
- `serial_utils.py`: Cross-platform serial port management and device detection

**Entry Point**
- `src/main.py`: Application initialization and Qt setup

### Key Design Patterns
- **Strategy Pattern**: Separate uploader classes for STM32 and ESP32 with common interface
- **Observer Pattern**: Progress callbacks for real-time upload status updates
- **Thread Separation**: UI remains responsive during uploads via QThread workers
- **Device Detection**: Smart filtering of serial ports by VID/PID and device descriptions

### Dependencies
- **PySide6**: Qt6 Python bindings for GUI
- **pyserial**: Serial port communication
- **esptool**: ESP32 firmware flashing tool
- External: STM32CubeProgrammer CLI (Windows) for STM32 uploads

### Configuration
- Code style enforced via Black (100 char line length)
- Import sorting via isort (black profile)
- Linting via flake8 and pylint with custom disable rules
- Type checking via mypy (lenient configuration for GUI code)
- VS Code settings provide auto-formatting and linting integration

### Platform Considerations
- Cross-platform design (Windows, Linux, macOS)
- Windows-specific STM32 programmer path detection and registry lookup
- Serial port detection adapts to platform-specific device naming