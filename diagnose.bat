@echo off
REM WP-AI Diagnostics Direct Execution

echo ===================================
echo    WP-AI Diagnostics
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
    echo Starting WordPress diagnostics...
    echo.
    wp-ai diagnose
) else (
    echo ERROR: Virtual environment not found
    echo Please run start_wp-ai.bat first to complete setup
    pause
    exit /b 1
)

echo.
echo ===================================
echo    Diagnostics completed
echo ===================================
pause
