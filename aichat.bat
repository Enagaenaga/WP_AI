@echo off
setlocal enabledelayedexpansion
REM WP-AI Chat with LLM

echo ===================================
echo    WP-AI Chat with LLM
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
    
    echo Enter your message (or 'exit' to quit):
    echo.
    set /p MESSAGE="> "
    
    if /i "!MESSAGE!"=="exit" (
        echo Exiting...
        exit /b 0
    )
    
    if not "!MESSAGE!"=="" (
        echo.
        echo Asking AI...
        echo.
        wp-ai aichat ask "!MESSAGE!"
    ) else (
        echo No message entered.
    )
) else (
    echo ERROR: Virtual environment not found
    echo Please run start_wp-ai.bat first to complete setup
    pause
    exit /b 1
)

echo.
pause
