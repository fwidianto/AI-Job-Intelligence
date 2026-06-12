@echo off
REM Job Intelligence Platform - Windows Launcher
REM =============================================

echo ============================================
echo   Job Intelligence Platform
echo ============================================
echo.

REM Get the directory where this batch file is located
set SCRIPT_DIR=%~dp0
cd /d "%SCRIPT_DIR%"

REM Check if virtual environment exists
if exist "venv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
) else (
    echo WARNING: Virtual environment not found.
    echo Run: python -m venv venv
    echo.
)

REM Run the main script
echo.
echo Running Job Intelligence Platform...
echo.

python src\main.py %*

REM Check for errors
if errorlevel 1 (
    echo.
    echo ERROR: Script failed with exit code %errorlevel%
    echo.
    pause
    exit /b %errorlevel%
)

echo.
echo ============================================
echo   Completed successfully!
echo ============================================
echo.

REM Keep window open if run directly (not from command line)
if "%cmdcmdline%" == "" (
    echo Press any key to exit...
    pause >nul
)