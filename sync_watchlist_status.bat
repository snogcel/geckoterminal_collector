@echo off
REM Synchronize watchlist active status from watchlist_state.json
REM Usage: sync_watchlist_status.bat [json_path] [config_path]

echo ========================================
echo Watchlist Active Status Synchronization
echo ========================================
echo.

REM Check if Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Set default paths
set JSON_PATH=watchlist_state.json
set CONFIG_PATH=config.yaml

REM Override with command line arguments if provided
if not "%~1"=="" set JSON_PATH=%~1
if not "%~2"=="" set CONFIG_PATH=%~2

echo Using JSON file: %JSON_PATH%
echo Using config file: %CONFIG_PATH%
echo.

REM Run the sync script
python sync_watchlist_active_status.py "%JSON_PATH%" "%CONFIG_PATH%"

if errorlevel 1 (
    echo.
    echo ERROR: Synchronization failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Synchronization completed successfully!
echo ========================================
pause
