"""
Filter and extract trading signals from log files.

Usage:
    python filter_logs.py                           # Extract all signals
    python filter_logs.py --min-score 80            # Only signals >= 80
    python filter_logs.py --level TRADE_SIGNAL      # Only TRADE_SIGNAL level
    python filter_logs.py --output signals.log      # Save to file
    python filter_logs.py --tail 50                 # Show last 50 lines
"""

import argparse
import re
from pathlib import Path
from datetime import datetime
from typing import List, Tuple


def parse_log_line(line: str) -> Tuple[str, str, str, str]:
    """
    Parse log line to extract timestamp, level, logger, and message.
    
    Returns:
        (timestamp, level, logger, message)
    """
    # Pattern: 2025-11-26 10:30:15 - logger.name - LEVEL - message
    pattern = r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}(?:,\d{3})?) - (.*?) - (\w+) - (.*)'
    match = re.match(pattern, line)
    
    if match:
        return match.groups()
    return None, None, None, line


def extract_signal_score(message: str) -> float:
    """Extract signal score from message."""
    # Pattern: Signal Score: 85.2/100 or signal score: 85.2
    patterns = [
        r'Signal Score:\s*(\d+\.?\d*)',
        r'signal score:\s*(\d+\.?\d*)',
        r'score:\s*(\d+\.?\d*)/100'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, message, re.IGNORECASE)
        if match:
            return float(match.group(1))
    
    return 0.0


def filter_logs(
    log_file: str,
    output_file: str = None,
    min_score: float = 0.0,
    level: str = None,
    tail: int = None,
    show_context: bool = False
):
    """
    Filter log file for trading signals.
    
    Args:
        log_file: Input log file path
        output_file: Output file path (optional)
        min_score: Minimum signal score to include
        level: Filter by log level (e.g., 'TRADE_SIGNAL')
        tail: Show only last N lines
        show_context: Show lines before/after signal
    """
    log_path = Path(log_file)
    
    if not log_path.exists():
        print(f"❌ Log file not found: {log_path}")
        return
    
    print(f"📖 Reading log file: {log_path}")
    print(f"   Size: {log_path.stat().st_size / 1024:.1f} KB")
    print()
    
    # Read all lines
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    print(f"   Total lines: {len(lines)}")
    
    # Filter lines
    filtered_lines = []
    signal_count = 0
    
    for i, line in enumerate(lines):
        timestamp, log_level, logger, message = parse_log_line(line)
        
        # Check level filter
        if level and log_level != level:
            continue
        
        # Check if line contains signal keywords
        is_signal = any(keyword in line.lower() for keyword in [
            'trade_signal',
            'strong signal detected',
            'signal score',
            '🚀',
            '💰'
        ])
        
        if not is_signal:
            continue
        
        # Check score filter
        if min_score > 0:
            score = extract_signal_score(message)
            if score < min_score:
                continue
        
        # Add context lines if requested
        if show_context:
            # Add 2 lines before
            for j in range(max(0, i-2), i):
                if lines[j] not in filtered_lines:
                    filtered_lines.append(lines[j])
        
        filtered_lines.append(line)
        signal_count += 1
        
        # Add 2 lines after
        if show_context:
            for j in range(i+1, min(len(lines), i+3)):
                if lines[j] not in filtered_lines:
                    filtered_lines.append(lines[j])
    
    print(f"   Signals found: {signal_count}")
    print()
    
    # Apply tail filter
    if tail and len(filtered_lines) > tail:
        filtered_lines = filtered_lines[-tail:]
        print(f"   Showing last {tail} lines")
        print()
    
    # Output results
    if output_file:
        output_path = Path(output_file)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(filtered_lines)
        print(f"✓ Filtered logs saved to: {output_path}")
        print(f"   Lines written: {len(filtered_lines)}")
    else:
        print("=" * 80)
        print("FILTERED LOGS")
        print("=" * 80)
        print()
        for line in filtered_lines:
            print(line, end='')
        print()
        print("=" * 80)
        print(f"Total: {len(filtered_lines)} lines")


def analyze_signals(log_file: str):
    """Analyze signal statistics from log file."""
    log_path = Path(log_file)
    
    if not log_path.exists():
        print(f"❌ Log file not found: {log_path}")
        return
    
    print(f"📊 Analyzing signals in: {log_path}")
    print()
    
    with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    scores = []
    signal_times = []
    
    for line in lines:
        if any(keyword in line.lower() for keyword in ['trade_signal', 'strong signal']):
            # Extract score
            score = extract_signal_score(line)
            if score > 0:
                scores.append(score)
            
            # Extract timestamp
            timestamp, _, _, _ = parse_log_line(line)
            if timestamp:
                signal_times.append(timestamp)
    
    if not scores:
        print("No signals found in log file")
        return
    
    print(f"Total signals: {len(scores)}")
    print(f"Average score: {sum(scores)/len(scores):.2f}")
    print(f"Highest score: {max(scores):.2f}")
    print(f"Lowest score: {min(scores):.2f}")
    print()
    
    # Score distribution
    print("Score distribution:")
    ranges = [(0, 60), (60, 70), (70, 80), (80, 90), (90, 100)]
    for low, high in ranges:
        count = sum(1 for s in scores if low <= s < high)
        pct = (count / len(scores)) * 100
        bar = '█' * int(pct / 2)
        print(f"  {low:3d}-{high:3d}: {count:3d} ({pct:5.1f}%) {bar}")
    
    print()
    
    # Time distribution
    if signal_times:
        print(f"First signal: {signal_times[0]}")
        print(f"Last signal:  {signal_times[-1]}")


def main():
    parser = argparse.ArgumentParser(
        description="Filter and analyze trading signals from log files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python filter_logs.py logs/collector.log
  python filter_logs.py logs/collector.log --min-score 80
  python filter_logs.py logs/collector.log --level TRADE_SIGNAL
  python filter_logs.py logs/collector.log --output signals.log
  python filter_logs.py logs/collector.log --tail 50
  python filter_logs.py logs/collector.log --analyze
        """
    )
    
    parser.add_argument(
        'log_file',
        nargs='?',
        default='logs/collector.log',
        help='Log file to filter (default: logs/collector.log)'
    )
    
    parser.add_argument(
        '--output', '-o',
        help='Output file for filtered logs'
    )
    
    parser.add_argument(
        '--min-score',
        type=float,
        default=0.0,
        help='Minimum signal score to include (default: 0)'
    )
    
    parser.add_argument(
        '--level', '-l',
        help='Filter by log level (e.g., TRADE_SIGNAL, INFO, WARNING)'
    )
    
    parser.add_argument(
        '--tail', '-t',
        type=int,
        help='Show only last N lines'
    )
    
    parser.add_argument(
        '--context', '-c',
        action='store_true',
        help='Show context lines around signals'
    )
    
    parser.add_argument(
        '--analyze', '-a',
        action='store_true',
        help='Analyze signal statistics instead of filtering'
    )
    
    args = parser.parse_args()
    
    if args.analyze:
        analyze_signals(args.log_file)
    else:
        filter_logs(
            args.log_file,
            args.output,
            args.min_score,
            args.level,
            args.tail,
            args.context
        )


if __name__ == "__main__":
    main()
