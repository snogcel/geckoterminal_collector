#!/usr/bin/env python3
"""
CLI Signal Commands Fix

This script fixes the signal analysis commands in the CLI by properly placing
the command functions before they are referenced in the parser setup.
"""

import re
from pathlib import Path


def fix_cli_signal_commands():
    """Fix the CLI signal commands by moving functions to correct location."""
    
    cli_file = Path("gecko_terminal_collector/cli.py")
    
    if not cli_file.exists():
        print(f"❌ CLI file not found: {cli_file}")
        return False
    
    print("🔧 Fixing CLI signal commands...")
    
    # Read the entire file
    with open(cli_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the misplaced functions after "if __name__ == "__main__":"
    main_pattern = r'if __name__ == "__main__":\s*sys\.exit\(main\(\)\)\s*\n\n(.*?)$'
    main_match = re.search(main_pattern, content, re.DOTALL)
    
    if not main_match:
        print("❌ Could not find main section")
        return False
    
    misplaced_functions = main_match.group(1)
    
    # Extract the signal command functions
    analyze_pattern = r'(async def analyze_pool_signals_command\(args\):.*?)(?=\n\nasync def|\n\ndef|\Z)'
    monitor_pattern = r'(async def monitor_pool_signals_command\(args\):.*?)(?=\n\nasync def|\n\ndef|\Z)'
    
    analyze_match = re.search(analyze_pattern, misplaced_functions, re.DOTALL)
    monitor_match = re.search(monitor_pattern, misplaced_functions, re.DOTALL)
    
    if not analyze_match or not monitor_match:
        print("❌ Could not find signal command functions")
        return False
    
    analyze_function = analyze_match.group(1).strip()
    monitor_function = monitor_match.group(1).strip()
    
    print("✓ Found signal command functions")
    
    # Find where to insert the functions (before main function)
    main_func_pattern = r'(def main\(\):)'
    main_func_match = re.search(main_func_pattern, content)
    
    if not main_func_match:
        print("❌ Could not find main function")
        return False
    
    # Insert the functions before main()
    insertion_point = main_func_match.start()
    
    new_content = (
        content[:insertion_point] + 
        analyze_function + "\n\n\n" +
        monitor_function + "\n\n\n" +
        content[insertion_point:]
    )
    
    # Remove the misplaced functions from after main
    new_content = re.sub(main_pattern, r'if __name__ == "__main__":\n    sys.exit(main())\n', new_content, flags=re.DOTALL)
    
    # Uncomment the signal command parser additions
    new_content = re.sub(
        r'# Signal analysis commands \(temporarily disabled due to function placement issue\)\s*\n\s*# _add_analyze_pool_signals_command\(subparsers\)\s*\n\s*# _add_monitor_pool_signals_command\(subparsers\)',
        '# Signal analysis commands\n    _add_analyze_pool_signals_command(subparsers)\n    _add_monitor_pool_signals_command(subparsers)',
        new_content
    )
    
    # Uncomment the command handlers
    new_content = re.sub(
        r'# "analyze-pool-signals": analyze_pool_signals_command,  # Temporarily disabled\s*\n\s*# "monitor-pool-signals": monitor_pool_signals_command,  # Temporarily disabled',
        '"analyze-pool-signals": analyze_pool_signals_command,\n        "monitor-pool-signals": monitor_pool_signals_command,',
        new_content
    )
    
    # Write the fixed content
    with open(cli_file, 'w', encoding='utf-8') as f:
        f.write(new_content)
    
    print("✓ Signal command functions moved to correct location")
    print("✓ Parser setup uncommented")
    print("✓ Command handlers uncommented")
    
    return True


def test_cli_fix():
    """Test that the CLI fix worked."""
    import subprocess
    
    print("\n🧪 Testing CLI fix...")
    
    # Test basic help
    try:
        result = subprocess.run(
            ['python', 'gecko_terminal_collector/cli.py', '--help'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            print("✅ Basic CLI help works")
        else:
            print(f"❌ Basic CLI help failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing basic help: {e}")
        return False
    
    # Test signal commands
    signal_commands = ['analyze-pool-signals', 'monitor-pool-signals']
    
    for cmd in signal_commands:
        try:
            result = subprocess.run(
                ['python', 'gecko_terminal_collector/cli.py', cmd, '--help'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print(f"✅ {cmd} help works")
            else:
                if "invalid choice" in result.stderr:
                    print(f"❌ {cmd} not available in CLI")
                    return False
                else:
                    print(f"❌ {cmd} help failed: {result.stderr}")
                    return False
                    
        except Exception as e:
            print(f"❌ Error testing {cmd}: {e}")
            return False
    
    return True


def main():
    """Main function."""
    print("🚀 CLI Signal Commands Fix")
    print("=" * 50)
    
    # Fix the CLI
    if not fix_cli_signal_commands():
        print("\n❌ Failed to fix CLI signal commands")
        return 1
    
    # Test the fix
    if not test_cli_fix():
        print("\n❌ CLI fix verification failed")
        return 1
    
    print("\n✅ CLI signal commands fixed successfully!")
    print("\nThe following commands are now available:")
    print("  • analyze-pool-signals - Analyze pool signals from new pools history")
    print("  • monitor-pool-signals - Monitor pools for signal conditions")
    
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())