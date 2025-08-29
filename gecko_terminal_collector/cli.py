"""
Command-line interface for GeckoTerminal Data Collector.
"""

import argparse
import sys
from pathlib import Path


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="GeckoTerminal Data Collector CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="gecko-terminal-collector 0.1.0"
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration file (default: config.yaml)"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Init command
    init_parser = subparsers.add_parser("init", help="Initialize configuration and database")
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing configuration"
    )
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate configuration")
    
    # Start command (placeholder)
    start_parser = subparsers.add_parser("start", help="Start data collection")
    start_parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run as daemon process"
    )
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return 1
    
    if args.command == "init":
        return init_command(args)
    elif args.command == "validate":
        return validate_command(args)
    elif args.command == "start":
        return start_command(args)
    
    return 0


def init_command(args):
    """Initialize configuration and database."""
    config_path = Path(args.config)
    
    if config_path.exists() and not args.force:
        print(f"Configuration file {config_path} already exists. Use --force to overwrite.")
        return 1
    
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        
        manager = ConfigManager(str(config_path))
        config = manager.load_config()
        
        print(f"Configuration initialized at {config_path}")
        print(f"Database URL: {config.database.url}")
        print(f"Target DEXes: {', '.join(config.dexes.targets)}")
        print(f"Network: {config.dexes.network}")
        
        return 0
        
    except Exception as e:
        print(f"Error initializing configuration: {e}")
        return 1


def validate_command(args):
    """Validate configuration file."""
    config_path = Path(args.config)
    
    if not config_path.exists():
        print(f"Configuration file {config_path} not found.")
        return 1
    
    try:
        from gecko_terminal_collector.config.manager import ConfigManager
        
        manager = ConfigManager(str(config_path))
        config = manager.load_config()
        
        errors = config.validate()
        if errors:
            print("Configuration validation failed:")
            for error in errors:
                print(f"  - {error}")
            return 1
        else:
            print("Configuration is valid.")
            return 0
            
    except Exception as e:
        print(f"Error validating configuration: {e}")
        return 1


def start_command(args):
    """Start data collection (placeholder)."""
    print("Data collection start command not yet implemented.")
    print("This will be implemented in future tasks.")
    return 0


if __name__ == "__main__":
    sys.exit(main())