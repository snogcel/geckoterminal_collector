@echo off
REM Quick Test File Cleanup Script
REM This script removes test SQLite database files and test output directories

echo Starting quick test file cleanup...
echo.

REM List files that will be deleted
echo Files to be deleted:
if exist test_*.db (
    echo   Test database files:
    dir test_*.db /b
)
if exist *_test.db (
    echo   Test database files:
    dir *_test.db /b
)
if exist demo_*.db (
    echo   Demo database files:
    dir demo_*.db /b
)
if exist simple_test_*.db (
    echo   Simple test files:
    dir simple_test_*.db /b
)
if exist bulk_demo_*.db (
    echo   Bulk demo files:
    dir bulk_demo_*.db /b
)

echo.
echo Directories to be deleted:
if exist test_output* (
    echo   Test output directories:
    dir test_output* /ad /b
)

echo.
set /p confirm="Do you want to delete these files? (y/N): "
if /i not "%confirm%"=="y" (
    echo Cleanup cancelled.
    pause
    exit /b
)

echo.
echo Deleting test files...

REM Delete test database files
if exist test_*.db (
    del /q test_*.db
    echo Deleted test_*.db files
)

if exist *_test.db (
    del /q *_test.db
    echo Deleted *_test.db files
)

if exist demo_*.db (
    del /q demo_*.db
    echo Deleted demo_*.db files
)

if exist simple_test_*.db (
    del /q simple_test_*.db
    echo Deleted simple_test_*.db files
)

if exist bulk_demo_*.db (
    del /q bulk_demo_*.db
    echo Deleted bulk_demo_*.db files
)

REM Delete specific known test files
if exist test_simple.db (
    del /q test_simple.db
    echo Deleted test_simple.db
)

if exist test_trade_fix.db (
    del /q test_trade_fix.db
    echo Deleted test_trade_fix.db
)

if exist test_enhanced_metadata.db (
    del /q test_enhanced_metadata.db
    echo Deleted test_enhanced_metadata.db
)

if exist new_pools_demo.db (
    del /q new_pools_demo.db
    echo Deleted new_pools_demo.db
)

if exist gecko_data_corrupted_backup.db (
    del /q gecko_data_corrupted_backup.db
    echo Deleted gecko_data_corrupted_backup.db
)

REM Delete test output directories
if exist test_output (
    rmdir /s /q test_output
    echo Deleted test_output directory
)

if exist test_output2 (
    rmdir /s /q test_output2
    echo Deleted test_output2 directory
)

if exist test_output3 (
    rmdir /s /q test_output3
    echo Deleted test_output3 directory
)

if exist test_output4 (
    rmdir /s /q test_output4
    echo Deleted test_output4 directory
)

REM Delete test log files
if exist ohlcv_trade_tests_*.log (
    del /q ohlcv_trade_tests_*.log
    echo Deleted test log files
)

if exist cli_test_results_*.json (
    del /q cli_test_results_*.json
    echo Deleted CLI test result files
)

if exist *_test_report_*.txt (
    del /q *_test_report_*.txt
    echo Deleted test report files
)

echo.
echo Quick cleanup completed!
echo.
pause