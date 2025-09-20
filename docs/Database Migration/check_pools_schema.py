#!/usr/bin/env python3

import psycopg2

def check_pools_schema():
    # Database connection details from config.yaml
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="gecko_terminal_collector",
        user="gecko_collector",
        password="12345678!"
    )
    
    cur = conn.cursor()
    cur.execute("""
        SELECT column_name, data_type, is_nullable, column_default 
        FROM information_schema.columns 
        WHERE table_name = 'pools' 
        ORDER BY ordinal_position;
    """)
    columns = cur.fetchall()
    
    print('Current pools table columns:')
    for col in columns:
        print(f'  {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})')
    
    cur.close()
    conn.close()

if __name__ == "__main__":
    check_pools_schema()