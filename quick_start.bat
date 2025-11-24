@echo off
REM WP-AI Quick Start (Direct Interactive Mode)

echo ===================================
echo    WP-AI Quick Start
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
    echo Showing help and available commands...
    echo.
    wp-ai --help
    echo.
    echo.
    echo To execute a specific command, use:
    echo   wp-ai COMMAND [OPTIONS]
    echo.
    echo Examples:
    echo   wp-ai system info --host default
    echo   wp-ai aichat ask "What is WordPress?"
    echo   wp-ai say "list all active plugins" --host default
    echo.
) else (
    echo ERROR: Virtual environment not found
    echo Please run start_wp-ai.bat first to complete setup
    pause
    exit /b 1
)

pause
