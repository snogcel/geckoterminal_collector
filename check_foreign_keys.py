#!/usr/bin/env python3
"""Check foreign key constraints"""

import asyncio
import asyncpg

async def check_foreign_keys():
    conn = await asyncpg.connect('postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector')
    
    # Get foreign key constraints for ohlcv_data and trades tables
    fks = await conn.fetch("""
        SELECT 
            tc.constraint_name, 
            tc.table_name, 
            kcu.column_name, 
            ccu.table_name AS foreign_table_name, 
            ccu.column_name AS foreign_column_name 
        FROM information_schema.table_constraints AS tc 
        JOIN information_schema.key_column_usage AS kcu 
            ON tc.constraint_name = kcu.constraint_name 
        JOIN information_schema.constraint_column_usage AS ccu 
            ON ccu.constraint_name = tc.constraint_name 
        WHERE constraint_type = 'FOREIGN KEY' 
            AND tc.table_name IN ('ohlcv_data', 'trades', 'pools')
    """)
    
    print("Foreign key constraints:")
    for row in fks:
        print(f"  {row['table_name']}.{row['column_name']} -> {row['foreign_table_name']}.{row['foreign_column_name']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_foreign_keys())