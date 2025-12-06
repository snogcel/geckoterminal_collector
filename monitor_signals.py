"""
Real-time signal monitor - displays latest trading signals.

Usage:
    python monitor_signals.py
    python monitor_signals.py --alerts-dir custom_alerts
    python monitor_signals.py --refresh 2  # Refresh every 2 seconds
"""

import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime


def clear_screen():
    """Clear terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def display_signal(alert_file: Path):
    """Display signal from alert file."""
    if not alert_file.exists():
        return None
    
    try:
        with open(alert_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Get file modification time
        mod_time = datetime.fromtimestamp(alert_file.stat().st_mtime)
        age_seconds = (datetime.now() - mod_time).total_seconds()
        
        return content, mod_time, age_seconds
    except Exception as e:
        return None


def format_age(seconds):
    """Format age in human-readable format."""
    if seconds < 60:
        return f"{int(seconds)}s ago"
    elif seconds < 3600:
        return f"{int(seconds/60)}m ago"
    else:
        return f"{int(seconds/3600)}h ago"


def monitor_signals(alerts_dir: str = "alerts", refresh_interval: int = 3):
    """
    Monitor trading signals in real-time.
    
    Args:
        alerts_dir: Directory containing alert files
        refresh_interval: Refresh interval in seconds
    """
    alerts_path = Path(alerts_dir)
    latest_file = alerts_path / "LATEST_SIGNAL.txt"
    
    print("=" * 80)
    print("🚀 TRADING SIGNAL MONITOR 🚀")
    print("=" * 80)
    print(f"\nMonitoring: {alerts_path.absolute()}")
    print(f"Refresh: Every {refresh_interval} seconds")
    print(f"Press Ctrl+C to exit\n")
    print("=" * 80)
    
    if not alerts_path.exists():
        print(f"\n❌ Alerts directory not found: {alerts_path}")
        print(f"Creating directory...")
        alerts_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ Directory created. Waiting for signals...\n")
    
    last_mod_time = None
    
    try:
        while True:
            result = display_signal(latest_file)
            
            if result:
                content, mod_time, age_seconds = result
                
                # Only update display if signal changed
                if mod_time != last_mod_time:
                    clear_screen()
                    print("=" * 80)
                    print("🚀 LATEST TRADING SIGNAL 🚀")
                    print("=" * 80)
                    print(f"Updated: {mod_time.strftime('%Y-%m-%d %H:%M:%S')} ({format_age(age_seconds)})")
                    print("=" * 80)
                    print()
                    print(content)
                    print()
                    print("=" * 80)
                    print(f"Monitoring... (refreshing every {refresh_interval}s)")
                    print("Press Ctrl+C to exit")
                    
                    last_mod_time = mod_time
                    
                    # Beep on new signal (Windows only)
                    if os.name == 'nt':
                        try:
                            import winsound
                            winsound.Beep(1000, 200)
                        except:
                            pass
            else:
                if last_mod_time is None:
                    clear_screen()
                    print("=" * 80)
                    print("🚀 TRADING SIGNAL MONITOR 🚀")
                    print("=" * 80)
                    print(f"\n⏳ Waiting for signals...")
                    print(f"\nMonitoring: {alerts_path.absolute()}")
                    print(f"Latest signal file: {latest_file.name}")
                    print(f"\nNo signals detected yet. Checking every {refresh_interval}s...")
                    print("\nPress Ctrl+C to exit")
                    last_mod_time = False  # Mark as checked
            
            time.sleep(refresh_interval)
            
    except KeyboardInterrupt:
        print("\n\n" + "=" * 80)
        print("Monitor stopped by user")
        print("=" * 80)
        sys.exit(0)


def list_recent_signals(alerts_dir: str = "alerts", count: int = 10):
    """List recent signal files."""
    alerts_path = Path(alerts_dir)
    
    if not alerts_path.exists():
        print(f"❌ Alerts directory not found: {alerts_path}")
        return
    
    # Get all signal files (excluding LATEST_SIGNAL.txt)
    signal_files = [
        f for f in alerts_path.glob("signal_*.txt")
        if f.name != "LATEST_SIGNAL.txt"
    ]
    
    if not signal_files:
        print(f"No signal files found in {alerts_path}")
        return
    
    # Sort by modification time (newest first)
    signal_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
    
    print("=" * 80)
    print(f"📊 RECENT SIGNALS (Last {count})")
    print("=" * 80)
    print()
    
    for i, signal_file in enumerate(signal_files[:count], 1):
        mod_time = datetime.fromtimestamp(signal_file.stat().st_mtime)
        age_seconds = (datetime.now() - mod_time).total_seconds()
        
        print(f"{i}. {signal_file.name}")
        print(f"   Time: {mod_time.strftime('%Y-%m-%d %H:%M:%S')} ({format_age(age_seconds)})")
        print(f"   Size: {signal_file.stat().st_size} bytes")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Monitor trading signals in real-time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python monitor_signals.py                    # Monitor with defaults
  python monitor_signals.py --refresh 5        # Refresh every 5 seconds
  python monitor_signals.py --list             # List recent signals
  python monitor_signals.py --list --count 20  # List last 20 signals
        """
    )
    
    parser.add_argument(
        '--alerts-dir',
        default='alerts',
        help='Directory containing alert files (default: alerts)'
    )
    
    parser.add_argument(
        '--refresh',
        type=int,
        default=3,
        help='Refresh interval in seconds (default: 3)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List recent signals instead of monitoring'
    )
    
    parser.add_argument(
        '--count',
        type=int,
        default=10,
        help='Number of recent signals to list (default: 10)'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_recent_signals(args.alerts_dir, args.count)
    else:
        monitor_signals(args.alerts_dir, args.refresh)


if __name__ == "__main__":
    main()
