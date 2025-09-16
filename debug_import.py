#!/usr/bin/env python3
"""Debug PostgreSQL manager import issues."""

import traceback
import sys

print("Testing PostgreSQL manager import...")

try:
    print("1. Testing individual imports...")
    
    # Test each import individually
    from gecko_terminal_collector.config.models import DatabaseConfig
    print("✓ DatabaseConfig imported")
    
    from gecko_terminal_collector.database.manager import DatabaseManager
    print("✓ DatabaseManager imported")
    
    from gecko_terminal_collector.database.models import Pool as PoolModel
    print("✓ Database models imported")
    
    from gecko_terminal_collector.models.core import Pool, Token
    print("✓ Core models imported")
    
    print("\n2. Testing PostgreSQL manager import...")
    from gecko_terminal_collector.database.postgresql_manager import PostgreSQLDatabaseManager
    print("✓ PostgreSQLDatabaseManager imported successfully!")
    
except Exception as e:
    print(f"❌ Import failed: {e}")
    print("\nFull traceback:")
    traceback.print_exc()
    
    print(f"\nPython version: {sys.version}")
    print(f"Python path: {sys.path[:3]}...")  # Show first 3 paths