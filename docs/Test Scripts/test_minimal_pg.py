#!/usr/bin/env python3
"""Test minimal PostgreSQL manager."""

print("Creating minimal PostgreSQL manager...")

# Test each import individually
try:
    from gecko_terminal_collector.config.models import DatabaseConfig
    print("✓ DatabaseConfig")
except Exception as e:
    print(f"❌ DatabaseConfig: {e}")

try:
    from gecko_terminal_collector.database.manager import DatabaseManager
    print("✓ DatabaseManager")
except Exception as e:
    print(f"❌ DatabaseManager: {e}")

try:
    from gecko_terminal_collector.database.models import Pool as PoolModel
    print("✓ Database models")
except Exception as e:
    print(f"❌ Database models: {e}")

try:
    from gecko_terminal_collector.models.core import Pool, Token, TradeRecord, OHLCVRecord
    print("✓ Core models")
except Exception as e:
    print(f"❌ Core models: {e}")

# Now try to create a minimal class
try:
    class TestPostgreSQLManager(DatabaseManager):
        def __init__(self, config):
            super().__init__(config)
            print("TestPostgreSQLManager created!")
    
    print("✓ Minimal class creation works")
    
    # Test instantiation
    config = DatabaseConfig(url="postgresql://test")
    manager = TestPostgreSQLManager(config)
    print("✓ Class instantiation works")
    
except Exception as e:
    print(f"❌ Class creation failed: {e}")
    import traceback
    traceback.print_exc()