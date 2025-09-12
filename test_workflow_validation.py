#!/usr/bin/env python3
"""
Test script for the watchlist-to-QLib workflow validation.
"""

import asyncio
import sys
import tempfile
from pathlib import Path

# Add the project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

from gecko_terminal_collector.cli import build_ohlcv_command, validate_workflow_command


class MockArgs:
    """Mock arguments class for testing CLI commands."""
    
    def __init__(self, **kwargs):
        self.config = "config.yaml"
        self.verbose = True
        for key, value in kwargs.items():
            setattr(self, key, value)


async def test_build_ohlcv_command():
    """Test the build-ohlcv CLI command."""
    print("Testing build-ohlcv command*...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        args = MockArgs(
            watchlist_item="CBRL",
            output=temp_dir,
            timeframe="1h",
            days=14,
            include_realtime=True,
            validate_data=True,
            force=False
        )
        
        try:
            result = await build_ohlcv_command(args)
            print(f"build-ohlcv command result: {result}")
            return result == 0
        except Exception as e:
            print(f"build-ohlcv command failed: {e}")
            return False


async def test_validate_workflow_command():
    """Test the validate-workflow CLI command."""
    print("Testing validate-workflow command...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        args = MockArgs(
            watchlist_file="specs/watchlist_with_prefix.csv",
            output=temp_dir,
            timeframe="1h",
            sample_size=1,
            days=14,
            use_real_api=False,  # Use mock API for testing
            detailed_report=True
        )
        
        try:
            result = await validate_workflow_command(args)
            print(f"validate-workflow command result: {result}")
            return result == 0
        except Exception as e:
            print(f"validate-workflow command failed: {e}")
            return False


async def main():
    """Run all tests."""
    print("Starting workflow validation tests...")
    
    # Test individual commands
    build_success = await test_build_ohlcv_command()
    #validate_success = await test_validate_workflow_command()
    
    # Summary
    print("\n" + "="*50)
    print("TEST RESULTS")
    print("="*50)
    print(f"build-ohlcv command: {'PASS' if build_success else 'FAIL'}")
    #print(f"validate-workflow command: {'PASS' if validate_success else 'FAIL'}")
    
    overall_success = build_success and validate_success
    print(f"\nOverall: {'PASS' if overall_success else 'FAIL'}")
    
    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))