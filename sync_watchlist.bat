@echo off
REM Hourly Enhanced Watchlist Sync Script
REM This script resets all watchlist entries to inactive, then syncs from the micro CSV

echo === Enhanced Watchlist Sync Started at %date% %time% ===

REM Step 1: Reset all watchlist entries to inactive
echo Step 1: Resetting all watchlist entries to inactive...
python -m examples.cli_with_scheduler reset-watchlist --config config.yaml

if %errorlevel% neq 0 (
    echo ERROR: Failed to reset watchlist entries
    exit /b 1
)

REM Step 2: Sync from the micro CSV file
echo Step 2: Syncing from watchlist_updated_micro.csv...
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro" --config config.yaml

if %errorlevel% neq 0 (
    echo ERROR: Failed to sync enhanced watchlist
    exit /b 1
)

echo === Enhanced Watchlist Sync Completed at %date% %time% ===
