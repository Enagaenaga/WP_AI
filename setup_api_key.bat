@echo off
REM Gemini API Key Setup Tool

echo ===================================
echo    Gemini API Key Setup
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
    echo Starting API key setup tool...
    echo.
    python set_api_key.py
) else (
    echo ERROR: Virtual environment not found
    echo Please run start_wp-ai.bat first to complete setup
    pause
    exit /b 1
)

echo.
pause
