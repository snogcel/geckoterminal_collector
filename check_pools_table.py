#!/usr/bin/env python3
"""Check pools table structure"""

import asyncio
import asyncpg

async def check_pools_table():
    conn = await asyncpg.connect('postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector')
    
    # Get pools table columns
    cols = await conn.fetch("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns 
        WHERE table_name = 'pools' 
        ORDER BY ordinal_position
    """)
    
    print("Pools table columns:")
    for col in cols:
        nullable = "nullable" if col['is_nullable'] == 'YES' else "NOT NULL"
        default = f" (default: {col['column_default']})" if col['column_default'] else ""
        print(f"  {col['column_name']}: {col['data_type']} {nullable}{default}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_pools_table())