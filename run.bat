@echo off
echo Starting WF Firmware Uploader...
echo.

REM Check if uv is available
where uv >nul 2>&1
if %errorlevel% == 0 (
    echo Using uv to run the application...
    uv run python src/main.py
) else (
    echo uv not found, trying with standard Python...
    where python >nul 2>&1
    if %errorlevel% == 0 (
        python src/main.py
    ) else (
        echo ERROR: Neither uv nor python found in PATH!
        echo Please install Python or uv and try again.
        echo.
        echo For uv installation: https://docs.astral.sh/uv/
        goto :end
    )
)

:end
echo.
echo Application finished.
pause