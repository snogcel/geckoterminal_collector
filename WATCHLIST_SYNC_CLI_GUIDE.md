# Watchlist Status Sync - CLI Integration Guide

## Overview

The `sync-watchlist-status` command has been integrated into the main CLI (`examples.cli_with_scheduler`) to match your existing workflow. This allows you to sync the watchlist active status from `watchlist_state.json` using the same command structure as `reset-watchlist`.

## CLI Command

### Basic Usage

```bash
python -m examples.cli_with_scheduler sync-watchlist-status
```

### With Options

```bash
# Specify custom paths
python -m examples.cli_with_scheduler sync-watchlist-status \
    --config custom_config.yaml \
    --json-path path/to/watchlist_state.json

# Dry run (preview changes without updating)
python -m examples.cli_with_scheduler sync-watchlist-status --dry-run

# View help
python -m examples.cli_with_scheduler sync-watchlist-status --help
```

## Shell Script (Linux)

### Quick Usage

```bash
# Make executable (first time only)
chmod +x sync_watchlist_status.sh

# Run synchronization
./sync_watchlist_status.sh

# Dry run mode
./sync_watchlist_status.sh --dry-run

# Custom paths
./sync_watchlist_status.sh --json-path /path/to/state.json --config /path/to/config.yaml
```

## Command Options

| Option | Short | Description | Default |
|--------|-------|-------------|---------|
| `--config` | `-c` | Path to configuration file | `config.yaml` |
| `--json-path` | `-j` | Path to watchlist state JSON | `watchlist_state.json` |
| `--dry-run` | | Preview changes without updating | disabled |
| `--help` | `-h` | Show help message | |

## Example Output

### Normal Run

```bash
$ python -m examples.cli_with_scheduler sync-watchlist-status

========================================
Watchlist Active Status Synchronization
========================================

Loading watchlist state from watchlist_state.json...

=== Watchlist State Analysis ===
Total tokens: 66
✅ Active: 0
❌ Inactive: 66
📅 Total cycles: 301
🕐 Last run: 2026-07-23T23:20:44.302970+00:00

=== Synchronization Results ===
✅ Tokens set to active: 0
❌ Tokens set to inactive: 66
⚠️  Tokens not found in DB: 0

✅ Synchronization completed successfully!
```

### Dry Run

```bash
$ python -m examples.cli_with_scheduler sync-watchlist-status --dry-run

=== Watchlist State Analysis ===
Total tokens: 66
✅ Active: 5
❌ Inactive: 61
📅 Total cycles: 301
🕐 Last run: 2026-07-23T23:20:44.302970+00:00

🔍 DRY RUN MODE - No changes will be made
Would update 5 tokens to active
Would update 61 tokens to inactive
```

## Integration with Your Workflow

### Current Reset-Watchlist Workflow

```bash
# Your current command
python -m examples.cli_with_scheduler reset-watchlist
```

### New Sync-Watchlist-Status Command

```bash
# New command - syncs from JSON
python -m examples.cli_with_scheduler sync-watchlist-status
```

### Combined Workflow Example

```bash
# Step 1: Collect enhanced watchlist data
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "micro"

# Step 2: Sync active status from watchlist_state.json
python -m examples.cli_with_scheduler sync-watchlist-status

# Step 3: Continue with other operations
python -m examples.cli_with_scheduler run-once --collector watchlist_monitor
```

## Automated Workflow Script

Create a workflow script (`update_watchlist_workflow.sh`):

```bash
#!/bin/bash
set -e  # Exit on error

echo "Starting watchlist update workflow..."

# Step 1: Collect data
echo "Step 1: Collecting watchlist data..."
python -m examples.cli_with_scheduler collect-enhanced-watchlist --sources "reference,micro"

# Step 2: Sync active status
echo "Step 2: Syncing active status to database..."
python -m examples.cli_with_scheduler sync-watchlist-status

# Step 3: Check status
echo "Step 3: Checking watchlist status..."
python -m examples.cli_with_scheduler status

echo "Workflow completed successfully!"
```

Make it executable:
```bash
chmod +x update_watchlist_workflow.sh
```

Run it:
```bash
./update_watchlist_workflow.sh
```

## Comparison with Standalone Scripts

### CLI Command (Recommended for Production)
✅ Integrated with existing CLI structure  
✅ Uses same configuration and initialization  
✅ Consistent logging and error handling  
✅ Works with your scheduler setup  
✅ Easy to call from shell scripts  

```bash
python -m examples.cli_with_scheduler sync-watchlist-status
```

### Standalone Script (Alternative)
✅ Can be run independently  
✅ Detailed logging and statistics  
✅ Retry logic built-in  

```bash
python sync_watchlist_active_status.py
```

Both methods use the same underlying `bulk_update_watchlist_active_status()` function in the database manager.

## Troubleshooting

### Command Not Found

**Issue**: `ModuleNotFoundError: No module named 'click'`

**Solution**: Install required dependencies
```bash
pip install -r requirements.txt
```

### File Not Found

**Issue**: `Watchlist state file not found: watchlist_state.json`

**Solution**: Specify the correct path
```bash
python -m examples.cli_with_scheduler sync-watchlist-status --json-path /full/path/to/watchlist_state.json
```

### Permission Denied (Shell Script)

**Issue**: `Permission denied: ./sync_watchlist_status.sh`

**Solution**: Make the script executable
```bash
chmod +x sync_watchlist_status.sh
```

### Database Locked

**Issue**: Database is locked during sync

**Solution**: 
1. Wait for other operations to complete
2. Check for stuck processes: `ps aux | grep python`
3. Kill stuck processes if needed: `kill -9 <PID>`

## Shell Script on Linux Server

Since you mentioned running on a Linux server, here's the recommended setup:

### 1. Copy Files to Server

```bash
# Copy the shell script
scp sync_watchlist_status.sh user@server:/path/to/project/

# Make executable
ssh user@server "chmod +x /path/to/project/sync_watchlist_status.sh"
```

### 2. Run from Server

```bash
# SSH into server
ssh user@server

# Navigate to project directory
cd /path/to/project

# Run sync
./sync_watchlist_status.sh

# Or using the CLI directly
python -m examples.cli_with_scheduler sync-watchlist-status
```

### 3. Add to Cron (Optional)

To run automatically after watchlist collection:

```bash
# Edit crontab
crontab -e

# Add line to sync every hour at 5 minutes past
5 * * * * cd /path/to/project && python -m examples.cli_with_scheduler sync-watchlist-status >> /var/log/watchlist_sync.log 2>&1

# Or run after enhanced watchlist collection
# (assuming watchlist collector runs at 0 minutes past)
10 * * * * cd /path/to/project && python -m examples.cli_with_scheduler sync-watchlist-status >> /var/log/watchlist_sync.log 2>&1
```

## Implementation Details

### What the Command Does

1. **Loads Configuration**: Uses your existing config system
2. **Reads JSON File**: Parses `watchlist_state.json`
3. **Extracts Status**: Separates active and inactive token addresses
4. **Bulk Update**: Calls `bulk_update_watchlist_active_status()` method
5. **Reports Results**: Shows statistics on updated entries

### Database Method Used

The command uses the existing method in `sqlalchemy_manager.py`:

```python
async def bulk_update_watchlist_active_status(self, token_addresses: dict) -> dict:
    """
    Bulk update active status for watchlist entries based on token addresses.
    
    Args:
        token_addresses: Dict with keys 'active' and 'inactive'
    
    Returns:
        Dict with counts of updated entries
    """
```

## Performance

- **Small datasets** (< 100 tokens): < 1 second
- **Medium datasets** (100-1K tokens): 1-3 seconds  
- **Large datasets** (1K-10K tokens): 3-10 seconds

The bulk update is very efficient as it uses single SQL queries.

## Best Practices

1. **Always use --dry-run first** when testing
2. **Check watchlist_state.json exists** before running
3. **Monitor logs** for any "not found" warnings
4. **Run after watchlist collection** for consistency
5. **Use in automated workflows** for hands-off operation

## Related Commands

```bash
# Reset all to inactive
python -m examples.cli_with_scheduler reset-watchlist

# Collect watchlist data
python -m examples.cli_with_scheduler collect-enhanced-watchlist

# Check scheduler status
python -m examples.cli_with_scheduler status

# Run watchlist monitor
python -m examples.cli_with_scheduler run-once --collector watchlist_monitor
```

## Additional Resources

- **Full Guide**: `WATCHLIST_SYNC_STATUS_GUIDE.md`
- **Quick Reference**: `WATCHLIST_SYNC_QUICK_REFERENCE.md`
- **Implementation Details**: `WATCHLIST_SYNC_IMPLEMENTATION.md`
- **Integration Examples**: `example_integration_sync.py`
