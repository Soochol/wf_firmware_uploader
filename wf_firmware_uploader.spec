# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for WF Firmware Uploader."""

import sys
from pathlib import Path

block_cipher = None

# Get the project root directory
project_root = Path(SPECPATH)

a = Analysis(
    ['src/main.py'],
    pathex=[str(project_root / 'src')],
    binaries=[],
    datas=[
        # Firmware files for ESP32 and STM32
        (str(project_root / 'firmwares' / 'esp32' / 'bootloader.bin'), 'firmwares/esp32'),
        (str(project_root / 'firmwares' / 'esp32' / 'partitions.bin'), 'firmwares/esp32'),
        (str(project_root / 'firmwares' / 'esp32' / 'firmware.bin'), 'firmwares/esp32'),
        (str(project_root / 'firmwares' / 'stm32' / 'WithForce_1.00.34.hex'), 'firmwares/stm32'),
    ],
    hiddenimports=[
        'PySide6.QtCore',
        'PySide6.QtGui',
        'PySide6.QtWidgets',
        'serial',
        'serial.tools',
        'serial.tools.list_ports',
        'esptool',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Exclude unnecessary modules to reduce size
        'matplotlib',
        'numpy',
        'pandas',
        'PIL',
        'tkinter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WF_Firmware_Uploader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # Set to False for GUI app (no console window)
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,  # Add icon file path here if you have one
)
