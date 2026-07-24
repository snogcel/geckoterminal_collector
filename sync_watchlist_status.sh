#!/bin/bash
# Synchronize watchlist active status from watchlist_state.json
# Usage: ./sync_watchlist_status.sh [--dry-run] [--json-path PATH] [--config PATH]

echo "========================================"
echo "Watchlist Active Status Synchronization"
echo "========================================"
echo ""

# Default paths
JSON_PATH="watchlist_state.json"
CONFIG_PATH="config.yaml"
DRY_RUN=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN="--dry-run"
            shift
            ;;
        --json-path)
            JSON_PATH="$2"
            shift 2
            ;;
        --config)
            CONFIG_PATH="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo ""
            echo "Options:"
            echo "  --dry-run           Preview changes without updating database"
            echo "  --json-path PATH    Path to watchlist_state.json (default: watchlist_state.json)"
            echo "  --config PATH       Path to config.yaml (default: config.yaml)"
            echo "  -h, --help          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use -h or --help for usage information"
            exit 1
            ;;
    esac
done

echo "Using JSON file: $JSON_PATH"
echo "Using config file: $CONFIG_PATH"
if [ -n "$DRY_RUN" ]; then
    echo "Mode: DRY RUN (preview only)"
fi
echo ""

# Check if Python is available
if ! command -v python &> /dev/null; then
    if ! command -v python3 &> /dev/null; then
        echo "ERROR: Python is not installed or not in PATH"
        exit 1
    fi
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Run the sync command
$PYTHON_CMD -m examples.cli_with_scheduler sync-watchlist-status \
    --config "$CONFIG_PATH" \
    --json-path "$JSON_PATH" \
    $DRY_RUN

EXIT_CODE=$?

if [ $EXIT_CODE -eq 0 ]; then
    echo ""
    echo "========================================"
    echo "Synchronization completed successfully!"
    echo "========================================"
else
    echo ""
    echo "ERROR: Synchronization failed!"
    exit $EXIT_CODE
fi
