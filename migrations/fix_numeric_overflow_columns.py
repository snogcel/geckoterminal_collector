"""
Migration to fix numeric overflow issues in new_pools_history table.

This migration increases precision for columns that can have large values
and adds constraints to cap percentage/score values at reasonable limits.
"""

from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv('.env.postgresql')

def run_migration():
    """Run the migration to fix numeric overflow issues."""
    
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        raise ValueError("DATABASE_URL not found in environment variables")
    
    engine = create_engine(database_url)
    
    migrations = [
        # Increase precision for FDV (can be in billions)
        """
        ALTER TABLE new_pools_history 
        ALTER COLUMN fdv_usd TYPE NUMERIC(30, 4);
        """,
        
        # Increase precision for market cap (can also be very large)
        """
        ALTER TABLE new_pools_history 
        ALTER COLUMN market_cap_usd TYPE NUMERIC(30, 4);
        """,
        
        # Increase precision for price change percentages (can have extreme spikes)
        # But we'll cap these in the application logic
        """
        ALTER TABLE new_pools_history 
        ALTER COLUMN price_change_percentage_h1 TYPE NUMERIC(15, 4);
        """,
        
        """
        ALTER TABLE new_pools_history 
        ALTER COLUMN price_change_percentage_h24 TYPE NUMERIC(15, 4);
        """,
        
        # Increase precision for momentum indicator
        """
        ALTER TABLE new_pools_history 
        ALTER COLUMN momentum_indicator TYPE NUMERIC(15, 4);
        """,
        
        # Add check constraints to ensure scores stay within reasonable bounds
        # (These will be enforced at DB level)
        """
        ALTER TABLE new_pools_history 
        ADD CONSTRAINT chk_signal_score_range 
        CHECK (signal_score IS NULL OR (signal_score >= 0 AND signal_score <= 100));
        """,
        
        """
        ALTER TABLE new_pools_history 
        ADD CONSTRAINT chk_activity_score_range 
        CHECK (activity_score IS NULL OR (activity_score >= 0 AND activity_score <= 100));
        """,
        
        """
        ALTER TABLE new_pools_history 
        ADD CONSTRAINT chk_volatility_score_range 
        CHECK (volatility_score IS NULL OR (volatility_score >= 0 AND volatility_score <= 100));
        """,
    ]
    
    with engine.connect() as conn:
        for i, migration_sql in enumerate(migrations, 1):
            try:
                print(f"Running migration {i}/{len(migrations)}...")
                conn.execute(text(migration_sql))
                conn.commit()
                print(f"✓ Migration {i} completed successfully")
            except Exception as e:
                # Some constraints might already exist, that's okay
                if "already exists" in str(e).lower():
                    print(f"⚠ Migration {i} skipped (already applied)")
                    conn.rollback()
                else:
                    print(f"✗ Migration {i} failed: {e}")
                    conn.rollback()
                    raise
    
    print("\n✓ All migrations completed successfully!")
    print("\nColumn precision updates:")
    print("  - fdv_usd: NUMERIC(10,4) → NUMERIC(30,4)")
    print("  - market_cap_usd: NUMERIC(10,4) → NUMERIC(30,4)")
    print("  - price_change_percentage_h1: NUMERIC(10,4) → NUMERIC(15,4)")
    print("  - price_change_percentage_h24: NUMERIC(10,4) → NUMERIC(15,4)")
    print("  - momentum_indicator: NUMERIC(10,4) → NUMERIC(15,4)")
    print("\nConstraints added:")
    print("  - signal_score: 0-100 range")
    print("  - activity_score: 0-100 range")
    print("  - volatility_score: 0-100 range")

if __name__ == "__main__":
    run_migration()
