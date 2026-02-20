#!/bin/bash
# Hourly Enhanced Watchlist Sync Script
# This script resets all watchlist entries to inactive, then syncs from the micro CSV

echo "=== Enhanced Watchlist Sync Started at $(date) ==="

# Step 1: Reset all watchlist entries to inactive
echo "Step 1: Resetting all watchlist entries to inactive..."
python -m examples.cli_with_scheduler reset-watchlist --config config.yaml

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to reset watchlist entries"
    exit 1
fi

# Step 2: Sync from the micro CSV file
echo "Step 2: Syncing from watchlist_updated_micro.csv..."
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro" --config config.yaml

if [ $? -ne 0 ]; then
    echo "ERROR: Failed to sync enhanced watchlist"
    exit 1
fi

echo "=== Enhanced Watchlist Sync Completed at $(date) ==="
