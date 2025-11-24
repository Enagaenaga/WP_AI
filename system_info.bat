@echo off
setlocal enabledelayedexpansion
REM WP-AI System Info

echo ===================================
echo    WP-AI System Information
echo ===================================
echo.

REM Change to project directory
cd /d "%~dp0wp-ai"
if errorlevel 1 (
    echo ERROR: wp-ai directory not found
    pause
    exit /b 1
)

REM Activate virtual environment
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
    
    set /p HOST="Enter host name [default]: "
    if "!HOST!"=="" set HOST=default
    
    echo.
    echo Fetching system information from host: !HOST!
    echo.
    wp-ai system info --host !HOST!
) else (
    echo ERROR: Virtual environment not found
    echo Please run start_wp-ai.bat first to complete setup
    pause
    exit /b 1
)

echo.
echo ===================================
echo    System info completed
echo ===================================
pause
