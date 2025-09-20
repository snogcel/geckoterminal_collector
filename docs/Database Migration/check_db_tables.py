#!/usr/bin/env python3
"""Check what tables exist in the database"""

import asyncio
import asyncpg

async def check_tables():
    conn = await asyncpg.connect('postgresql://gecko_collector:12345678!@localhost:5432/gecko_terminal_collector')
    
    # Get all tables
    tables = await conn.fetch("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    
    print("Existing tables:")
    for row in tables:
        print(f"  {row['table_name']}")
    
    # Check if ohlcv_data table exists and get its columns
    if any(row['table_name'] == 'ohlcv_data' for row in tables):
        print("\nOHLCV_DATA table columns:")
        columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'ohlcv_data' 
            ORDER BY ordinal_position
        """)
        for col in columns:
            print(f"  {col['column_name']}: {col['data_type']}")
    
    # Check if trade_data table exists
    if any(row['table_name'] == 'trade_data' for row in tables):
        print("\nTRADE_DATA table columns:")
        columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'trade_data' 
            ORDER BY ordinal_position
        """)
        for col in columns:
            print(f"  {col['column_name']}: {col['data_type']}")
    
    # Check if trades table exists
    if any(row['table_name'] == 'trades' for row in tables):
        print("\nTRADES table columns:")
        columns = await conn.fetch("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'trades' 
            ORDER BY ordinal_position
        """)
        for col in columns:
            print(f"  {col['column_name']}: {col['data_type']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(check_tables())