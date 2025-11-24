@echo off
setlocal EnableExtensions

cd /d "%~dp0wp-ai"

REM Set UTF-8 encoding
chcp 65001 >nul 2>&1
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"

REM Check for virtual environment
if not exist "..\.venv\Scripts\python.exe" (
    echo Virtual environment not found. Please run setup.bat first.
    pause
    exit /b 1
)

REM Activate virtual environment
call ..\.venv\Scripts\activate.bat

REM Launch GUI
echo Launching WP-AI GUI...
python -m wp_ai.gui.launcher

if errorlevel 1 (
    echo.
    echo Failed to launch GUI.
    echo Error code: %errorlevel%
    pause
    exit /b %errorlevel%
)

pause
