@echo off
REM Build MSI installer for WF Firmware Uploader
REM This script uses WiX Toolset to create the MSI

echo ===============================================
echo WF Firmware Uploader - MSI Builder
echo ===============================================
echo.

REM Check if WiX is installed
where candle.exe >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: WiX Toolset not found!
    echo.
    echo Please install WiX Toolset v3.11+ from:
    echo https://wixtoolset.org/releases/
    echo.
    echo Add WiX bin directory to PATH, then run this script again.
    echo.
    pause
    exit /b 1
)

echo [1/4] Cleaning previous build...
if exist "..\installer_output" rmdir /s /q "..\installer_output"
mkdir "..\installer_output"

echo [2/4] Creating WXS file...
echo ^<?xml version="1.0" encoding="UTF-8"?^> > installer.wxs
echo ^<Wix xmlns="http://schemas.microsoft.com/wix/2006/wi"^> >> installer.wxs
echo   ^<Product Id="*" Name="WF Firmware Uploader" Language="1033" Version="1.0.0" >> installer.wxs
echo            Manufacturer="WF Team" UpgradeCode="A1B2C3D4-E5F6-7890-ABCD-EF1234567890"^> >> installer.wxs
echo     ^<Package InstallerVersion="200" Compressed="yes" InstallScope="perMachine" /^> >> installer.wxs
echo     ^<MajorUpgrade DowngradeErrorMessage="A newer version is already installed." /^> >> installer.wxs
echo     ^<MediaTemplate EmbedCab="yes" /^> >> installer.wxs
echo. >> installer.wxs
echo     ^<Feature Id="ProductFeature" Title="WF Firmware Uploader" Level="1"^> >> installer.wxs
echo       ^<ComponentGroupRef Id="ProductComponents" /^> >> installer.wxs
echo     ^</Feature^> >> installer.wxs
echo   ^</Product^> >> installer.wxs
echo. >> installer.wxs
echo   ^<Fragment^> >> installer.wxs
echo     ^<Directory Id="TARGETDIR" Name="SourceDir"^> >> installer.wxs
echo       ^<Directory Id="ProgramFilesFolder"^> >> installer.wxs
echo         ^<Directory Id="INSTALLFOLDER" Name="WF Firmware Uploader" /^> >> installer.wxs
echo       ^</Directory^> >> installer.wxs
echo       ^<Directory Id="ProgramMenuFolder"^> >> installer.wxs
echo         ^<Directory Id="ApplicationProgramsFolder" Name="WF Firmware Uploader"/^> >> installer.wxs
echo       ^</Directory^> >> installer.wxs
echo     ^</Directory^> >> installer.wxs
echo   ^</Fragment^> >> installer.wxs
echo. >> installer.wxs
echo   ^<Fragment^> >> installer.wxs
echo     ^<ComponentGroup Id="ProductComponents" Directory="INSTALLFOLDER"^> >> installer.wxs
echo       ^<Component Id="MainExecutable" Guid="*"^> >> installer.wxs
echo         ^<File Id="WFUploaderEXE" Source="dist\wf_firmware_uploader.exe" KeyPath="yes" /^> >> installer.wxs
echo         ^<Shortcut Id="StartMenuShortcut" Directory="ApplicationProgramsFolder" >> installer.wxs
echo                   Name="WF Firmware Uploader" WorkingDirectory="INSTALLFOLDER" >> installer.wxs
echo                   Icon="AppIcon" IconIndex="0" Advertise="yes" /^> >> installer.wxs
echo       ^</Component^> >> installer.wxs
echo     ^</ComponentGroup^> >> installer.wxs
echo   ^</Fragment^> >> installer.wxs
echo. >> installer.wxs
echo   ^<Fragment^> >> installer.wxs
echo     ^<Icon Id="AppIcon" SourceFile="dist\wf_firmware_uploader.exe" /^> >> installer.wxs
echo   ^</Fragment^> >> installer.wxs
echo ^</Wix^> >> installer.wxs

echo [3/4] Compiling WiX object file...
candle.exe installer.wxs -o "..\installer_output\installer.wixobj"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to compile WXS file
    pause
    exit /b 1
)

echo [4/4] Linking MSI installer...
light.exe "..\installer_output\installer.wixobj" -o "..\installer_output\WF_Firmware_Uploader_v1.0.0.msi"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to create MSI
    pause
    exit /b 1
)

echo.
echo ===============================================
echo SUCCESS! MSI installer created:
echo %~dp0..\installer_output\WF_Firmware_Uploader_v1.0.0.msi
echo ===============================================
echo.
pause
