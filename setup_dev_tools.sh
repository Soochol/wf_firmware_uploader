#!/bin/bash

# Setup script for development tools
# This script installs the necessary Python tools for code formatting and linting

echo "Setting up development tools for WF Firmware Uploader..."

# Check if pipx is available
if command -v pipx &> /dev/null; then
    echo "Using pipx to install development tools..."
    pipx install black
    pipx install isort  
    pipx install flake8
    pipx install pylint
    pipx install mypy
else
    echo "pipx not found. Attempting to install with pip in user mode..."
    
    # Try to install in user mode with --break-system-packages if needed
    python3 -m pip install --user black isort flake8 pylint mypy types-pyserial || \
    python3 -m pip install --user --break-system-packages black isort flake8 pylint mypy types-pyserial
fi

echo "Development tools installation complete!"
echo ""
echo "VS Code configuration files created:"
echo "  - .vscode/settings.json (auto-formatting and linting settings)"  
echo "  - .vscode/extensions.json (recommended extensions)"
echo "  - pyproject.toml (tool configurations)"
echo ""
echo "To use these tools:"
echo "1. Open the project in VS Code"
echo "2. Install recommended extensions when prompted"
echo "3. Press Ctrl+S to auto-format and lint your code"
echo ""
echo "Manual commands:"
echo "  black src/          # Format code"
echo "  isort src/          # Sort imports"  
echo "  flake8 src/         # Style checking"
echo "  pylint src/         # Code analysis"
echo "  mypy src/           # Type checking"