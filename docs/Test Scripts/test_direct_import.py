#!/usr/bin/env python3
"""Test direct import of PostgreSQL manager."""

import sys
import traceback

print("Testing direct import...")

try:
    # Try importing the module
    import gecko_terminal_collector.database.postgresql_manager as pg_module
    print(f"Module imported: {pg_module}")
    print(f"Module attributes: {dir(pg_module)}")
    
    # Check if class exists
    if hasattr(pg_module, 'PostgreSQLDatabaseManager'):
        print("✓ PostgreSQLDatabaseManager class found!")
        cls = getattr(pg_module, 'PostgreSQLDatabaseManager')
        print(f"Class: {cls}")
    else:
        print("❌ PostgreSQLDatabaseManager class not found")
        
except Exception as e:
    print(f"❌ Error: {e}")
    traceback.print_exc()