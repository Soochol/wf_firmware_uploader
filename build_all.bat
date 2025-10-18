@echo off
echo ========================================
echo Building WF Firmware Uploader
echo ========================================
echo.

echo [1/2] Building executable with PyInstaller...
uv run pyinstaller wf_firmware_uploader.spec --clean --distpath build/application
if errorlevel 1 (
    echo ERROR: PyInstaller build failed!
    exit /b 1
)
echo.

echo [2/2] Building installer with Inno Setup...
cd build
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" installer.iss
if errorlevel 1 (
    echo ERROR: Inno Setup build failed!
    cd ..
    exit /b 1
)
cd ..
echo.

echo ========================================
echo Build complete!
echo ========================================
echo Executable: build\application\WF_Firmware_Uploader.exe
echo Installer:  build\installer\WF_Firmware_Uploader_Setup_v1.0.0.exe
echo ========================================
