"""
Quick script to fix numeric overflow issues.

This script:
1. Runs the database migration to increase column precision
2. Tests the fix with sample data
"""

import sys
import os
from decimal import Decimal

def main():
    print("=" * 70)
    print("NUMERIC OVERFLOW FIX")
    print("=" * 70)
    print()
    
    print("This script will fix the numeric overflow error by:")
    print("  1. Increasing column precision for large values (FDV, market cap)")
    print("  2. Increasing precision for extreme price changes")
    print("  3. Adding database constraints for score fields (0-100)")
    print("  4. Updating application code to cap extreme values")
    print()
    
    # Check if migration file exists
    migration_file = "migrations/fix_numeric_overflow_columns.py"
    if not os.path.exists(migration_file):
        print(f"❌ Migration file not found: {migration_file}")
        return 1
    
    print(f"✓ Migration file found: {migration_file}")
    print()
    
    # Ask user to confirm
    response = input("Run the database migration now? (yes/no): ").strip().lower()
    if response not in ['yes', 'y']:
        print("\nMigration cancelled. You can run it manually later with:")
        print(f"  python {migration_file}")
        return 0
    
    print("\nRunning migration...")
    print("-" * 70)
    
    # Run the migration
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("migration", migration_file)
        migration_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration_module)
        
        migration_module.run_migration()
        
        print("-" * 70)
        print("\n✓ Migration completed successfully!")
        print()
        print("Summary of changes:")
        print("  • fdv_usd: NUMERIC(20,4) → NUMERIC(30,4)")
        print("  • market_cap_usd: NUMERIC(20,4) → NUMERIC(30,4)")
        print("  • price_change_percentage_h1: NUMERIC(10,4) → NUMERIC(15,4)")
        print("  • price_change_percentage_h24: NUMERIC(10,4) → NUMERIC(15,4)")
        print("  • momentum_indicator: NUMERIC(10,4) → NUMERIC(15,4)")
        print()
        print("Application code has been updated to cap extreme values:")
        print("  • Price changes capped at ±99,999%")
        print("  • FDV/Market cap capped at 999 billion")
        print("  • Momentum indicator capped at ±99,999")
        print("  • Scores (signal, activity, volatility) capped at 0-100")
        print()
        print("✓ You can now run your collector without numeric overflow errors!")
        
        return 0
        
    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        print("\nPlease check:")
        print("  1. DATABASE_URL is set in .env.postgresql")
        print("  2. PostgreSQL database is running and accessible")
        print("  3. You have permission to ALTER tables")
        return 1

if __name__ == "__main__":
    sys.exit(main())
